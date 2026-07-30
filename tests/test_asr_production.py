from __future__ import annotations

import json
import socket
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from liveclip.asr import adapters as adapters_module
from liveclip.asr.adapters import (
    AdapterSegment,
    create_adapter,
    offline_network_guard,
)
from liveclip.asr.exporters import (
    cleanup_work_dir,
    format_srt_timestamp,
    render_srt,
    render_transcript,
)
from liveclip.asr.pipeline import (
    ASRPipelineError,
    StateFileError,
    run_transcription,
)
from liveclip.asr.timeline import (
    TimelineValidationError,
    build_timeline,
    canonical_segment,
    validate_timeline,
)
from liveclip.cli import build_parser
from liveclip.media import FFmpegPaths, MediaProbe, StreamInfo


@dataclass
class FakeAdapter:
    engine: str = "paraformer"
    identity: str = "fake-model-v1"
    segments: list[AdapterSegment] = field(
        default_factory=lambda: [AdapterSegment(0, 900, "  测试 文本？  ")]
    )
    fail_on_call: int | None = None
    calls: list[str] = field(default_factory=list)

    def transcribe(self, wav_path: Path) -> list[AdapterSegment]:
        self.calls.append(wav_path.name)
        if self.fail_on_call == len(self.calls):
            raise RuntimeError("fake recognition failure")
        return list(self.segments)


def fake_paths(tmp_path: Path) -> FFmpegPaths:
    return FFmpegPaths(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe")


def fake_probe(duration_seconds: float = 25.0):
    def probe(path: Path, **_: Any) -> MediaProbe:
        return MediaProbe(
            path=Path(path).resolve(),
            container_format="mov,mp4,m4a,3gp,3g2,mj2",
            duration_seconds=duration_seconds,
            file_size_bytes=Path(path).stat().st_size,
            video_streams=(StreamInfo(0, "video", "h264"),),
            audio_streams=(StreamInfo(1, "audio", "aac", sample_rate=48000, channels=2),),
        )

    return probe


def fake_extract(
    source: Path,
    output: Path,
    *,
    duration_ms: int,
    **_: Any,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * max(1, int(duration_ms * 16)))
    return output


def run_fake(
    source: Path,
    output: Path,
    *,
    adapter: FakeAdapter | None = None,
    duration_seconds: float = 25.0,
    chunk_seconds: float = 10.0,
    after_chunk=None,
):
    return run_transcription(
        source,
        output_dir=output,
        engine=(adapter.engine if adapter else "paraformer"),
        chunk_seconds=chunk_seconds,
        adapter=adapter or FakeAdapter(),
        paths=fake_paths(output),
        progress=lambda _: None,
        after_chunk=after_chunk,
        probe_function=fake_probe(duration_seconds),
        extract_function=fake_extract,
    )


def test_mp4_path_with_chinese_spaces_and_parentheses(tmp_path: Path) -> None:
    source = tmp_path / "中文 路径" / "直播 (测试).mp4"
    source.parent.mkdir()
    original = b"fake-mp4-source"
    source.write_bytes(original)
    result = run_fake(source, tmp_path / "输出 目录")
    timeline = json.loads(result.timeline_path.read_text(encoding="utf-8"))
    assert timeline["source"]["file_name"] == "直播 (测试).mp4"
    assert source.read_bytes() == original


def test_missing_and_non_mp4_inputs_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ASRPipelineError, match="does not exist"):
        run_fake(tmp_path / "missing.mp4", tmp_path / "out")
    text = tmp_path / "input.txt"
    text.write_text("x", encoding="utf-8")
    with pytest.raises(ASRPipelineError, match=r"\.mp4"):
        run_fake(text, tmp_path / "out2")


def test_timeline_accepts_valid_ordered_segments() -> None:
    timeline = build_timeline(
        file_name="sample.mp4",
        duration_ms=3000,
        source_sha256="a" * 64,
        engine="paraformer",
        segments=[
            canonical_segment(start_ms=0, end_ms=1000, text_raw="第一段"),
            canonical_segment(start_ms=1000, end_ms=2000, text_raw="第二段"),
        ],
    )
    validate_timeline(timeline)
    assert [segment["id"] for segment in timeline["segments"]] == [1, 2]


def test_timeline_rejects_overlap() -> None:
    with pytest.raises(TimelineValidationError, match="overlap"):
        build_timeline(
            file_name="sample.mp4",
            duration_ms=3000,
            source_sha256="b" * 64,
            engine="paraformer",
            segments=[
                canonical_segment(start_ms=0, end_ms=1200, text_raw="第一段"),
                canonical_segment(start_ms=1000, end_ms=2000, text_raw="第二段"),
            ],
        )


def test_empty_recognition_text_is_omitted(tmp_path: Path) -> None:
    source = tmp_path / "silent.mp4"
    source.write_bytes(b"silent")
    adapter = FakeAdapter(segments=[AdapterSegment(0, 500, " \t ")])
    result = run_fake(
        source,
        tmp_path / "silent_liveclip",
        adapter=adapter,
        duration_seconds=2,
        chunk_seconds=2,
    )
    timeline = json.loads(result.timeline_path.read_text(encoding="utf-8"))
    assert timeline["segments"] == []
    assert result.subtitles_path.read_text(encoding="utf-8") == ""
    assert result.transcript_path.read_text(encoding="utf-8") == ""


def test_srt_timestamp_sequence_and_text() -> None:
    segments = [
        {"start_ms": 0, "end_ms": 2350, "text": "第一段"},
        {"start_ms": 3723456, "end_ms": 3724456, "text": "second"},
    ]
    rendered = render_srt(segments)
    assert format_srt_timestamp(3723456) == "01:02:03,456"
    assert "1\n00:00:00,000 --> 00:00:02,350\n第一段" in rendered
    assert "2\n01:02:03,456 --> 01:02:04,456\nsecond" in rendered


def test_transcript_format() -> None:
    rendered = render_transcript(
        [{"start_ms": 0, "end_ms": 2350, "text": "识别文本"}]
    )
    assert rendered == "[00:00:00.000 - 00:00:02.350] 识别文本\n"


def test_adapter_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paraformer = object()
    sensevoice = object()
    monkeypatch.setattr(
        adapters_module, "ParaformerAdapter", lambda root: paraformer
    )
    monkeypatch.setattr(
        adapters_module, "SenseVoiceAdapter", lambda root: sensevoice
    )
    assert create_adapter("paraformer", tmp_path) is paraformer
    assert create_adapter("sensevoice", tmp_path) is sensevoice


def test_cli_default_engine_is_paraformer() -> None:
    args = build_parser().parse_args(["transcribe", "--input", "sample.mp4"])
    assert args.engine == "paraformer"


def test_state_created_and_completed_chunks_resume_without_repeat(
    tmp_path: Path,
) -> None:
    source = tmp_path / "resume.mp4"
    source.write_bytes(b"resume-source")
    output = tmp_path / "resume_liveclip"
    first = FakeAdapter()

    def interrupt_after_first(index: int, _: dict[str, Any]) -> None:
        if index == 0:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_fake(source, output, adapter=first, after_chunk=interrupt_after_first)
    interrupted = json.loads((output / "task_state.json").read_text(encoding="utf-8"))
    assert interrupted["status"] == "interrupted"
    assert len(interrupted["completed_chunks"]) == 1
    first_record = interrupted["completed_chunks"][0]
    assert len(first.calls) == 1

    second = FakeAdapter()
    result = run_fake(source, output, adapter=second)
    completed = json.loads(result.state_path.read_text(encoding="utf-8"))
    assert completed["status"] == "completed"
    assert len(completed["completed_chunks"]) == 3
    assert completed["completed_chunks"][0] == first_record
    assert len(second.calls) == 2


def test_source_change_rejects_old_state(tmp_path: Path) -> None:
    source = tmp_path / "changed.mp4"
    source.write_bytes(b"version-one")
    output = tmp_path / "changed_liveclip"

    def interrupt(_: int, __: dict[str, Any]) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_fake(source, output, after_chunk=interrupt)
    source.write_bytes(b"version-two")
    with pytest.raises(StateFileError, match="does not match"):
        run_fake(source, output)


def test_model_change_rejects_old_state(tmp_path: Path) -> None:
    source = tmp_path / "model-change.mp4"
    source.write_bytes(b"same-source")
    output = tmp_path / "model-change_liveclip"

    def interrupt(_: int, __: dict[str, Any]) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_fake(source, output, adapter=FakeAdapter(identity="model-a"), after_chunk=interrupt)
    with pytest.raises(StateFileError, match="does not match"):
        run_fake(source, output, adapter=FakeAdapter(identity="model-b"))


def test_output_write_failure_keeps_timeline_unpublished(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "write-failure.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "write-failure_liveclip"

    def fail_publish(*_: Any, **__: Any):
        raise OSError("simulated output write failure")

    monkeypatch.setattr(
        "liveclip.asr.pipeline.publish_final_outputs", fail_publish
    )
    with pytest.raises(OSError, match="simulated"):
        run_fake(
            source,
            output,
            duration_seconds=2,
            chunk_seconds=2,
        )
    state = json.loads((output / "task_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert not (output / "timeline.json").exists()


def test_failed_incomplete_task_has_no_completed_timeline(tmp_path: Path) -> None:
    source = tmp_path / "failure.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "failure_liveclip"
    with pytest.raises(RuntimeError, match="fake recognition"):
        run_fake(
            source,
            output,
            adapter=FakeAdapter(fail_on_call=1),
            duration_seconds=2,
            chunk_seconds=2,
        )
    assert not (output / "timeline.json").exists()
    state = json.loads((output / "task_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"


def test_corrupt_state_is_reported_without_replacement(tmp_path: Path) -> None:
    source = tmp_path / "corrupt-state.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "corrupt-state_liveclip"
    output.mkdir()
    state_path = output / "task_state.json"
    state_path.write_text("{bad-json", encoding="utf-8")
    with pytest.raises(StateFileError, match="corrupt"):
        run_fake(source, output, duration_seconds=2, chunk_seconds=2)
    assert state_path.read_text(encoding="utf-8") == "{bad-json"


def test_completed_task_is_idempotent_and_does_not_rerun_adapter(
    tmp_path: Path,
) -> None:
    source = tmp_path / "complete.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "complete_liveclip"
    first = FakeAdapter()
    run_fake(source, output, adapter=first, duration_seconds=2, chunk_seconds=2)
    timeline_before = (output / "timeline.json").read_bytes()
    second = FakeAdapter(fail_on_call=1)
    result = run_fake(
        source,
        output,
        adapter=second,
        duration_seconds=2,
        chunk_seconds=2,
    )
    assert result.already_completed
    assert second.calls == []
    assert (output / "timeline.json").read_bytes() == timeline_before


def test_cleanup_removes_interrupted_ffmpeg_partial(tmp_path: Path) -> None:
    work = tmp_path / ".work"
    work.mkdir()
    (work / ".chunk-00002.deadbeef.part.wav").write_bytes(b"partial")
    cleanup_work_dir(work)
    assert not work.exists()


def test_local_asr_network_guard_blocks_socket_connections() -> None:
    with socket.socket() as client:
        with offline_network_guard(), pytest.raises(
            RuntimeError, match="blocked a network connection"
        ):
            client.connect(("127.0.0.1", 9))

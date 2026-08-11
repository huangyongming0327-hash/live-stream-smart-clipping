from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from liveclip.asr.exporters import atomic_write_json
from liveclip.asr.timeline import build_timeline, canonical_segment
from liveclip.cli import build_parser
from liveclip.media import FFmpegPaths, MediaProbe, StreamInfo
from liveclip.pipeline.runner import PipelineRunError, run_pipeline


ENVIRONMENT = {
    "LIVECLIP_LLM_ENDPOINT": "https://example.invalid/v1/chat/completions",
    "LIVECLIP_LLM_API_KEY": "unit-test-value",
    "LIVECLIP_LLM_MODEL": "fake-model",
}


def fake_paths(tmp_path: Path) -> FFmpegPaths:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_bytes(b"fake")
    ffprobe.write_bytes(b"fake")
    return FFmpegPaths(ffmpeg, ffprobe)


def fake_probe(path: Path, **_: Any) -> MediaProbe:
    return MediaProbe(
        path=Path(path).resolve(),
        container_format="mov,mp4",
        duration_seconds=30.0,
        file_size_bytes=Path(path).stat().st_size,
        video_streams=(StreamInfo(0, "video", "h264"),),
        audio_streams=(StreamInfo(1, "audio", "aac"),),
    )


def write_timeline(video: Path, workdir: Path, *, sha: str | None = None) -> Path:
    timeline = build_timeline(
        file_name=video.name,
        duration_ms=30_000,
        source_sha256=sha or hashlib.sha256(video.read_bytes()).hexdigest(),
        engine="paraformer",
        segments=[
            canonical_segment(start_ms=0, end_ms=15_000, text_raw="第一段字幕"),
            canonical_segment(start_ms=15_000, end_ms=30_000, text_raw="第二段字幕"),
        ],
    )
    workdir.mkdir(parents=True, exist_ok=True)
    return atomic_write_json(workdir / "timeline.json", timeline)


def write_analysis(workdir: Path) -> Path:
    timeline_path = workdir / "timeline.json"
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    timeline_sha = hashlib.sha256(timeline_path.read_bytes()).hexdigest()
    analysis = {
        "schema_version": "1.0",
        "source": {
            "timeline_file_name": "timeline.json",
            "timeline_sha256": timeline_sha,
            "video_file_name": timeline["source"]["file_name"],
            "duration_ms": 30_000,
        },
        "analysis": {
            "provider": "openai_compatible",
            "model": "fake-model",
            "completed": True,
            "generated_at": "2026-08-05T00:00:00Z",
            "window_count": 1,
        },
        "topics": [
            {
                "id": "topic-001",
                "start_segment_id": 1,
                "end_segment_id": 2,
                "start_ms": 0,
                "end_ms": 30_000,
                "title": "合成主题",
                "summary": "合成摘要",
            }
        ],
        "candidates": [
            {
                "id": "candidate-001",
                "topic_id": "topic-001",
                "start_segment_id": 1,
                "end_segment_id": 2,
                "start_ms": 0,
                "end_ms": 30_000,
                "duration_ms": 30_000,
                "title": "合成候选",
                "reason": "用于 runner 测试。",
                "quote_segment_id": 1,
                "quote": "第一段字幕",
                "content_value": 25,
                "problem_solving": 20,
                "emotion_or_reversal": 10,
                "information_density": 15,
                "hook_and_shareability": 10,
                "completeness": 10,
                "risk_penalty": 5,
                "total_score": 85,
                "recommended": True,
            }
        ],
    }
    return atomic_write_json(workdir / "current_analysis.json", analysis)


def dependencies(tmp_path: Path) -> dict[str, Any]:
    return {
        "assets_root": tmp_path,
        "model_root": tmp_path,
        "environ": ENVIRONMENT,
        "ffmpeg_paths": fake_paths(tmp_path),
        "probe_function": fake_probe,
        "model_identity_function": lambda _engine, _root: "fake-identity",
    }


def test_run_parser_defaults_and_options() -> None:
    args = build_parser().parse_args(["run", "--video", "视频.mp4"])
    assert args.workdir is None
    assert args.output is None
    assert args.asr_model == "paraformer"
    assert args.no_open_browser is False
    selected = build_parser().parse_args(
        [
            "run",
            "--video",
            "视频.mp4",
            "--workdir",
            "工作 目录",
            "--output",
            "输出 目录",
            "--asr-model",
            "sensevoice",
            "--no-open-browser",
        ]
    )
    assert selected.asr_model == "sensevoice"
    assert selected.no_open_browser is True


def test_missing_environment_stops_before_asr(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    calls: list[str] = []
    with pytest.raises(PipelineRunError, match="缺少环境变量"):
        run_pipeline(
            video,
            environ={},
            transcribe_function=lambda *_args, **_kwargs: calls.append("asr"),
        )
    assert calls == []


def test_missing_artifacts_call_existing_stages_and_default_paths(tmp_path: Path) -> None:
    video = tmp_path / "中文 视频.mp4"
    video.write_bytes(b"video")
    calls: list[tuple[str, Any]] = []

    def transcribe(source: Path, **kwargs: Any) -> Any:
        calls.append(("transcribe", kwargs["engine"]))
        write_timeline(source, Path(kwargs["output_dir"]))
        return SimpleNamespace(resumed_from_chunk=0)

    def analyze(_timeline: Path, **kwargs: Any) -> Any:
        calls.append(("analyze", kwargs["output_dir"]))
        write_analysis(Path(kwargs["output_dir"]))
        return SimpleNamespace(resumed_from_window=0)

    def review(_video: Path, _timeline: Path, _analysis: Path, **kwargs: Any) -> None:
        calls.append(("review", kwargs))

    result = run_pipeline(
        video,
        asr_model="sensevoice",
        transcribe_function=transcribe,
        analyze_function=analyze,
        review_function=review,
        **dependencies(tmp_path),
    )
    assert [name for name, _ in calls] == ["transcribe", "analyze", "review"]
    assert result.workdir == tmp_path / "中文 视频_liveclip"
    assert result.output_dir == result.workdir / "exports"
    assert calls[-1][1]["open_browser"] is True
    assert result.transcribe_action == "completed"
    assert result.analyze_action == "completed"


def test_valid_timeline_and_analysis_are_reused(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    workdir = tmp_path / "work"
    write_timeline(video, workdir)
    write_analysis(workdir)
    calls: list[str] = []
    run_pipeline(
        video,
        workdir=workdir,
        transcribe_function=lambda *_a, **_k: calls.append("transcribe"),
        analyze_function=lambda *_a, **_k: calls.append("analyze"),
        review_function=lambda *_a, **_k: calls.append("review"),
        **dependencies(tmp_path),
    )
    assert calls == ["review"]


def test_custom_workdir_output_and_no_browser_are_forwarded(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    workdir = tmp_path / "自定义 工作目录"
    output = tmp_path / "自定义 导出目录"
    write_timeline(video, workdir)
    write_analysis(workdir)
    captured: dict[str, Any] = {}

    def review(_video: Path, _timeline: Path, _analysis: Path, **kwargs: Any) -> None:
        captured.update(kwargs)

    result = run_pipeline(
        video,
        workdir=workdir,
        output_dir=output,
        open_browser=False,
        review_function=review,
        **dependencies(tmp_path),
    )
    assert result.workdir == workdir
    assert result.output_dir == output
    assert captured["output_dir"] == output
    assert captured["open_browser"] is False


def test_resume_markers_call_existing_recovery_paths(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "task_state.json").write_text("{}", encoding="utf-8")
    messages: list[str] = []

    def transcribe(source: Path, **kwargs: Any) -> None:
        write_timeline(source, Path(kwargs["output_dir"]))

    def analyze(_timeline: Path, **kwargs: Any) -> None:
        write_analysis(Path(kwargs["output_dir"]))

    run_pipeline(
        video,
        workdir=workdir,
        transcribe_function=transcribe,
        analyze_function=analyze,
        review_function=lambda *_a, **_k: None,
        progress=messages.append,
        **dependencies(tmp_path),
    )
    assert any("字幕识别：已恢复" in message for message in messages)

    (workdir / "current_analysis.json").unlink()
    state = workdir / ".analysis_work" / "analysis_state.json"
    state.parent.mkdir()
    state.write_text("{}", encoding="utf-8")
    messages.clear()
    run_pipeline(
        video,
        workdir=workdir,
        analyze_function=analyze,
        review_function=lambda *_a, **_k: None,
        progress=messages.append,
        **dependencies(tmp_path),
    )
    assert any("爆点分析：已恢复" in message for message in messages)


def test_video_change_never_reuses_old_timeline(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"old")
    workdir = tmp_path / "work"
    write_timeline(video, workdir)
    video.write_bytes(b"new")
    calls: list[str] = []
    with pytest.raises(PipelineRunError, match="不属于当前视频"):
        run_pipeline(
            video,
            workdir=workdir,
            transcribe_function=lambda *_a, **_k: calls.append("asr"),
            **dependencies(tmp_path),
        )
    assert calls == []


@pytest.mark.parametrize("name", ["timeline.json", "current_analysis.json"])
def test_corrupt_artifact_is_preserved(tmp_path: Path, name: str) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    workdir = tmp_path / "work"
    if name == "current_analysis.json":
        write_timeline(video, workdir)
    else:
        workdir.mkdir()
    corrupt = workdir / name
    corrupt.write_text("{broken", encoding="utf-8")
    with pytest.raises(PipelineRunError, match="已损坏"):
        run_pipeline(video, workdir=workdir, **dependencies(tmp_path))
    assert corrupt.read_text(encoding="utf-8") == "{broken"


def test_pipeline_status_is_rederived_atomically_without_private_content(tmp_path: Path) -> None:
    video = tmp_path / "中文 路径" / "source.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video")
    workdir = tmp_path / "工作 目录"
    write_timeline(video, workdir)
    write_analysis(workdir)
    (workdir / "pipeline_status.json").write_text("{broken", encoding="utf-8")
    run_pipeline(
        video,
        workdir=workdir,
        review_function=lambda *_a, **_k: None,
        **dependencies(tmp_path),
    )
    status_path = workdir / "pipeline_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    serialized = status_path.read_text(encoding="utf-8")
    assert status["stages"] == {
        "transcribe": "completed",
        "analyze": "completed",
        "review": "pending",
    }
    assert status["source"]["video_file_name"] == "source.mp4"
    assert str(video.parent) not in serialized
    assert ENVIRONMENT["LIVECLIP_LLM_API_KEY"] not in serialized
    assert "第一段字幕" not in serialized
    assert not list(workdir.glob(".pipeline_status.json.*.tmp"))


def test_existing_analysis_is_validated_after_missing_timeline_is_rebuilt(
    tmp_path: Path,
) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    workdir = tmp_path / "work"
    write_timeline(video, workdir)
    analysis_path = write_analysis(workdir)
    old_analysis = analysis_path.read_bytes()
    (workdir / "timeline.json").unlink()
    analysis_calls: list[str] = []

    def transcribe(source: Path, **kwargs: Any) -> None:
        write_timeline(source, Path(kwargs["output_dir"]))

    run_pipeline(
        video,
        workdir=workdir,
        transcribe_function=transcribe,
        analyze_function=lambda *_a, **_k: analysis_calls.append("analyze"),
        review_function=lambda *_a, **_k: None,
        **dependencies(tmp_path),
    )
    assert analysis_calls == []
    assert analysis_path.read_bytes() == old_analysis


def test_completed_review_status_requires_export_files(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    workdir = tmp_path / "work"
    timeline_path = write_timeline(video, workdir)
    analysis_path = write_analysis(workdir)
    review = {
        "schema_version": "1.0",
        "source": {
            "analysis_file_name": analysis_path.name,
            "analysis_sha256": hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
            "timeline_file_name": timeline_path.name,
            "timeline_sha256": hashlib.sha256(timeline_path.read_bytes()).hexdigest(),
            "video_file_name": video.name,
        },
        "review": {
            "candidate_id": "candidate-001",
            "approved": True,
            "original_start_ms": 0,
            "original_end_ms": 30_000,
            "final_start_ms": 1_000,
            "final_end_ms": 29_000,
            "reviewed_at": "2026-08-05T00:00:00Z",
        },
        "export": {
            "video_file_name": "missing.mp4",
            "subtitle_file_name": "missing.srt",
            "completed": True,
        },
    }
    atomic_write_json(workdir / "review_current.json", review)
    result = run_pipeline(
        video,
        workdir=workdir,
        review_function=lambda *_a, **_k: None,
        **dependencies(tmp_path),
    )
    status = json.loads((workdir / "pipeline_status.json").read_text(encoding="utf-8"))
    assert result.review_completed is False
    assert status["stages"]["review"] == "pending"


def test_completed_review_is_reused_but_review_page_still_opens(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    workdir = tmp_path / "work"
    timeline_path = write_timeline(video, workdir)
    analysis_path = write_analysis(workdir)
    output = workdir / "exports"
    output.mkdir()
    (output / "source_candidate-001.mp4").write_bytes(b"video")
    (output / "source_candidate-001.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\n合成字幕\n",
        encoding="utf-8",
    )
    review = {
        "schema_version": "1.0",
        "source": {
            "analysis_file_name": analysis_path.name,
            "analysis_sha256": hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
            "timeline_file_name": timeline_path.name,
            "timeline_sha256": hashlib.sha256(timeline_path.read_bytes()).hexdigest(),
            "video_file_name": video.name,
        },
        "review": {
            "candidate_id": "candidate-001",
            "approved": True,
            "original_start_ms": 0,
            "original_end_ms": 30_000,
            "final_start_ms": 1_000,
            "final_end_ms": 29_000,
            "reviewed_at": "2026-08-05T00:00:00Z",
        },
        "export": {
            "video_file_name": "source_candidate-001.mp4",
            "subtitle_file_name": "source_candidate-001.srt",
            "completed": True,
            "subtitles_burned_in": True,
        },
    }
    atomic_write_json(workdir / "review_current.json", review)
    calls: list[str] = []
    messages: list[str] = []
    result = run_pipeline(
        video,
        workdir=workdir,
        review_function=lambda *_a, **_k: calls.append("review"),
        progress=messages.append,
        **dependencies(tmp_path),
    )
    status = json.loads((workdir / "pipeline_status.json").read_text(encoding="utf-8"))
    assert calls == ["review"]
    assert result.review_completed is True
    assert status["stages"]["review"] == "completed"
    assert any("已复用，打开此前审核结果" in message for message in messages)


@pytest.mark.parametrize(
    ("subtitles_burned_in", "srt_text"),
    [
        (True, ""),
        (False, "1\n00:00:00,000 --> 00:00:01,000\n合成字幕\n"),
    ],
)
def test_inconsistent_completed_subtitle_state_is_not_reused_or_deleted(
    tmp_path: Path,
    subtitles_burned_in: bool,
    srt_text: str,
) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    workdir = tmp_path / "work"
    timeline_path = write_timeline(video, workdir)
    analysis_path = write_analysis(workdir)
    output = workdir / "exports"
    output.mkdir()
    video_output = output / "source_candidate-001.mp4"
    subtitle_output = output / "source_candidate-001.srt"
    video_output.write_bytes(b"video")
    subtitle_output.write_text(srt_text, encoding="utf-8", newline="\n")
    review = {
        "schema_version": "1.0",
        "source": {
            "analysis_file_name": analysis_path.name,
            "analysis_sha256": hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
            "timeline_file_name": timeline_path.name,
            "timeline_sha256": hashlib.sha256(timeline_path.read_bytes()).hexdigest(),
            "video_file_name": video.name,
        },
        "review": {
            "candidate_id": "candidate-001",
            "approved": True,
            "original_start_ms": 0,
            "original_end_ms": 30_000,
            "final_start_ms": 1_000,
            "final_end_ms": 29_000,
            "reviewed_at": "2026-08-11T00:00:00Z",
        },
        "export": {
            "video_file_name": video_output.name,
            "subtitle_file_name": subtitle_output.name,
            "completed": True,
            "subtitles_burned_in": subtitles_burned_in,
        },
    }
    review_path = workdir / "review_current.json"
    atomic_write_json(review_path, review)
    before = {
        review_path: review_path.read_bytes(),
        video_output: video_output.read_bytes(),
        subtitle_output: subtitle_output.read_bytes(),
    }
    calls: list[str] = []
    messages: list[str] = []

    result = run_pipeline(
        video,
        workdir=workdir,
        review_function=lambda *_a, **_k: calls.append("review"),
        progress=messages.append,
        **dependencies(tmp_path),
    )

    status = json.loads((workdir / "pipeline_status.json").read_text(encoding="utf-8"))
    assert calls == ["review"]
    assert result.review_completed is False
    assert status["stages"]["review"] == "pending"
    assert any("人工审核与导出：开始" in message for message in messages)
    assert {path: path.read_bytes() for path in before} == before


def test_windows_launcher_is_native_bounded_and_cancel_safe() -> None:
    root = Path(__file__).resolve().parents[1]
    command = (root / "Start-LiveClip.cmd").read_text(encoding="utf-8")
    launcher = (root / "tools" / "windows" / "Start-LiveClip.ps1").read_text(
        encoding="utf-8"
    )
    assert "%~dp0tools\\windows\\Start-LiveClip.ps1" in command
    assert 'if not "%LIVECLIP_EXIT_CODE%"=="0"' in command
    assert "OpenFileDialog" in launcher
    assert "MP4 video (*.mp4)|*.mp4" in launcher
    assert "DialogResult]::OK" in launcher
    assert "No video selected. LiveClip exited normally." in launcher
    assert "exit 0" in launcher
    assert "PromptForChoice" in launcher
    assert "Paraformer (recommended)" in launcher
    assert "SenseVoice (low resource)" in launcher
    assert "-m liveclip run --video $videoPath --asr-model $asrModel" in launcher
    assert "LIVECLIP_ASSETS_ROOT" in launcher
    assert ".venv\\Scripts\\python.exe" in launcher
    assert "Start-Process" not in launcher
    assert "RunAs" not in launcher

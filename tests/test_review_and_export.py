from __future__ import annotations

import hashlib
import http.client
import json
import threading
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import pytest

from liveclip.cli import build_parser, main
from liveclip.media import FFmpegPaths, MediaProbe, StreamInfo
from liveclip.media.errors import (
    ProcessExecutionError,
    ProcessFailure,
)
from liveclip.media.process_runner import decode_process_output
from liveclip.review.exporter import ExportResult, export_review_clip, render_timeline_srt
from liveclip.review.schema import (
    CompletedExport,
    MAX_CLIP_DURATION_MS,
    ReviewConflictError,
    ReviewError,
    ReviewInputs,
    bind_review_inputs,
    build_session_payload,
    load_completed_export,
    validate_clip_range,
)
from liveclip.review import server as server_module
from liveclip.review.server import STATIC_ROOT, create_review_server


TOKEN = "test-token-0123456789abcdef"


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _fake_paths(tmp_path: Path) -> FFmpegPaths:
    return FFmpegPaths(tmp_path / "fake-ffmpeg.exe", tmp_path / "fake-ffprobe.exe")


class FakeFFprobe:
    def __init__(
        self,
        source: Path,
        *,
        source_duration_ms: int = 30_000,
        output_duration_ms: int = 18_500,
        output_valid: bool = True,
        fail_output: bool = False,
        has_audio: bool = True,
    ) -> None:
        self.source = source.resolve()
        self.source_duration_ms = source_duration_ms
        self.output_duration_ms = output_duration_ms
        self.output_valid = output_valid
        self.fail_output = fail_output
        self.has_audio = has_audio
        self.calls: list[Path] = []

    def __call__(self, path: Path, **_: Any) -> MediaProbe:
        resolved = Path(path).resolve()
        self.calls.append(resolved)
        is_source = resolved == self.source
        if not is_source and self.fail_output:
            raise RuntimeError("fake ffprobe failure")
        duration_ms = self.source_duration_ms if is_source else self.output_duration_ms
        video_codec = "h264" if is_source or self.output_valid else "vp9"
        audio_codec = "aac" if is_source or self.output_valid else "opus"
        audio = (
            (StreamInfo(1, "audio", audio_codec, sample_rate=48_000, channels=2),)
            if (self.has_audio or not is_source)
            else ()
        )
        return MediaProbe(
            path=resolved,
            container_format="mov,mp4,m4a,3gp,3g2,mj2",
            duration_seconds=duration_ms / 1000,
            file_size_bytes=resolved.stat().st_size if resolved.is_file() else 0,
            video_streams=(StreamInfo(0, "video", video_codec, width=1280, height=720),),
            audio_streams=audio,
        )


class FakeFFmpeg:
    def __init__(self, *, fail: bool = False, mutate_source: Path | None = None) -> None:
        self.fail = fail
        self.mutate_source = mutate_source
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, executable: Path, arguments: tuple[Any, ...], **_: Any) -> Any:
        command = (str(executable), *(str(item) for item in arguments))
        self.calls.append(command)
        if self.fail:
            failure = ProcessFailure(
                command=command,
                returncode=1,
                stdout_details=decode_process_output(b""),
                stderr_details=decode_process_output(b"fake failure"),
                timed_out=False,
                timeout_seconds=30.0,
            )
            raise ProcessExecutionError("fake FFmpeg failed", failure)
        output = Path(arguments[-1])
        output.write_bytes(b"fake-h264-aac-mp4")
        if self.mutate_source is not None:
            self.mutate_source.write_bytes(b"changed-during-export")
        return SimpleNamespace(elapsed_seconds=0.42)


def make_review_inputs(
    tmp_path: Path,
    *,
    candidates: bool = True,
    analysis_completed: bool = True,
    timeline_sha_override: str | None = None,
    video_sha_override: str | None = None,
    duration_ms: int = 30_000,
    candidate_id: str = "clip-001",
    has_audio: bool = True,
) -> tuple[ReviewInputs, FakeFFprobe, FFmpegPaths]:
    source = tmp_path / "真实 直播.mp4"
    source.write_bytes(bytes(range(256)) * 8)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    timeline = {
        "schema_version": "1.0",
        "source": {
            "file_name": source.name,
            "duration_ms": duration_ms,
            "sha256": video_sha_override or source_sha,
        },
        "asr": {"engine": "sensevoice", "language": "zh", "completed": True},
        "segments": [
            {"id": 1, "start_ms": 0, "end_ms": 3_000, "text_raw": "开场", "text": "开场", "speaker": None, "is_question": False, "is_uncertain": False},
            {"id": 2, "start_ms": 3_000, "end_ms": 9_000, "text_raw": "第一条", "text": "第一条", "speaker": None, "is_question": False, "is_uncertain": False},
            {"id": 3, "start_ms": 9_000, "end_ms": 16_000, "text_raw": "第二条", "text": "第二条", "speaker": None, "is_question": False, "is_uncertain": False},
            {"id": 4, "start_ms": 16_000, "end_ms": 23_000, "text_raw": "收尾", "text": "收尾", "speaker": None, "is_question": False, "is_uncertain": False},
            {"id": 5, "start_ms": 25_000, "end_ms": 29_000, "text_raw": "尾声", "text": "尾声", "speaker": None, "is_question": False, "is_uncertain": False},
        ],
    }
    timeline_path = tmp_path / "timeline.json"
    timeline_raw = _json_bytes(timeline)
    timeline_path.write_bytes(timeline_raw)
    timeline_sha = hashlib.sha256(timeline_raw).hexdigest()
    topics = [
        {
            "id": "topic-001",
            "start_segment_id": 1,
            "end_segment_id": 4,
            "start_ms": 0,
            "end_ms": 23_000,
            "title": "测试主题",
            "summary": "合成摘要",
        }
    ] if candidates else []
    candidate_items = [
        {
            "id": candidate_id,
            "topic_id": "topic-001",
            "start_segment_id": 2,
            "end_segment_id": 4,
            "start_ms": 3_000,
            "end_ms": 23_000,
            "duration_ms": 20_000,
            "title": "合成候选",
            "reason": "范围完整，适合人工预览。",
            "quote_segment_id": 3,
            "quote": "第二条",
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
    ] if candidates else []
    analysis = {
        "schema_version": "1.0",
        "source": {
            "timeline_file_name": timeline_path.name,
            "timeline_sha256": timeline_sha_override or timeline_sha,
            "video_file_name": source.name,
            "duration_ms": duration_ms,
        },
        "analysis": {
            "provider": "openai_compatible",
            "model": "fake-model",
            "completed": analysis_completed,
            "generated_at": "2026-07-31T00:00:00Z",
            "window_count": 1 if candidates else 0,
        },
        "topics": topics,
        "candidates": candidate_items,
    }
    analysis_path = tmp_path / "current_analysis.json"
    analysis_path.write_bytes(_json_bytes(analysis))
    paths = _fake_paths(tmp_path)
    fake_probe = FakeFFprobe(
        source,
        source_duration_ms=duration_ms,
        has_audio=has_audio,
    )
    inputs = bind_review_inputs(
        source,
        timeline_path,
        analysis_path,
        paths=paths,
        probe_function=fake_probe,
    )
    return inputs, fake_probe, paths


@contextmanager
def running_server(inputs: ReviewInputs, **kwargs: Any) -> Iterator[Any]:
    server = create_review_server(inputs, token=TOKEN, **kwargs)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def request(
    server: Any,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection(*server.server_address, timeout=5)
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = dict(headers or {})
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        request_headers["Content-Length"] = str(len(payload))
    connection.request(method, path, body=payload, headers=request_headers)
    response = connection.getresponse()
    data = response.read()
    result_headers = {name.lower(): value for name, value in response.getheaders()}
    connection.close()
    return response.status, result_headers, data


def test_review_parser_requires_three_inputs() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "review",
        "--video", "source.mp4",
        "--timeline", "timeline.json",
        "--analysis", "current_analysis.json",
    ])
    assert args.command == "review"
    assert args.output is None


def test_valid_video_timeline_analysis_binding_and_default_output(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    assert inputs.video_duration_ms == 30_000
    assert inputs.output_dir == tmp_path / "真实 直播_exports"
    assert inputs.review_path == tmp_path / "review_current.json"
    assert inputs.analysis_sha256 == hashlib.sha256(inputs.analysis_path.read_bytes()).hexdigest()


def test_timeline_sha_mismatch_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="timeline SHA-256"):
        make_review_inputs(tmp_path, timeline_sha_override="0" * 64)


def test_video_sha_mismatch_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="原视频 SHA-256"):
        make_review_inputs(tmp_path, video_sha_override="0" * 64)


def test_incomplete_analysis_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="全部窗口完成"):
        make_review_inputs(tmp_path, analysis_completed=False)


def test_unsafe_candidate_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="candidate ID"):
        make_review_inputs(tmp_path, candidate_id="../escape")


def test_no_candidates_is_a_valid_pending_session(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path, candidates=False)
    payload = build_session_payload(inputs)
    assert payload["candidates"] == []
    assert payload["export_completed"] is False
    assert payload["completed_export"] is None


def test_candidate_list_fields_and_default_pending_status(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    candidate = build_session_payload(inputs)["candidates"][0]
    assert set(candidate) == {
        "id", "rank", "title", "total_score", "duration_ms", "reason", "risk",
        "review_status", "original_start_ms", "original_end_ms",
    }
    assert candidate["review_status"] == "待审核"
    assert "approved" not in candidate


@pytest.mark.parametrize(
    ("start_ms", "end_ms", "valid"),
    [
        (0, 1_000, True),
        (0, MAX_CLIP_DURATION_MS, True),
        (-1, 1_000, False),
        (0, 999, False),
        (10_000, 10_000, False),
        (0, MAX_CLIP_DURATION_MS + 1, False),
        (0, 30_001, False),
        (True, 2_000, False),
        (0.0, 2_000, False),
    ],
)
def test_clip_range_boundaries(start_ms: Any, end_ms: Any, valid: bool) -> None:
    if valid:
        validate_clip_range(start_ms, end_ms, max(30_000, end_ms))
    else:
        with pytest.raises(ReviewError):
            validate_clip_range(start_ms, end_ms, 30_000)


def test_timeline_segments_are_cropped_shifted_and_numbered(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    srt, count = render_timeline_srt(inputs.timeline, 5_000, 18_000)
    assert count == 3
    assert "1\n00:00:00,000 --> 00:00:04,000\n第一条" in srt
    assert "2\n00:00:04,000 --> 00:00:11,000\n第二条" in srt
    assert "3\n00:00:11,000 --> 00:00:13,000\n收尾" in srt
    assert srt.count("-->") == 3


def test_empty_timeline_range_produces_legal_empty_srt(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    assert render_timeline_srt(inputs.timeline, 23_000, 24_000) == ("", 0)


def test_export_requires_explicit_confirmation(tmp_path: Path) -> None:
    inputs, fake_probe, paths = make_review_inputs(tmp_path)
    with pytest.raises(ReviewError, match="必须先勾选"):
        export_review_clip(
            inputs,
            candidate_id="clip-001",
            start_ms=4_000,
            end_ms=22_500,
            confirmed=False,
            paths=paths,
            process_function=FakeFFmpeg(),
            probe_function=fake_probe,
        )
    assert not inputs.review_path.exists()


def test_fake_ffmpeg_ffprobe_success_publishes_mp4_srt_and_review(tmp_path: Path) -> None:
    inputs, fake_probe, paths = make_review_inputs(tmp_path)
    source_before = inputs.video_path.read_bytes()
    timeline_before = inputs.timeline_path.read_bytes()
    analysis_before = inputs.analysis_path.read_bytes()
    fake_ffmpeg = FakeFFmpeg()
    result = export_review_clip(
        inputs,
        candidate_id="clip-001",
        start_ms=4_000,
        end_ms=22_500,
        confirmed=True,
        paths=paths,
        process_function=fake_ffmpeg,
        probe_function=fake_probe,
        now_function=lambda: datetime(2026, 7, 31, 8, 9, 10, tzinfo=timezone.utc),
    )
    assert result.video_path.name == "真实 直播_clip-001.mp4"
    assert result.subtitle_path.name == "真实 直播_clip-001.srt"
    assert result.video_path.read_bytes() == b"fake-h264-aac-mp4"
    assert result.subtitle_count == 3
    command = fake_ffmpeg.calls[0]
    assert ("-c:v", "libx264") == (command[command.index("-c:v")], command[command.index("-c:v") + 1])
    assert command[command.index("-crf") + 1] == "20"
    assert command[command.index("-c:a") + 1] == "aac"
    assert command[command.index("-b:a") + 1] == "160k"
    assert command[command.index("-movflags") + 1] == "+faststart"
    review = json.loads(inputs.review_path.read_text(encoding="utf-8"))
    assert review["review"] == {
        "candidate_id": "clip-001",
        "approved": True,
        "original_start_ms": 3_000,
        "original_end_ms": 23_000,
        "final_start_ms": 4_000,
        "final_end_ms": 22_500,
        "reviewed_at": "2026-07-31T08:09:10Z",
    }
    assert review["source"]["timeline_sha256"] == inputs.timeline_sha256
    assert review["source"]["analysis_sha256"] == inputs.analysis_sha256
    assert review["export"]["completed"] is True
    assert inputs.video_path.read_bytes() == source_before
    assert inputs.timeline_path.read_bytes() == timeline_before
    assert inputs.analysis_path.read_bytes() == analysis_before


def test_no_audio_source_uses_local_silence_and_still_requests_aac(tmp_path: Path) -> None:
    inputs, fake_probe, paths = make_review_inputs(tmp_path, has_audio=False)
    fake_ffmpeg = FakeFFmpeg()
    export_review_clip(
        inputs,
        candidate_id="clip-001",
        start_ms=4_000,
        end_ms=22_500,
        confirmed=True,
        paths=paths,
        process_function=fake_ffmpeg,
        probe_function=fake_probe,
    )
    command = fake_ffmpeg.calls[0]
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in command
    assert command[command.index("-c:a") + 1] == "aac"


def test_existing_output_files_are_never_overwritten(tmp_path: Path) -> None:
    inputs, fake_probe, paths = make_review_inputs(tmp_path)
    inputs.output_dir.mkdir()
    existing = inputs.output_dir / "真实 直播_clip-001.mp4"
    existing.write_bytes(b"user-file")
    with pytest.raises(ReviewConflictError, match="同名输出"):
        export_review_clip(
            inputs,
            candidate_id="clip-001",
            start_ms=4_000,
            end_ms=22_500,
            confirmed=True,
            paths=paths,
            process_function=FakeFFmpeg(),
            probe_function=fake_probe,
        )
    assert existing.read_bytes() == b"user-file"


def test_fake_ffmpeg_failure_publishes_nothing_and_preserves_old_review(tmp_path: Path) -> None:
    inputs, fake_probe, paths = make_review_inputs(tmp_path)
    inputs.review_path.write_bytes(b"old-review")
    with pytest.raises(ReviewError, match="FFmpeg 导出失败"):
        export_review_clip(
            inputs,
            candidate_id="clip-001",
            start_ms=4_000,
            end_ms=22_500,
            confirmed=True,
            paths=paths,
            process_function=FakeFFmpeg(fail=True),
            probe_function=fake_probe,
        )
    assert inputs.review_path.read_bytes() == b"old-review"
    assert list(inputs.output_dir.glob("*")) == []


def test_fake_ffprobe_failure_publishes_nothing_and_preserves_old_review(tmp_path: Path) -> None:
    inputs, _, paths = make_review_inputs(tmp_path)
    inputs.review_path.write_bytes(b"old-review")
    failing_probe = FakeFFprobe(inputs.video_path, fail_output=True)
    with pytest.raises(ReviewError, match="ffprobe"):
        export_review_clip(
            inputs,
            candidate_id="clip-001",
            start_ms=4_000,
            end_ms=22_500,
            confirmed=True,
            paths=paths,
            process_function=FakeFFmpeg(),
            probe_function=failing_probe,
        )
    assert inputs.review_path.read_bytes() == b"old-review"
    assert list(inputs.output_dir.glob("*")) == []


def test_invalid_export_codec_is_not_published(tmp_path: Path) -> None:
    inputs, _, paths = make_review_inputs(tmp_path)
    bad_probe = FakeFFprobe(inputs.video_path, output_valid=False)
    with pytest.raises(ReviewError, match="流格式"):
        export_review_clip(
            inputs,
            candidate_id="clip-001",
            start_ms=4_000,
            end_ms=22_500,
            confirmed=True,
            paths=paths,
            process_function=FakeFFmpeg(),
            probe_function=bad_probe,
        )
    assert not inputs.review_path.exists()


def test_source_change_during_export_blocks_publication(tmp_path: Path) -> None:
    inputs, fake_probe, paths = make_review_inputs(tmp_path)
    with pytest.raises(ReviewError, match="原视频在导出期间发生变化"):
        export_review_clip(
            inputs,
            candidate_id="clip-001",
            start_ms=4_000,
            end_ms=22_500,
            confirmed=True,
            paths=paths,
            process_function=FakeFFmpeg(mutate_source=inputs.video_path),
            probe_function=fake_probe,
        )
    assert not inputs.review_path.exists()


def test_server_binds_only_ipv4_localhost(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    server = create_review_server(inputs, token=TOKEN)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


def test_page_and_analysis_api_require_runtime_token(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    with running_server(inputs) as server:
        assert request(server, "GET", "/")[0] == 403
        assert request(server, "GET", "/?token=wrong-token-000000")[0] == 403
        assert request(server, "GET", "/?token=%E9%94%99%E8%AF%AF")[0] == 403
        status, headers, body = request(server, "GET", f"/?token={TOKEN}")
        assert status == 200
        assert headers["content-security-policy"].startswith("default-src 'self'")
        assert "候选审核与单片段导出" in body.decode("utf-8")
        status, _, body = request(server, "GET", f"/api/session?token={TOKEN}")
        assert status == 200
        assert json.loads(body)["candidates"][0]["review_status"] == "待审核"


def test_browser_range_playback_requests_are_supported(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    source_bytes = inputs.video_path.read_bytes()
    with running_server(inputs) as server:
        status, headers, body = request(
            server,
            "GET",
            f"/media?token={TOKEN}",
            headers={"Range": "bytes=10-29"},
        )
        assert status == 206
        assert headers["accept-ranges"] == "bytes"
        assert headers["content-range"] == f"bytes 10-29/{len(source_bytes)}"
        assert body == source_bytes[10:30]
        status, _, body = request(
            server,
            "GET",
            f"/media?token={TOKEN}",
            headers={"Range": "bytes=-16"},
        )
        assert status == 206
        assert body == source_bytes[-16:]


def test_invalid_range_and_path_traversal_are_rejected(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    with running_server(inputs) as server:
        status, headers, _ = request(
            server,
            "GET",
            f"/media?token={TOKEN}",
            headers={"Range": "bytes=999999-"},
        )
        assert status == 416
        assert headers["content-range"].startswith("bytes */")
        status, _, body = request(server, "GET", f"/%2e%2e/secret?token={TOKEN}")
        assert status == 400
        assert "路径穿越" in body.decode("utf-8")
        assert request(server, "GET", f"/media?token={TOKEN}&path=C:%5Csecret.mp4")[0] == 403


def test_unconfirmed_export_api_is_rejected(tmp_path: Path) -> None:
    inputs, fake_probe, paths = make_review_inputs(tmp_path)
    exporter = lambda bound, **kwargs: export_review_clip(
        bound,
        process_function=FakeFFmpeg(),
        probe_function=fake_probe,
        **kwargs,
    )
    with running_server(inputs, exporter=exporter, paths=paths) as server:
        status, _, body = request(
            server,
            "POST",
            f"/api/export?token={TOKEN}",
            body={"candidate_id": "clip-001", "start_ms": 4_000, "end_ms": 22_500, "confirmed": False},
        )
        assert status == 400
        assert "必须先勾选" in body.decode("utf-8")
        assert not inputs.review_path.exists()


def test_successful_export_api_allows_only_one_session_export(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    calls: list[dict[str, Any]] = []

    def fake_exporter(bound: ReviewInputs, **kwargs: Any) -> ExportResult:
        calls.append(kwargs)
        return ExportResult(
            bound.output_dir / "one.mp4",
            bound.output_dir / "one.srt",
            bound.review_path,
            2,
            kwargs["end_ms"] - kwargs["start_ms"],
            0.1,
        )

    payload = {"candidate_id": "clip-001", "start_ms": 4_000, "end_ms": 22_500, "confirmed": True}
    with running_server(inputs, exporter=fake_exporter) as server:
        status, _, first_body = request(server, "POST", f"/api/export?token={TOKEN}", body=payload)
        assert status == 200
        response = json.loads(first_body)
        assert response["video_file_name"] == "one.mp4"
        assert response["subtitle_file_name"] == "one.srt"
        assert response["final_start_ms"] == 4_000
        assert response["final_end_ms"] == 22_500
        assert response["output_folder_name"] == inputs.output_dir.name
        status, _, body = request(server, "POST", f"/api/export?token={TOKEN}", body=payload)
        assert status == 409
        assert "已经完成一次导出" in body.decode("utf-8")
        assert len(calls) == 1


def test_static_page_is_local_framework_free_and_defaults_unconfirmed() -> None:
    html = (STATIC_ROOT / "review.html").read_text(encoding="utf-8")
    css = (STATIC_ROOT / "review.css").read_text(encoding="utf-8")
    javascript = (STATIC_ROOT / "review.js").read_text(encoding="utf-8")
    combined = "\n".join((html, css, javascript)).lower()
    assert "http://" not in combined and "https://" not in combined
    assert "react" not in combined and "vue" not in combined and "cdn" not in combined
    assert '<video id="video" controls' in html
    assert 'type="range"' in html and 'type="number"' in html
    assert 'id="confirmExport" type="checkbox" disabled' in html
    assert 'id="exportButton" type="button" class="export-button" disabled' in html
    assert "恢复AI推荐范围" in html
    assert "original_start_ms" in javascript and "original_end_ms" in javascript
    assert 'addEventListener("pagehide", requestShutdown)' in javascript
    assert "keepalive: true" in javascript
    assert 'localUrl("/api/heartbeat")' in javascript
    assert "elements.confirmExport.checked = false" in javascript
    assert "final_start_ms" in javascript and "final_end_ms" in javascript
    assert "video_file_name" in javascript and "subtitle_file_name" in javascript
    assert "output_folder_name" in javascript


def test_existing_completed_review_is_displayed_without_absolute_paths(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    inputs.output_dir.mkdir()
    video_name = "真实 直播_clip-001.mp4"
    subtitle_name = "真实 直播_clip-001.srt"
    (inputs.output_dir / video_name).write_bytes(b"video")
    (inputs.output_dir / subtitle_name).write_text("", encoding="utf-8")
    payload = {
        "schema_version": "1.0",
        "source": {
            "analysis_file_name": inputs.analysis_path.name,
            "analysis_sha256": inputs.analysis_sha256,
            "timeline_file_name": inputs.timeline_path.name,
            "timeline_sha256": inputs.timeline_sha256,
            "video_file_name": inputs.video_path.name,
        },
        "review": {
            "candidate_id": "clip-001",
            "approved": True,
            "original_start_ms": 3_000,
            "original_end_ms": 23_000,
            "final_start_ms": 4_000,
            "final_end_ms": 22_500,
            "reviewed_at": "2026-08-05T00:00:00Z",
        },
        "export": {
            "video_file_name": video_name,
            "subtitle_file_name": subtitle_name,
            "completed": True,
        },
    }
    inputs.review_path.write_bytes(_json_bytes(payload))
    completed = load_completed_export(inputs)
    assert completed == CompletedExport(
        candidate_id="clip-001",
        video_file_name=video_name,
        subtitle_file_name=subtitle_name,
        final_start_ms=4_000,
        final_end_ms=22_500,
        duration_ms=18_500,
        output_folder_name=inputs.output_dir.name,
    )
    session = build_session_payload(inputs, completed_export=completed)
    assert session["export_completed"] is True
    assert session["completed_export"]["output_folder_name"] == inputs.output_dir.name
    assert str(inputs.output_dir) not in json.dumps(session, ensure_ascii=False)


def test_heartbeat_timeout_stops_server_after_hard_page_close(tmp_path: Path) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    server = create_review_server(
        inputs,
        token=TOKEN,
        heartbeat_timeout_seconds=0.2,
        heartbeat_check_seconds=0.05,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    thread.join(timeout=2)
    try:
        assert not thread.is_alive()
    finally:
        server.server_close()


def test_launch_starts_local_service_before_opening_browser(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    opened_urls: list[str] = []

    monkeypatch.setattr(server_module, "bind_review_inputs", lambda *args, **kwargs: inputs)

    def open_and_stop(url: str, **_: Any) -> bool:
        opened_urls.append(url)
        with urllib.request.urlopen(url, timeout=3) as response:
            assert response.status == 200
        shutdown_url = url.replace("/?token=", "/api/shutdown?token=")
        request = urllib.request.Request(shutdown_url, method="POST")
        with urllib.request.urlopen(request, timeout=3) as response:
            assert response.status == 202
        return True

    monkeypatch.setattr(server_module.webbrowser, "open", open_and_stop)
    server_module.launch_review("video.mp4", "timeline.json", "analysis.json")
    assert len(opened_urls) == 1
    assert opened_urls[0].startswith("http://127.0.0.1:")


def test_no_open_browser_allows_time_to_copy_local_url(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    inputs, _, _ = make_review_inputs(tmp_path)
    captured: dict[str, Any] = {}
    fake_server = SimpleNamespace(
        server_address=("127.0.0.1", 12345),
        app=SimpleNamespace(token=TOKEN),
        serve_forever=lambda: None,
        shutdown=lambda: None,
        server_close=lambda: None,
    )
    monkeypatch.setattr(server_module, "bind_review_inputs", lambda *args, **kwargs: inputs)

    def create(*_args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return fake_server

    monkeypatch.setattr(server_module, "create_review_server", create)
    monkeypatch.setattr(
        server_module.webbrowser,
        "open",
        lambda *_args, **_kwargs: pytest.fail("browser must not open"),
    )
    server_module.launch_review(
        "video.mp4",
        "timeline.json",
        "analysis.json",
        open_browser=False,
    )
    assert captured["heartbeat_timeout_seconds"] == 60.0


def test_cli_input_error_is_one_line_without_traceback_or_absolute_path(capsys: Any) -> None:
    missing = "definitely-missing.mp4"
    exit_code = main([
        "review",
        "--video", missing,
        "--timeline", "timeline.json",
        "--analysis", "current_analysis.json",
    ])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.count("\n") == 1
    assert "Traceback" not in captured.err
    assert str(Path(missing).resolve()) not in captured.err


def test_task_006_adds_only_the_bounded_run_command() -> None:
    parser = build_parser()
    choices = parser._subparsers._group_actions[0].choices  # type: ignore[union-attr]
    assert "TASK-007" not in choices
    assert set(choices) == {"transcribe", "analyze", "review", "run"}

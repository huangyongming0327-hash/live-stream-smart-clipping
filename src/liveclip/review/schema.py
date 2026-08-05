"""Input binding and server-authoritative review validation."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from liveclip.analysis.schema import validate_analysis
from liveclip.asr.timeline import validate_timeline
from liveclip.media import FFmpegPaths, MediaProbe, probe_media, resolve_ffmpeg_paths


MAX_DURATION_MISMATCH_MS = 1_000
MIN_CLIP_DURATION_MS = 1_000
MAX_CLIP_DURATION_MS = 180_000
SAFE_CANDIDATE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")


class ReviewError(RuntimeError):
    """A review failure that is safe to show without a traceback or local path."""


class ReviewConflictError(ReviewError):
    """A review request conflicts with an existing user file or completed export."""


@dataclass(frozen=True, slots=True)
class ReviewInputs:
    """One validated video/timeline/analysis binding for one review session."""

    video_path: Path
    timeline_path: Path
    analysis_path: Path
    output_dir: Path
    review_path: Path
    video_duration_ms: int
    video_height: int
    video_sha256: str
    timeline_sha256: str
    analysis_sha256: str
    timeline: dict[str, Any]
    analysis: dict[str, Any]
    has_audio: bool


@dataclass(frozen=True, slots=True)
class CompletedExport:
    """Display-safe details from one valid completed review."""

    candidate_id: str
    video_file_name: str
    subtitle_file_name: str
    final_start_ms: int
    final_end_ms: int
    duration_ms: int
    output_folder_name: str
    subtitles_burned_in: bool


ProbeFunction = Callable[..., MediaProbe]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    if not path.is_file():
        raise ReviewError(f"{label}不存在或不是文件。")
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ReviewError(f"{label}无法读取或 JSON 已损坏。") from None
    if not isinstance(payload, dict):
        raise ReviewError(f"{label}顶层必须是 JSON 对象。")
    return payload, raw


def _resolve_tools(paths: FFmpegPaths | None) -> FFmpegPaths:
    if paths is not None:
        return paths
    try:
        return resolve_ffmpeg_paths()
    except Exception:
        raise ReviewError("项目本地 FFmpeg/ffprobe 不可用。") from None


def bind_review_inputs(
    video: str | Path,
    timeline: str | Path,
    analysis: str | Path,
    *,
    output_dir: str | Path | None = None,
    paths: FFmpegPaths | None = None,
    probe_function: ProbeFunction = probe_media,
) -> ReviewInputs:
    """Validate and bind exactly one source video, timeline, and analysis."""

    video_path = Path(video).expanduser().resolve()
    timeline_path = Path(timeline).expanduser().resolve()
    analysis_path = Path(analysis).expanduser().resolve()
    if not video_path.is_file():
        raise ReviewError("原视频不存在或不是文件。")
    if video_path.suffix.lower() != ".mp4":
        raise ReviewError("原视频必须是 .mp4 文件。")
    if timeline_path.suffix.lower() != ".json":
        raise ReviewError("timeline 必须是 JSON 文件。")
    if analysis_path.suffix.lower() != ".json":
        raise ReviewError("analysis 必须是 JSON 文件。")

    resolved_paths = _resolve_tools(paths)
    try:
        video_probe = probe_function(
            video_path,
            paths=resolved_paths,
            require_audio=False,
            timeout_seconds=30.0,
        )
    except Exception:
        raise ReviewError("原视频无法通过 ffprobe 读取。") from None
    if (
        not video_probe.video_streams
        or not math.isfinite(video_probe.duration_seconds)
        or video_probe.duration_seconds <= 0
    ):
        raise ReviewError("原视频必须包含可读取的视频流和有效时长。")
    video_height = video_probe.video_streams[0].height
    if (
        isinstance(video_height, bool)
        or not isinstance(video_height, int)
        or video_height <= 0
    ):
        raise ReviewError("原视频必须包含可读取的视频高度。")
    video_duration_ms = int(round(video_probe.duration_seconds * 1000))

    timeline_data, timeline_raw = _read_json(timeline_path, "timeline")
    try:
        validate_timeline(timeline_data)
    except ValueError as exc:
        raise ReviewError(f"timeline 校验失败：{exc}") from None

    try:
        video_sha256 = sha256_file(video_path)
    except OSError:
        raise ReviewError("原视频无法读取。") from None
    if timeline_data["source"]["file_name"] != video_path.name:
        raise ReviewError("timeline 与所选原视频文件名不匹配。")
    if timeline_data["source"]["sha256"] != video_sha256:
        raise ReviewError("timeline 与所选原视频 SHA-256 不匹配。")
    if (
        abs(timeline_data["source"]["duration_ms"] - video_duration_ms)
        > MAX_DURATION_MISMATCH_MS
    ):
        raise ReviewError("timeline 时长与原视频时长不匹配。")

    analysis_data, analysis_raw = _read_json(analysis_path, "analysis")
    try:
        validate_analysis(analysis_data, timeline=timeline_data)
    except Exception as exc:
        raise ReviewError(f"analysis 校验失败：{exc}") from None
    timeline_sha256 = hashlib.sha256(timeline_raw).hexdigest()
    if analysis_data["source"]["timeline_sha256"] != timeline_sha256:
        raise ReviewError("analysis 引用的 timeline SHA-256 与当前文件不匹配。")

    for candidate in analysis_data["candidates"]:
        candidate_id = candidate["id"]
        if SAFE_CANDIDATE_ID.fullmatch(candidate_id) is None:
            raise ReviewError("analysis 包含不安全的 candidate ID。")
        validate_clip_range(
            candidate["start_ms"],
            candidate["end_ms"],
            video_duration_ms,
        )

    selected_output = (
        Path(output_dir).expanduser().resolve()
        if output_dir is not None
        else video_path.with_name(f"{video_path.stem}_exports").resolve()
    )
    if selected_output.exists() and not selected_output.is_dir():
        raise ReviewError("输出位置已存在且不是目录。")

    return ReviewInputs(
        video_path=video_path,
        timeline_path=timeline_path,
        analysis_path=analysis_path,
        output_dir=selected_output,
        review_path=analysis_path.with_name("review_current.json"),
        video_duration_ms=video_duration_ms,
        video_height=video_height,
        video_sha256=video_sha256,
        timeline_sha256=timeline_sha256,
        analysis_sha256=hashlib.sha256(analysis_raw).hexdigest(),
        timeline=timeline_data,
        analysis=analysis_data,
        has_audio=bool(video_probe.audio_streams),
    )


def validate_clip_range(start_ms: Any, end_ms: Any, video_duration_ms: int) -> None:
    if (
        isinstance(start_ms, bool)
        or isinstance(end_ms, bool)
        or not isinstance(start_ms, int)
        or not isinstance(end_ms, int)
    ):
        raise ReviewError("开始和结束时间必须是整数毫秒。")
    if start_ms < 0 or end_ms > video_duration_ms or end_ms <= start_ms:
        raise ReviewError("时间范围必须满足 0 <= start < end <= 视频时长。")
    duration_ms = end_ms - start_ms
    if not MIN_CLIP_DURATION_MS <= duration_ms <= MAX_CLIP_DURATION_MS:
        raise ReviewError("调整后的片段时长必须为 1—180 秒。")


def find_candidate(inputs: ReviewInputs, candidate_id: Any) -> dict[str, Any]:
    if not isinstance(candidate_id, str):
        raise ReviewError("candidate_id 无效。")
    for candidate in inputs.analysis["candidates"]:
        if candidate["id"] == candidate_id:
            return candidate
    raise ReviewError("所选候选不存在。")


def load_completed_export(inputs: ReviewInputs) -> CompletedExport | None:
    """Return a matching completed export without trusting arbitrary paths."""

    if not inputs.review_path.is_file():
        return None
    try:
        payload = json.loads(inputs.review_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != "1.0":
            return None
        source = payload["source"]
        review = payload["review"]
        export = payload["export"]
        if (
            not isinstance(source, dict)
            or not isinstance(review, dict)
            or not isinstance(export, dict)
            or source.get("video_file_name") != inputs.video_path.name
            or source.get("timeline_file_name") != inputs.timeline_path.name
            or source.get("timeline_sha256") != inputs.timeline_sha256
            or source.get("analysis_file_name") != inputs.analysis_path.name
            or source.get("analysis_sha256") != inputs.analysis_sha256
            or review.get("approved") is not True
            or export.get("completed") is not True
        ):
            return None
        candidate = find_candidate(inputs, review.get("candidate_id"))
        start_ms = review.get("final_start_ms")
        end_ms = review.get("final_end_ms")
        validate_clip_range(start_ms, end_ms, inputs.video_duration_ms)
        if (
            review.get("original_start_ms") != candidate["start_ms"]
            or review.get("original_end_ms") != candidate["end_ms"]
        ):
            return None
        video_name = export.get("video_file_name")
        subtitle_name = export.get("subtitle_file_name")
        subtitles_burned_in = export.get("subtitles_burned_in")
        if (
            not isinstance(video_name, str)
            or not video_name
            or Path(video_name).name != video_name
            or not isinstance(subtitle_name, str)
            or not subtitle_name
            or Path(subtitle_name).name != subtitle_name
            or not isinstance(subtitles_burned_in, bool)
            or not (inputs.output_dir / video_name).is_file()
            or not (inputs.output_dir / subtitle_name).is_file()
        ):
            return None
        return CompletedExport(
            candidate_id=candidate["id"],
            video_file_name=video_name,
            subtitle_file_name=subtitle_name,
            final_start_ms=start_ms,
            final_end_ms=end_ms,
            duration_ms=end_ms - start_ms,
            output_folder_name=inputs.output_dir.name or "exports",
            subtitles_burned_in=subtitles_burned_in,
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ReviewError,
    ):
        return None


def _risk_text(candidate: dict[str, Any]) -> str:
    penalty = candidate["risk_penalty"]
    if penalty:
        return f"AI 风险扣分 {penalty}；仍需人工复核具体风险。"
    return "AI 未标记具体风险；仍需人工复核隐私、健康和营销表述。"


def build_session_payload(
    inputs: ReviewInputs,
    *,
    exported_candidate_id: str | None = None,
    completed_export: CompletedExport | None = None,
) -> dict[str, Any]:
    completed_candidate_id = (
        completed_export.candidate_id
        if completed_export is not None
        else exported_candidate_id
    )
    candidates = []
    for rank, candidate in enumerate(inputs.analysis["candidates"], start=1):
        candidates.append(
            {
                "id": candidate["id"],
                "rank": rank,
                "title": candidate["title"],
                "total_score": candidate["total_score"],
                "duration_ms": candidate["duration_ms"],
                "reason": candidate["reason"],
                "risk": _risk_text(candidate),
                "review_status": (
                    "已导出" if candidate["id"] == completed_candidate_id else "待审核"
                ),
                "original_start_ms": candidate["start_ms"],
                "original_end_ms": candidate["end_ms"],
            }
        )
    return {
        "schema_version": "1.0",
        "video": {
            "file_name": inputs.video_path.name,
            "duration_ms": inputs.video_duration_ms,
        },
        "candidates": candidates,
        "export_completed": completed_candidate_id is not None,
        "completed_export": (
            {
                "candidate_id": completed_export.candidate_id,
                "video_file_name": completed_export.video_file_name,
                "subtitle_file_name": completed_export.subtitle_file_name,
                "final_start_ms": completed_export.final_start_ms,
                "final_end_ms": completed_export.final_end_ms,
                "duration_ms": completed_export.duration_ms,
                "output_folder_name": completed_export.output_folder_name,
                "subtitles_burned_in": completed_export.subtitles_burned_in,
            }
            if completed_export is not None
            else None
        ),
    }

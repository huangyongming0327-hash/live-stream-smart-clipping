"""Machine-readable audio/video synchronization measurements."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .errors import MediaFileNotFoundError, ProbeError, ProcessExecutionError
from .ffmpeg_paths import FFmpegPaths, resolve_ffmpeg_paths
from .process_runner import run_process


@dataclass(frozen=True, slots=True)
class SyncTolerances:
    av_start_offset_ms: float = 100.0
    stream_duration_delta_ms: float = 150.0
    target_duration_delta_ms: float = 150.0

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative.")


@dataclass(frozen=True, slots=True)
class MediaSyncMetrics:
    path: Path
    video_start_time: float
    audio_start_time: float
    av_start_offset_ms: float
    video_duration: float
    audio_duration: float
    stream_duration_delta_ms: float
    container_duration: float
    target_duration: float
    target_duration_delta_ms: float
    sync_within_tolerance: bool
    duration_within_tolerance: bool
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["path"] = str(self.path)
        result["warnings"] = list(self.warnings)
        return result


def _json_object(payload: str | bytes | dict[str, Any], label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProbeError(f"ffprobe returned malformed {label} JSON.") from exc
    if not isinstance(value, dict):
        raise ProbeError(f"ffprobe {label} JSON root must be an object.")
    return value


def _finite_number(value: object, label: str, *, non_negative: bool = False) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ProbeError(f"ffprobe is missing a numeric {label}.") from exc
    if not math.isfinite(number) or (non_negative and number < 0):
        constraint = "finite and non-negative" if non_negative else "finite"
        raise ProbeError(f"ffprobe {label} must be {constraint}.")
    return number


def _stream_duration(streams: object, codec_type: str) -> float:
    if not isinstance(streams, list):
        raise ProbeError("ffprobe sync JSON streams must be an array.")
    stream = next(
        (
            item
            for item in streams
            if isinstance(item, dict) and item.get("codec_type") == codec_type
        ),
        None,
    )
    if stream is None:
        raise ProbeError(f"ffprobe sync JSON has no {codec_type} stream.")
    return _finite_number(
        stream.get("duration"), f"{codec_type} stream duration", non_negative=True
    )


def _first_timestamp(
    payload: dict[str, Any],
    collection_name: str,
    candidate_fields: tuple[str, ...],
    label: str,
) -> float:
    collection = payload.get(collection_name)
    if not isinstance(collection, list) or not collection or not isinstance(collection[0], dict):
        raise ProbeError(f"ffprobe is missing the first {label} start time.")
    first = collection[0]
    for field in candidate_fields:
        if first.get(field) not in (None, "", "N/A"):
            return _finite_number(first[field], f"first {label} PTS")
    raise ProbeError(f"ffprobe is missing the first {label} start time.")


def _within(value: float, tolerance: float) -> bool:
    magnitude = abs(value)
    return magnitude <= tolerance or math.isclose(
        magnitude, tolerance, rel_tol=0.0, abs_tol=1e-9
    )


def parse_sync_probe_json(
    stream_payload: str | bytes | dict[str, Any],
    video_frame_payload: str | bytes | dict[str, Any],
    audio_packet_payload: str | bytes | dict[str, Any],
    source_path: str | Path,
    *,
    target_duration: float,
    tolerances: SyncTolerances | None = None,
) -> MediaSyncMetrics:
    """Build finite synchronization metrics from three focused ffprobe results."""

    tolerances = tolerances or SyncTolerances()
    streams_data = _json_object(stream_payload, "stream")
    video_data = _json_object(video_frame_payload, "video-frame")
    audio_data = _json_object(audio_packet_payload, "audio-packet")
    streams = streams_data.get("streams")
    format_data = streams_data.get("format")
    if not isinstance(format_data, dict):
        raise ProbeError("ffprobe sync JSON format must be an object.")

    video_start = _first_timestamp(
        video_data,
        "frames",
        ("best_effort_timestamp_time", "pts_time"),
        "video frame",
    )
    audio_start = _first_timestamp(
        audio_data, "packets", ("pts_time", "dts_time"), "audio packet"
    )
    video_duration = _stream_duration(streams, "video")
    audio_duration = _stream_duration(streams, "audio")
    container_duration = _finite_number(
        format_data.get("duration"), "container duration", non_negative=True
    )
    target = _finite_number(target_duration, "target duration", non_negative=True)

    av_offset_ms = (audio_start - video_start) * 1000.0
    stream_delta_ms = (audio_duration - video_duration) * 1000.0
    target_delta_ms = (container_duration - target) * 1000.0
    av_start_ok = _within(av_offset_ms, tolerances.av_start_offset_ms)
    stream_duration_ok = _within(
        stream_delta_ms, tolerances.stream_duration_delta_ms
    )
    sync_ok = av_start_ok and stream_duration_ok
    duration_ok = _within(target_delta_ms, tolerances.target_duration_delta_ms)
    warnings: list[str] = []
    if not av_start_ok:
        warnings.append(
            f"A/V start offset {av_offset_ms:.3f} ms exceeds "
            f"{tolerances.av_start_offset_ms:.3f} ms."
        )
    if not stream_duration_ok:
        warnings.append(
            f"Stream duration delta {stream_delta_ms:.3f} ms exceeds "
            f"{tolerances.stream_duration_delta_ms:.3f} ms."
        )
    if not duration_ok:
        warnings.append(
            f"Target duration delta {target_delta_ms:.3f} ms exceeds "
            f"{tolerances.target_duration_delta_ms:.3f} ms."
        )

    numeric_values = (
        video_start,
        audio_start,
        av_offset_ms,
        video_duration,
        audio_duration,
        stream_delta_ms,
        container_duration,
        target,
        target_delta_ms,
    )
    if not all(math.isfinite(value) for value in numeric_values):
        raise ProbeError("Calculated synchronization metrics must all be finite.")

    return MediaSyncMetrics(
        path=Path(source_path).resolve(),
        video_start_time=video_start,
        audio_start_time=audio_start,
        av_start_offset_ms=av_offset_ms,
        video_duration=video_duration,
        audio_duration=audio_duration,
        stream_duration_delta_ms=stream_delta_ms,
        container_duration=container_duration,
        target_duration=target,
        target_duration_delta_ms=target_delta_ms,
        sync_within_tolerance=sync_ok,
        duration_within_tolerance=duration_ok,
        warnings=tuple(warnings),
    )


def probe_media_sync(
    media_path: str | Path,
    *,
    target_duration: float | None = None,
    paths: FFmpegPaths | None = None,
    tolerances: SyncTolerances | None = None,
    timeout_seconds: float = 30.0,
) -> MediaSyncMetrics:
    """Measure first A/V PTS and duration deltas with focused ffprobe JSON calls."""

    media = Path(media_path).resolve()
    if not media.is_file():
        raise MediaFileNotFoundError(f"Media file does not exist: {media}")
    paths = paths or resolve_ffmpeg_paths()
    try:
        stream_result = run_process(
            paths.ffprobe,
            (
                "-v",
                "error",
                "-show_entries",
                "stream=index,codec_type,start_time,duration",
                "-show_entries",
                "format=start_time,duration",
                "-of",
                "json",
                media,
            ),
            timeout_seconds=timeout_seconds,
        )
        video_result = run_process(
            paths.ffprobe,
            (
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-read_intervals",
                "%+#1",
                "-show_frames",
                "-show_entries",
                "frame=pts_time,best_effort_timestamp_time",
                "-of",
                "json",
                media,
            ),
            timeout_seconds=timeout_seconds,
        )
        audio_result = run_process(
            paths.ffprobe,
            (
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-read_intervals",
                "%+#1",
                "-show_packets",
                "-show_entries",
                "packet=pts_time,dts_time",
                "-of",
                "json",
                media,
            ),
            timeout_seconds=timeout_seconds,
        )
    except ProcessExecutionError as exc:
        detail = exc.failure.stderr.strip() or str(exc)
        raise ProbeError(f"ffprobe could not measure synchronization for {media}: {detail}") from exc

    stream_json = _json_object(stream_result.stdout, "stream")
    measured_target = (
        target_duration
        if target_duration is not None
        else _finite_number(
            (stream_json.get("format") or {}).get("duration")
            if isinstance(stream_json.get("format"), dict)
            else None,
            "container duration",
            non_negative=True,
        )
    )
    return parse_sync_probe_json(
        stream_json,
        video_result.stdout,
        audio_result.stdout,
        media,
        target_duration=measured_target,
        tolerances=tolerances,
    )

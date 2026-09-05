"""ffprobe JSON models and media probing."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import MediaFileNotFoundError, NoAudioStreamError, ProbeError
from .ffmpeg_paths import FFmpegPaths, resolve_ffmpeg_paths
from .process_runner import ProcessExecutionError, run_process


@dataclass(frozen=True, slots=True)
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str | None
    width: int | None = None
    height: int | None = None
    pixel_format: str | None = None
    frame_rate: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str | None = None


@dataclass(frozen=True, slots=True)
class MediaProbe:
    path: Path
    container_format: str
    duration_seconds: float
    file_size_bytes: int
    video_streams: tuple[StreamInfo, ...]
    audio_streams: tuple[StreamInfo, ...]

    @property
    def video_stream_count(self) -> int:
        return len(self.video_streams)

    @property
    def audio_stream_count(self) -> int:
        return len(self.audio_streams)

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_streams)


def parse_frame_rate(value: object) -> float | None:
    if value in (None, "", "0/0", "N/A"):
        return None
    try:
        if isinstance(value, str) and "/" in value:
            numerator_text, denominator_text = value.split("/", 1)
            denominator = float(denominator_text)
            if denominator == 0:
                return None
            result = float(numerator_text) / denominator
        else:
            result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        return None


def _duration(format_data: dict[str, Any], streams: list[dict[str, Any]]) -> float:
    candidates: list[float] = []
    for value in (format_data.get("duration"), *(s.get("duration") for s in streams)):
        try:
            candidate = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(candidate) and candidate >= 0:
            candidates.append(candidate)
    if not candidates:
        raise ProbeError("ffprobe JSON does not contain a finite media duration.")
    return max(candidates)


def parse_probe_json(
    payload: str | bytes | dict[str, Any],
    source_path: str | Path,
    *,
    require_audio: bool = False,
) -> MediaProbe:
    try:
        data = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProbeError("ffprobe returned malformed JSON.") from exc
    if not isinstance(data, dict):
        raise ProbeError("ffprobe JSON root must be an object.")

    raw_streams = data.get("streams", [])
    format_data = data.get("format", {})
    if not isinstance(raw_streams, list) or not isinstance(format_data, dict):
        raise ProbeError("ffprobe JSON has invalid streams or format fields.")

    streams: list[StreamInfo] = []
    stream_dicts = [item for item in raw_streams if isinstance(item, dict)]
    for item in stream_dicts:
        codec_type = str(item.get("codec_type") or "")
        streams.append(
            StreamInfo(
                index=_optional_int(item.get("index")) or 0,
                codec_type=codec_type,
                codec_name=(str(item["codec_name"]) if item.get("codec_name") else None),
                width=_optional_int(item.get("width")),
                height=_optional_int(item.get("height")),
                pixel_format=(
                    str(item["pix_fmt"]) if item.get("pix_fmt") else None
                ),
                frame_rate=parse_frame_rate(
                    item.get("avg_frame_rate") or item.get("r_frame_rate")
                ),
                sample_rate=_optional_int(item.get("sample_rate")),
                channels=_optional_int(item.get("channels")),
                channel_layout=(
                    str(item["channel_layout"]) if item.get("channel_layout") else None
                ),
            )
        )

    path = Path(source_path).resolve()
    size = _optional_int(format_data.get("size"))
    if size is None and path.is_file():
        size = path.stat().st_size
    if size is None:
        size = 0

    result = MediaProbe(
        path=path,
        container_format=str(format_data.get("format_name") or "unknown"),
        duration_seconds=_duration(format_data, stream_dicts),
        file_size_bytes=size,
        video_streams=tuple(s for s in streams if s.codec_type == "video"),
        audio_streams=tuple(s for s in streams if s.codec_type == "audio"),
    )
    if require_audio and not result.has_audio:
        raise NoAudioStreamError(f"Media has no audio stream: {path}")
    return result


def probe_media(
    media_path: str | Path,
    *,
    paths: FFmpegPaths | None = None,
    require_audio: bool = False,
    timeout_seconds: float = 30.0,
) -> MediaProbe:
    media = Path(media_path).resolve()
    if not media.is_file():
        raise MediaFileNotFoundError(f"Media file does not exist: {media}")
    paths = paths or resolve_ffmpeg_paths()
    try:
        result = run_process(
            paths.ffprobe,
            (
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                media,
            ),
            timeout_seconds=timeout_seconds,
        )
    except ProcessExecutionError as exc:
        detail = exc.failure.stderr.strip() or str(exc)
        raise ProbeError(f"ffprobe could not read {media}: {detail}") from exc
    return parse_probe_json(result.stdout, media, require_audio=require_audio)

"""Minimal UTF-8 SRT retiming and libass subtitle burn-in."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .errors import MediaFileNotFoundError, SubtitleError
from .ffmpeg_paths import FFmpegPaths, resolve_ffmpeg_paths
from .outputs import (
    discard_temporary,
    prepare_output,
    publish_without_overwrite,
    temporary_sibling,
)
from .probe import MediaProbe, probe_media
from .process_runner import run_process

_TIMESTAMP_PATTERN = re.compile(r"^(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})$")


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    index: int
    start_seconds: float
    end_seconds: float
    text: str


def parse_srt_timestamp(value: str) -> float:
    match = _TIMESTAMP_PATTERN.fullmatch(value.strip())
    if not match:
        raise SubtitleError(f"Invalid SRT timestamp: {value!r}")
    hours, minutes, seconds, milliseconds = (int(part) for part in match.groups())
    if minutes >= 60 or seconds >= 60:
        raise SubtitleError(f"Invalid SRT timestamp: {value!r}")
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def format_srt_timestamp(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise SubtitleError("SRT time must be finite and non-negative.")
    total_ms = int(
        (Decimal(str(seconds)) * Decimal(1000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def parse_srt_text(text: str) -> list[SubtitleCue]:
    normalized = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return []
    blocks = re.split(r"\n[ \t]*\n", normalized.strip("\n"))
    cues: list[SubtitleCue] = []
    for block in blocks:
        lines = block.split("\n")
        if len(lines) < 2:
            raise SubtitleError(f"Malformed SRT cue: {block!r}")
        try:
            index = int(lines[0].strip())
        except ValueError as exc:
            raise SubtitleError(f"Invalid SRT cue index: {lines[0]!r}") from exc
        if "-->" not in lines[1]:
            raise SubtitleError(f"Missing SRT time arrow in cue {index}.")
        start_text, end_text = (part.strip() for part in lines[1].split("-->", 1))
        start = parse_srt_timestamp(start_text)
        end = parse_srt_timestamp(end_text)
        if end <= start:
            raise SubtitleError(f"SRT cue {index} must end after it starts.")
        cues.append(
            SubtitleCue(
                index=index,
                start_seconds=start,
                end_seconds=end,
                text="\n".join(lines[2:]),
            )
        )
    return cues


def read_srt(path: str | Path) -> list[SubtitleCue]:
    source = Path(path).resolve()
    if not source.is_file():
        raise MediaFileNotFoundError(f"SRT file does not exist: {source}")
    return parse_srt_text(source.read_text(encoding="utf-8-sig"))


def retime_cues(
    cues: list[SubtitleCue], clip_start: float, clip_end: float
) -> list[SubtitleCue]:
    if (
        not math.isfinite(clip_start)
        or not math.isfinite(clip_end)
        or clip_start < 0
        or clip_end <= clip_start
    ):
        raise ValueError("Clip range must be finite and satisfy 0 <= start < end.")
    duration = clip_end - clip_start
    result: list[SubtitleCue] = []
    for cue in cues:
        if cue.end_seconds <= clip_start or cue.start_seconds >= clip_end:
            continue
        start = max(cue.start_seconds, clip_start) - clip_start
        end = min(cue.end_seconds, clip_end) - clip_start
        # SRT has millisecond precision; quantize here to avoid float drift.
        start = round(max(0.0, min(start, duration)), 3)
        end = round(max(0.0, min(end, duration)), 3)
        if end <= start:
            continue
        result.append(
            SubtitleCue(
                index=len(result) + 1,
                start_seconds=start,
                end_seconds=end,
                text=cue.text,
            )
        )
    return result


def render_srt(cues: list[SubtitleCue]) -> str:
    blocks = [
        "\n".join(
            (
                str(index),
                f"{format_srt_timestamp(cue.start_seconds)} --> "
                f"{format_srt_timestamp(cue.end_seconds)}",
                cue.text,
            )
        )
        for index, cue in enumerate(cues, start=1)
    ]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def write_srt(cues: list[SubtitleCue], output_path: str | Path) -> Path:
    output = prepare_output(output_path)
    temporary = temporary_sibling(output)
    try:
        temporary.write_text(render_srt(cues), encoding="utf-8", newline="\n")
        publish_without_overwrite(temporary, output)
        return output
    except Exception:
        discard_temporary(temporary)
        raise


def retime_srt(
    source_path: str | Path,
    output_path: str | Path,
    clip_start: float,
    clip_end: float,
) -> list[SubtitleCue]:
    cues = retime_cues(read_srt(source_path), clip_start, clip_end)
    write_srt(cues, output_path)
    return cues


def escape_subtitles_path(path: str | Path) -> str:
    """Escape a Windows path for FFmpeg's subtitles filter parser."""

    value = Path(path).resolve().as_posix()
    value = value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"filename='{value}'"


def burn_subtitles(
    media_path: str | Path,
    srt_path: str | Path,
    output_path: str | Path,
    *,
    paths: FFmpegPaths | None = None,
    timeout_seconds: float = 180.0,
) -> MediaProbe:
    paths = paths or resolve_ffmpeg_paths()
    source = Path(media_path).resolve()
    subtitle = Path(srt_path).resolve()
    if not subtitle.is_file():
        raise MediaFileNotFoundError(f"SRT file does not exist: {subtitle}")
    output = prepare_output(output_path)
    probe_media(source, paths=paths, require_audio=True, timeout_seconds=timeout_seconds)
    filter_value = (
        f"subtitles={escape_subtitles_path(subtitle)}:charenc=UTF-8:"
        "force_style='FontName=Microsoft YaHei,FontSize=24',setpts=PTS-STARTPTS"
    )
    temporary = temporary_sibling(output)
    try:
        run_process(
            paths.ffmpeg,
            (
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                source,
                "-vf",
                filter_value,
                "-af",
                "asetpts=PTS-STARTPTS",
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                "-avoid_negative_ts",
                "make_zero",
                temporary,
            ),
            timeout_seconds=timeout_seconds,
        )
        result = probe_media(
            temporary, paths=paths, require_audio=True, timeout_seconds=timeout_seconds
        )
        publish_without_overwrite(temporary, output)
        return MediaProbe(
            path=output,
            container_format=result.container_format,
            duration_seconds=result.duration_seconds,
            file_size_bytes=output.stat().st_size,
            video_streams=result.video_streams,
            audio_streams=result.audio_streams,
        )
    except Exception:
        discard_temporary(temporary)
        raise

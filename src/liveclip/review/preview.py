"""Low-resource, browser-compatible review preview proxy generation."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from liveclip.media import FFmpegPaths, MediaProbe, probe_media, resolve_ffmpeg_paths
from liveclip.media.errors import ProcessExecutionError
from liveclip.media.outputs import discard_temporary
from liveclip.media.process_runner import ProcessResult, run_process

from .schema import ReviewError, ReviewInputs, sha256_file


PREVIEW_VERSION = "browser_preview_v1"
MAX_PREVIEW_WIDTH = 1280
MAX_PREVIEW_HEIGHT = 720
MAX_DURATION_MISMATCH_MS = 1_000
PREVIEW_FILTER = (
    "scale=w='min(1280,iw)':h='min(720,ih)':"
    "force_original_aspect_ratio=decrease:force_divisible_by=2:out_range=tv,"
    "format=yuv420p,setparams=range=limited,"
    "setsar=1,setpts=PTS-STARTPTS"
)


@dataclass(frozen=True, slots=True)
class PreviewResult:
    path: Path
    cached: bool
    elapsed_seconds: float
    width: int
    height: int
    file_size_bytes: int


ProcessFunction = Callable[..., ProcessResult]
ProbeFunction = Callable[..., MediaProbe]


def preview_proxy_path(inputs: ReviewInputs) -> Path:
    """Return a source-bound cache path inside the current LiveClip work directory."""

    return (
        inputs.analysis_path.parent
        / ".review_preview"
        / f"{PREVIEW_VERSION}_{inputs.video_sha256}.mp4"
    )


def _resolve_tools(paths: FFmpegPaths | None) -> FFmpegPaths:
    if paths is not None:
        return paths
    try:
        return resolve_ffmpeg_paths()
    except Exception:
        raise ReviewError("项目本地 FFmpeg/ffprobe 不可用。") from None


def preview_ffmpeg_arguments(
    inputs: ReviewInputs,
    temporary_output: Path,
) -> tuple[str | Path, ...]:
    arguments: list[str | Path] = [
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        inputs.video_path,
        "-map",
        "0:v:0",
    ]
    if inputs.has_audio:
        arguments.extend(("-map", "0:a:0", "-af", "asetpts=PTS-STARTPTS"))
    arguments.extend(
        (
            "-vf",
            PREVIEW_FILTER,
            "-c:v",
            "libx264",
            "-profile:v",
            "main",
            "-preset",
            "veryfast",
            "-crf",
            "29",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "2",
        )
    )
    if inputs.has_audio:
        arguments.extend(("-c:a", "aac", "-ac", "2", "-b:a", "96k"))
    arguments.extend(
        (
            "-movflags",
            "+faststart",
            temporary_output,
        )
    )
    return tuple(arguments)


def _valid_dimensions(probe: MediaProbe) -> tuple[int, int] | None:
    if not probe.video_streams:
        return None
    width = probe.video_streams[0].width
    height = probe.video_streams[0].height
    if (
        isinstance(width, bool)
        or not isinstance(width, int)
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height <= 0
        or width > MAX_PREVIEW_WIDTH
        or height > MAX_PREVIEW_HEIGHT
        or width % 2
        or height % 2
    ):
        return None
    return width, height


def validate_preview_proxy(
    path: Path,
    inputs: ReviewInputs,
    *,
    paths: FFmpegPaths,
    probe_function: ProbeFunction = probe_media,
) -> MediaProbe | None:
    """Return probe data only for a complete proxy matching the source contract."""

    try:
        if not path.is_file() or path.stat().st_size <= 0:
            return None
        probe = probe_function(
            path,
            paths=paths,
            require_audio=False,
            timeout_seconds=30.0,
        )
        dimensions = _valid_dimensions(probe)
        if dimensions is None:
            return None
        video = probe.video_streams[0]
        if video.codec_name != "h264" or video.pixel_format != "yuv420p":
            return None
        duration_ms = int(round(probe.duration_seconds * 1000))
        if (
            not math.isfinite(probe.duration_seconds)
            or probe.duration_seconds <= 0
            or abs(duration_ms - inputs.video_duration_ms) > MAX_DURATION_MISMATCH_MS
        ):
            return None
        if inputs.has_audio:
            if not probe.audio_streams or probe.audio_streams[0].codec_name != "aac":
                return None
        elif probe.audio_streams:
            return None

        width, height = dimensions
        source_ratio = inputs.video_width / inputs.video_height
        proxy_ratio = width / height
        if abs(proxy_ratio - source_ratio) / source_ratio > 0.01:
            return None
        return probe
    except (OSError, OverflowError, ValueError, TypeError):
        return None
    except Exception:
        return None


def ensure_preview_proxy(
    inputs: ReviewInputs,
    *,
    paths: FFmpegPaths | None = None,
    process_function: ProcessFunction = run_process,
    probe_function: ProbeFunction = probe_media,
    timeout_seconds: float = 14_400.0,
) -> PreviewResult:
    """Create or reuse one validated full-duration browser preview proxy."""

    resolved_paths = _resolve_tools(paths)
    output = preview_proxy_path(inputs)
    cached_probe = validate_preview_proxy(
        output,
        inputs,
        paths=resolved_paths,
        probe_function=probe_function,
    )
    if cached_probe is not None:
        width, height = _valid_dimensions(cached_probe) or (0, 0)
        return PreviewResult(output, True, 0.0, width, height, output.stat().st_size)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise ReviewError("兼容预览缓存目录无法创建。") from None
    temporary = output.with_name(f".{output.stem}.{uuid4().hex}.part.mp4")
    process_result: ProcessResult | None = None
    try:
        if (
            sha256_file(inputs.video_path) != inputs.video_sha256
            or sha256_file(inputs.timeline_path) != inputs.timeline_sha256
            or sha256_file(inputs.analysis_path) != inputs.analysis_sha256
        ):
            raise ReviewError("审核输入在生成兼容预览前发生变化。")
        try:
            process_result = process_function(
                resolved_paths.ffmpeg,
                preview_ffmpeg_arguments(inputs, temporary),
                timeout_seconds=timeout_seconds,
            )
        except ProcessExecutionError:
            raise ReviewError("兼容预览生成失败。") from None
        except OSError:
            raise ReviewError("兼容预览无法启动 FFmpeg。") from None
        probe = validate_preview_proxy(
            temporary,
            inputs,
            paths=resolved_paths,
            probe_function=probe_function,
        )
        if probe is None:
            raise ReviewError("兼容预览未通过格式或时间轴校验。")
        if (
            sha256_file(inputs.video_path) != inputs.video_sha256
            or sha256_file(inputs.timeline_path) != inputs.timeline_sha256
            or sha256_file(inputs.analysis_path) != inputs.analysis_sha256
        ):
            raise ReviewError("审核输入在生成兼容预览期间发生变化。")
        os.replace(temporary, output)
        width, height = _valid_dimensions(probe) or (0, 0)
        return PreviewResult(
            output,
            False,
            process_result.elapsed_seconds if process_result else 0.0,
            width,
            height,
            output.stat().st_size,
        )
    except ReviewError:
        raise
    except OSError:
        raise ReviewError("兼容预览无法安全发布。") from None
    finally:
        discard_temporary(temporary)

"""Low-resource, browser-compatible review preview proxy generation."""

from __future__ import annotations

import math
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from liveclip.media import FFmpegPaths, MediaProbe, probe_media, resolve_ffmpeg_paths
from liveclip.media.errors import ProcessExecutionError
from liveclip.media.outputs import discard_temporary
from liveclip.media.process_runner import ProcessResult, run_process

from .schema import ReviewError, ReviewInputs, sha256_file


PREVIEW_VERSION = "v2"
CACHE_PARENT_NAME = ".review_preview"
CACHE_MARKER_NAME = ".liveclip-preview-cache"
CACHE_MARKER_CONTENT = f"liveclip-review-preview\n{PREVIEW_VERSION}\n".encode("ascii")
MAX_PREVIEW_WIDTH = 1280
MAX_PREVIEW_HEIGHT = 720
MAX_DURATION_MISMATCH_MS = 1_000
MAX_START_TIME_SECONDS = 0.05
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


def _is_reparse_point(details: os.stat_result) -> bool:
    attributes = getattr(details, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & flag)


def _lstat(path: Path) -> os.stat_result:
    try:
        return path.lstat()
    except OSError:
        raise ReviewError("兼容预览缓存路径无法安全读取。") from None


def _require_plain_directory(path: Path) -> None:
    details = _lstat(path)
    if _is_reparse_point(details) or not stat.S_ISDIR(details.st_mode):
        raise ReviewError("兼容预览缓存目录必须是本地普通目录。")


def _require_plain_file(path: Path) -> None:
    details = _lstat(path)
    if _is_reparse_point(details) or not stat.S_ISREG(details.st_mode):
        raise ReviewError("兼容预览缓存文件类型不安全。")


def _controlled_root(inputs: ReviewInputs) -> Path:
    try:
        root = inputs.analysis_path.parent.resolve(strict=True)
    except OSError:
        raise ReviewError("审核工作目录无法安全解析。") from None
    _require_plain_directory(root)
    return root


def _cache_directory(inputs: ReviewInputs, *, create: bool) -> Path:
    root = _controlled_root(inputs)
    parent = root / CACHE_PARENT_NAME
    versioned = parent / PREVIEW_VERSION
    marker = versioned / CACHE_MARKER_NAME

    if not os.path.lexists(parent):
        if not create:
            raise ReviewError("兼容预览缓存尚未初始化。")
        try:
            parent.mkdir()
        except FileExistsError:
            pass
        except OSError:
            raise ReviewError("兼容预览缓存目录无法创建。") from None
    _require_plain_directory(parent)

    created_version = False
    if not os.path.lexists(versioned):
        if not create:
            raise ReviewError("兼容预览缓存尚未初始化。")
        try:
            versioned.mkdir()
            created_version = True
        except FileExistsError:
            pass
        except OSError:
            raise ReviewError("兼容预览缓存目录无法创建。") from None
    _require_plain_directory(parent)
    _require_plain_directory(versioned)

    if created_version:
        try:
            with marker.open("xb") as handle:
                handle.write(CACHE_MARKER_CONTENT)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            raise ReviewError("兼容预览缓存所有权标记无法创建。") from None
    if not os.path.lexists(marker):
        raise ReviewError("兼容预览缓存目录缺少所有权标记。")
    _require_plain_file(marker)
    try:
        if marker.read_bytes() != CACHE_MARKER_CONTENT:
            raise ReviewError("兼容预览缓存目录所有权标记无效。")
    except OSError:
        raise ReviewError("兼容预览缓存所有权标记无法读取。") from None

    _require_plain_directory(parent)
    _require_plain_directory(versioned)
    return versioned


def preview_proxy_path(inputs: ReviewInputs) -> Path:
    """Return the v2 source-bound cache path under the resolved work root."""

    return (
        _controlled_root(inputs)
        / CACHE_PARENT_NAME
        / PREVIEW_VERSION
        / f"{PREVIEW_VERSION}_{inputs.video_sha256}.mp4"
    )


def _validate_cache_file_path(
    path: Path,
    inputs: ReviewInputs,
    *,
    allow_temporary: bool,
) -> Path:
    cache = _cache_directory(inputs, create=False)
    expected = cache / f"{PREVIEW_VERSION}_{inputs.video_sha256}.mp4"
    allowed = path == expected
    if allow_temporary and path.parent == cache:
        prefix = f".{expected.stem}."
        middle = path.name[len(prefix) : -len(".part.mp4")]
        allowed = allowed or (
            path.name.startswith(prefix)
            and path.name.endswith(".part.mp4")
            and len(middle) == 32
            and all(character in "0123456789abcdef" for character in middle)
        )
    if not allowed or not os.path.lexists(path):
        raise ReviewError("兼容预览尚未准备好。")
    _require_plain_file(path)
    return path


def validate_preview_media_path(path: Path, inputs: ReviewInputs) -> Path:
    """Validate an already-owned final proxy immediately before local serving."""

    return _validate_cache_file_path(path, inputs, allow_temporary=False)


def _resolve_tools(paths: FFmpegPaths | None) -> FFmpegPaths:
    if paths is not None:
        return paths
    try:
        return resolve_ffmpeg_paths()
    except Exception:
        raise ReviewError("项目本地 FFmpeg/ffprobe 不可用。") from None


def _audio_filter(inputs: ReviewInputs) -> str:
    audio_start = inputs.audio_start_time_seconds or 0.0
    relative_start = audio_start - inputs.video_start_time_seconds
    duration = inputs.video_duration_ms / 1000
    filters: list[str] = ["asetpts=PTS-STARTPTS"]
    if relative_start < -0.0005:
        filters.extend(
            (f"atrim=start={-relative_start:.6f}", "asetpts=PTS-STARTPTS")
        )
    if relative_start > 0.0005:
        filters.append(f"adelay={int(round(relative_start * 1000))}:all=1")
    filters.extend((f"apad=whole_dur={duration:.3f}", f"atrim=duration={duration:.3f}"))
    return ",".join(filters)


def preview_ffmpeg_arguments(
    inputs: ReviewInputs,
    temporary_output: Path,
) -> tuple[str | Path, ...]:
    arguments: list[str | Path] = [
        "-nostdin", "-hide_banner", "-loglevel", "error", "-i", inputs.video_path,
        "-map", "0:v:0",
    ]
    if inputs.has_audio:
        arguments.extend(("-map", "0:a:0", "-af", _audio_filter(inputs)))
    arguments.extend((
        "-vf", PREVIEW_FILTER, "-c:v", "libx264", "-profile:v", "main",
        "-preset", "veryfast", "-crf", "29", "-pix_fmt", "yuv420p",
        "-threads", "2",
    ))
    if inputs.has_audio:
        arguments.extend(("-c:a", "aac", "-ac", "2", "-b:a", "96k"))
    arguments.extend(("-movflags", "+faststart", temporary_output))
    return tuple(arguments)


def _valid_dimensions(probe: MediaProbe, inputs: ReviewInputs) -> tuple[int, int] | None:
    if not probe.video_streams:
        return None
    width = probe.video_streams[0].width
    height = probe.video_streams[0].height
    if (
        isinstance(width, bool) or not isinstance(width, int) or width <= 0
        or isinstance(height, bool) or not isinstance(height, int) or height <= 0
        or width > min(MAX_PREVIEW_WIDTH, inputs.video_width)
        or height > min(MAX_PREVIEW_HEIGHT, inputs.video_height)
        or width % 2 or height % 2
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
    """Return probe data only for a safe, complete proxy matching the v2 contract."""

    try:
        _validate_cache_file_path(path, inputs, allow_temporary=True)
        if path.stat().st_size <= 0:
            return None
        probe = probe_function(path, paths=paths, require_audio=False, timeout_seconds=30.0)
        dimensions = _valid_dimensions(probe, inputs)
        if dimensions is None:
            return None
        video = probe.video_streams[0]
        if (
            video.codec_name != "h264" or video.pixel_format != "yuv420p"
            or video.profile != "Main" or video.start_time_seconds is None
            or abs(video.start_time_seconds) > MAX_START_TIME_SECONDS
        ):
            return None
        duration_ms = int(round(probe.duration_seconds * 1000))
        if (
            not math.isfinite(probe.duration_seconds) or probe.duration_seconds <= 0
            or abs(duration_ms - inputs.video_duration_ms) > MAX_DURATION_MISMATCH_MS
        ):
            return None
        if inputs.has_audio:
            if not probe.audio_streams or probe.audio_streams[0].codec_name != "aac":
                return None
            audio_start = probe.audio_streams[0].start_time_seconds
            if audio_start is None or abs(audio_start) > MAX_START_TIME_SECONDS:
                return None
        elif probe.audio_streams:
            return None

        width, height = dimensions
        source_ratio = inputs.video_width / inputs.video_height
        proxy_ratio = width / height
        if abs(proxy_ratio - source_ratio) / source_ratio > 0.01:
            return None
        return probe
    except Exception:
        return None


def _inputs_match_bound_hashes(inputs: ReviewInputs) -> bool:
    try:
        return (
            sha256_file(inputs.video_path) == inputs.video_sha256
            and sha256_file(inputs.timeline_path) == inputs.timeline_sha256
            and sha256_file(inputs.analysis_path) == inputs.analysis_sha256
        )
    except OSError:
        return False


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
    if not _inputs_match_bound_hashes(inputs):
        raise ReviewError("审核输入在生成兼容预览前发生变化。")
    cache = _cache_directory(inputs, create=True)
    output = cache / f"{PREVIEW_VERSION}_{inputs.video_sha256}.mp4"
    if os.path.lexists(output):
        _require_plain_file(output)
        cached_probe = validate_preview_proxy(
            output, inputs, paths=resolved_paths, probe_function=probe_function
        )
        if cached_probe is not None:
            width, height = _valid_dimensions(cached_probe, inputs) or (0, 0)
            return PreviewResult(output, True, 0.0, width, height, output.stat().st_size)

    temporary = output.with_name(f".{output.stem}.{uuid4().hex}.part.mp4")
    process_result: ProcessResult | None = None
    try:
        _cache_directory(inputs, create=False)
        process_result = process_function(
            resolved_paths.ffmpeg,
            preview_ffmpeg_arguments(inputs, temporary),
            timeout_seconds=timeout_seconds,
        )
        probe = validate_preview_proxy(
            temporary, inputs, paths=resolved_paths, probe_function=probe_function
        )
        if probe is None:
            raise ReviewError("兼容预览未通过格式或时间轴校验。")
        if not _inputs_match_bound_hashes(inputs):
            raise ReviewError("审核输入在生成兼容预览期间发生变化。")
        cache = _cache_directory(inputs, create=False)
        if cache / output.name != output:
            raise ReviewError("兼容预览缓存路径在发布前发生变化。")
        if os.path.lexists(output):
            _require_plain_file(output)
        _require_plain_file(temporary)
        os.replace(temporary, output)
        validate_preview_media_path(output, inputs)
        width, height = _valid_dimensions(probe, inputs) or (0, 0)
        return PreviewResult(
            output, False,
            process_result.elapsed_seconds if process_result else 0.0,
            width, height, output.stat().st_size,
        )
    except ProcessExecutionError:
        raise ReviewError("兼容预览生成失败。") from None
    except ReviewError:
        raise
    except OSError:
        raise ReviewError("兼容预览无法安全发布。") from None
    finally:
        discard_temporary(temporary)

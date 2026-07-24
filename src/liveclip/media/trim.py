"""Frame-accurate re-encoded video trimming."""

from __future__ import annotations

import math
from pathlib import Path

from .ffmpeg_paths import FFmpegPaths, resolve_ffmpeg_paths
from .outputs import (
    discard_temporary,
    prepare_output,
    publish_without_overwrite,
    temporary_sibling,
)
from .probe import MediaProbe, probe_media
from .process_runner import run_process


def trim_video_precise(
    media_path: str | Path,
    output_path: str | Path,
    start_seconds: float,
    end_seconds: float,
    *,
    paths: FFmpegPaths | None = None,
    video_encoder: str = "libx264",
    timeout_seconds: float = 180.0,
) -> MediaProbe:
    """Trim with input decoding and CPU H.264/AAC re-encoding for precision."""

    if (
        not math.isfinite(start_seconds)
        or not math.isfinite(end_seconds)
        or start_seconds < 0
        or end_seconds <= start_seconds
    ):
        raise ValueError("Trim range must be finite and satisfy 0 <= start < end.")

    paths = paths or resolve_ffmpeg_paths()
    source = Path(media_path).resolve()
    output = prepare_output(output_path)
    source_probe = probe_media(
        source, paths=paths, require_audio=True, timeout_seconds=timeout_seconds
    )
    if end_seconds > source_probe.duration_seconds + 0.001:
        raise ValueError(
            f"Trim end {end_seconds} exceeds media duration "
            f"{source_probe.duration_seconds:.3f}."
        )

    duration = end_seconds - start_seconds
    temporary = temporary_sibling(output)
    try:
        run_process(
            paths.ffmpeg,
            (
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{start_seconds:.6f}",
                "-i",
                source,
                "-t",
                f"{duration:.6f}",
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-c:v",
                video_encoder,
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

"""Audio extraction for later ASR tasks (without performing ASR)."""

from __future__ import annotations

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


def extract_asr_wav(
    media_path: str | Path,
    output_path: str | Path,
    *,
    paths: FFmpegPaths | None = None,
    timeout_seconds: float = 120.0,
) -> MediaProbe:
    """Extract PCM s16le, 16 kHz, mono WAV and return its verified probe."""

    paths = paths or resolve_ffmpeg_paths()
    source = Path(media_path).resolve()
    output = prepare_output(output_path)
    probe_media(source, paths=paths, require_audio=True, timeout_seconds=timeout_seconds)
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
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-f",
                "wav",
                temporary,
            ),
            timeout_seconds=timeout_seconds,
        )
        result = probe_media(
            temporary, paths=paths, require_audio=True, timeout_seconds=timeout_seconds
        )
        audio = result.audio_streams[0]
        if audio.codec_name != "pcm_s16le" or audio.sample_rate != 16000 or audio.channels != 1:
            raise ValueError(
                "Extracted WAV is not PCM s16le, 16 kHz, mono as required."
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

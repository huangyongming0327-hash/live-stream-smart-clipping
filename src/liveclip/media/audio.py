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


def extract_asr_wav_chunk(
    media_path: str | Path,
    output_path: str | Path,
    *,
    start_ms: int,
    duration_ms: int,
    paths: FFmpegPaths | None = None,
    timeout_seconds: float = 120.0,
) -> Path:
    """Extract one PCM s16le, 16 kHz, mono WAV chunk without loading full media."""

    if start_ms < 0:
        raise ValueError("start_ms must be non-negative")
    if duration_ms <= 0:
        raise ValueError("duration_ms must be positive")

    paths = paths or resolve_ffmpeg_paths()
    source = Path(media_path).resolve()
    output = prepare_output(output_path)
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
                f"{start_ms / 1000:.3f}",
                "-i",
                source,
                "-t",
                f"{duration_ms / 1000:.3f}",
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
        if not temporary.is_file() or temporary.stat().st_size <= 44:
            raise ValueError("FFmpeg produced an empty ASR WAV chunk.")
        publish_without_overwrite(temporary, output)
        return output
    except Exception:
        discard_temporary(temporary)
        raise

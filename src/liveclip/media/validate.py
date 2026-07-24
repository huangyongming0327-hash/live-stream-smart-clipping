"""Lightweight post-export validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ffmpeg_paths import FFmpegPaths
from .probe import MediaProbe, probe_media
from .subtitles import read_srt
from .sync import MediaSyncMetrics, SyncTolerances, probe_media_sync


@dataclass(frozen=True, slots=True)
class ExportValidation:
    ok: bool
    path: Path
    exists: bool
    nonempty: bool
    probe_readable: bool
    video_stream_count: int
    audio_stream_count: int
    duration_seconds: float | None
    expected_duration_seconds: float | None
    duration_tolerance_seconds: float
    video_codecs: tuple[str, ...]
    audio_codecs: tuple[str, ...]
    srt_checked: bool
    srt_within_duration: bool | None
    video_start_time: float | None
    audio_start_time: float | None
    av_start_offset_ms: float | None
    video_duration: float | None
    audio_duration: float | None
    stream_duration_delta_ms: float | None
    container_duration: float | None
    target_duration: float | None
    target_duration_delta_ms: float | None
    sync_within_tolerance: bool | None
    duration_within_tolerance: bool | None
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


def validate_export(
    media_path: str | Path,
    *,
    expected_duration_seconds: float | None = None,
    duration_tolerance_seconds: float = 0.15,
    require_audio: bool = True,
    srt_path: str | Path | None = None,
    paths: FFmpegPaths | None = None,
    sync_tolerances: SyncTolerances | None = None,
) -> ExportValidation:
    media = Path(media_path).resolve()
    errors: list[str] = []
    exists = media.is_file()
    nonempty = exists and media.stat().st_size > 0
    if not exists:
        errors.append(f"Export does not exist: {media}")
    elif not nonempty:
        errors.append(f"Export is empty: {media}")

    probe: MediaProbe | None = None
    if nonempty:
        try:
            probe = probe_media(media, paths=paths, require_audio=False)
        except Exception as exc:  # Return all validation failures structurally.
            errors.append(f"ffprobe could not read export: {exc}")

    if probe is not None:
        if probe.video_stream_count < 1:
            errors.append("Export has no video stream.")
        if require_audio and probe.audio_stream_count < 1:
            errors.append("Export has no required audio stream.")
        if expected_duration_seconds is not None and abs(
            probe.duration_seconds - expected_duration_seconds
        ) > duration_tolerance_seconds:
            errors.append(
                f"Duration {probe.duration_seconds:.3f}s differs from expected "
                f"{expected_duration_seconds:.3f}s by more than "
                f"{duration_tolerance_seconds:.3f}s."
            )

    sync: MediaSyncMetrics | None = None
    sync_warnings: list[str] = []
    if probe is not None and probe.video_stream_count > 0 and probe.audio_stream_count > 0:
        try:
            sync = probe_media_sync(
                media,
                target_duration=(
                    expected_duration_seconds
                    if expected_duration_seconds is not None
                    else probe.duration_seconds
                ),
                paths=paths,
                tolerances=sync_tolerances,
            )
            sync_warnings.extend(sync.warnings)
            if not sync.sync_within_tolerance:
                errors.append("Export audio/video synchronization exceeds tolerance.")
            if not sync.duration_within_tolerance:
                errors.append("Export container duration differs from target beyond tolerance.")
        except Exception as exc:
            errors.append(f"Synchronization validation failed: {exc}")

    srt_checked = srt_path is not None
    srt_within_duration: bool | None = None
    if srt_path is not None:
        try:
            cues = read_srt(srt_path)
            if probe is None:
                srt_within_duration = False
            else:
                srt_within_duration = all(
                    cue.start_seconds >= 0
                    and cue.end_seconds <= probe.duration_seconds + 0.001
                    for cue in cues
                )
                if not srt_within_duration:
                    errors.append("SRT contains a cue outside the exported duration.")
        except Exception as exc:
            srt_within_duration = False
            errors.append(f"SRT validation failed: {exc}")

    video_codecs = (
        tuple(stream.codec_name or "unknown" for stream in probe.video_streams)
        if probe
        else ()
    )
    audio_codecs = (
        tuple(stream.codec_name or "unknown" for stream in probe.audio_streams)
        if probe
        else ()
    )
    return ExportValidation(
        ok=not errors,
        path=media,
        exists=exists,
        nonempty=nonempty,
        probe_readable=probe is not None,
        video_stream_count=probe.video_stream_count if probe else 0,
        audio_stream_count=probe.audio_stream_count if probe else 0,
        duration_seconds=probe.duration_seconds if probe else None,
        expected_duration_seconds=expected_duration_seconds,
        duration_tolerance_seconds=duration_tolerance_seconds,
        video_codecs=video_codecs,
        audio_codecs=audio_codecs,
        srt_checked=srt_checked,
        srt_within_duration=srt_within_duration,
        video_start_time=sync.video_start_time if sync else None,
        audio_start_time=sync.audio_start_time if sync else None,
        av_start_offset_ms=sync.av_start_offset_ms if sync else None,
        video_duration=sync.video_duration if sync else None,
        audio_duration=sync.audio_duration if sync else None,
        stream_duration_delta_ms=(sync.stream_duration_delta_ms if sync else None),
        container_duration=sync.container_duration if sync else None,
        target_duration=sync.target_duration if sync else None,
        target_duration_delta_ms=(sync.target_duration_delta_ms if sync else None),
        sync_within_tolerance=sync.sync_within_tolerance if sync else None,
        duration_within_tolerance=(sync.duration_within_tolerance if sync else None),
        warnings=tuple(sync_warnings),
        errors=tuple(errors),
    )

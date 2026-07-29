"""Deterministic PCM WAV validation and padded clipping."""

from __future__ import annotations

import hashlib
import math
import os
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from .input_parser import ReviewWindow


@dataclass(frozen=True, slots=True)
class WavInfo:
    channels: int
    sample_width_bytes: int
    sample_rate: int
    frame_count: int
    duration_seconds: float
    compression_type: str
    sha256: str


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_source_wav(path: str | Path) -> WavInfo:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    with wave.open(str(source), "rb") as handle:
        info = WavInfo(
            channels=handle.getnchannels(),
            sample_width_bytes=handle.getsampwidth(),
            sample_rate=handle.getframerate(),
            frame_count=handle.getnframes(),
            duration_seconds=handle.getnframes() / handle.getframerate(),
            compression_type=handle.getcomptype(),
            sha256=sha256_file(source),
        )
    if info.compression_type != "NONE":
        raise ValueError("Source WAV must use uncompressed PCM")
    if info.channels != 1:
        raise ValueError("Source WAV must be mono")
    if info.sample_width_bytes != 2:
        raise ValueError("Source WAV must use 16-bit samples")
    if info.sample_rate != 16_000:
        raise ValueError("Source WAV must use a 16 kHz sample rate")
    return info


def clip_window(
    source_path: str | Path,
    output_path: str | Path,
    window: ReviewWindow,
    wav_info: WavInfo,
    *,
    padding_seconds: float = 0.8,
) -> tuple[dict[str, object], bool]:
    if not math.isfinite(padding_seconds) or padding_seconds < 0:
        raise ValueError("padding_seconds must be finite and non-negative")

    source = Path(source_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    padded_start = max(0.0, window.start - padding_seconds)
    padded_end = min(wav_info.duration_seconds, window.end + padding_seconds)
    start_frame = max(0, int(math.floor(padded_start * wav_info.sample_rate)))
    end_frame = min(
        wav_info.frame_count,
        int(math.ceil(padded_end * wav_info.sample_rate)),
    )
    if end_frame <= start_frame:
        raise ValueError(f"window {window.window_id} produces an empty clip")

    with wave.open(str(source), "rb") as input_wav:
        input_wav.setpos(start_frame)
        frames = input_wav.readframes(end_frame - start_frame)

    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        with wave.open(str(temporary), "wb") as output_wav:
            output_wav.setnchannels(wav_info.channels)
            output_wav.setsampwidth(wav_info.sample_width_bytes)
            output_wav.setframerate(wav_info.sample_rate)
            output_wav.writeframes(frames)
        generated_sha = sha256_file(temporary)
        reused = destination.is_file() and sha256_file(destination) == generated_sha
        if reused:
            temporary.unlink()
        else:
            os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    actual_start = start_frame / wav_info.sample_rate
    actual_end = end_frame / wav_info.sample_rate
    return (
        {
            "window_id": window.window_id,
            "file": f"clips/{destination.name}",
            "original_start": window.start,
            "original_end": window.end,
            "actual_start": actual_start,
            "actual_end": actual_end,
            "duration_seconds": actual_end - actual_start,
            "sha256": generated_sha,
        },
        reused,
    )

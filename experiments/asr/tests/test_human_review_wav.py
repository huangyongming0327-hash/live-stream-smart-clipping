from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from experiments.asr.human_review.input_parser import ReviewWindow
from experiments.asr.human_review.wav_clipper import (
    clip_window,
    inspect_source_wav,
    sha256_file,
)


def _write_wav(
    path: Path,
    *,
    seconds: float = 3.0,
    rate: int = 16_000,
    channels: int = 1,
    sample_width: int = 2,
) -> None:
    frame_count = int(seconds * rate)
    if sample_width == 2:
        mono = b"".join(
            struct.pack("<h", int(1000 * math.sin(index / 15.0)))
            for index in range(frame_count)
        )
    else:
        mono = bytes((index % 255 for index in range(frame_count)))
    frames = b"".join(
        mono[index : index + sample_width] * channels
        for index in range(0, len(mono), sample_width)
    )
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(sample_width)
        handle.setframerate(rate)
        handle.writeframes(frames)


def _window(window_id: str, start: float, end: float) -> ReviewWindow:
    return ReviewWindow(
        window_id=window_id,
        start=start,
        end=end,
        label="合成",
        disagreement=0.0,
        candidate_texts={
            "SenseVoice": "甲",
            "Paraformer": "乙",
            "Faster-Whisper": "丙",
        },
    )


@pytest.mark.parametrize(
    "rate,channels,sample_width,match",
    [
        (8_000, 1, 2, "16 kHz"),
        (16_000, 2, 2, "mono"),
        (16_000, 1, 1, "16-bit"),
    ],
)
def test_invalid_wav_parameters_are_rejected(
    tmp_path: Path,
    rate: int,
    channels: int,
    sample_width: int,
    match: str,
) -> None:
    path = tmp_path / "invalid.wav"
    _write_wav(path, rate=rate, channels=channels, sample_width=sample_width)

    with pytest.raises(ValueError, match=match):
        inspect_source_wav(path)


def test_padding_is_clamped_and_output_parameters_are_preserved(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.wav"
    _write_wav(source)
    info = inspect_source_wav(source)

    first, _ = clip_window(
        source,
        tmp_path / "window-001.wav",
        _window("1", 0.2, 0.8),
        info,
    )
    last, _ = clip_window(
        source,
        tmp_path / "window-002.wav",
        _window("2", 2.5, 3.0004),
        info,
    )

    assert first["actual_start"] == 0.0
    assert first["actual_end"] == pytest.approx(1.6)
    assert last["actual_start"] == pytest.approx(1.7)
    assert last["actual_end"] == 3.0
    output_info = inspect_source_wav(tmp_path / "window-001.wav")
    assert (output_info.channels, output_info.sample_width_bytes, output_info.sample_rate) == (
        1,
        2,
        16_000,
    )


def test_clip_sha_and_repeat_run_are_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    destination = tmp_path / "window-001.wav"
    _write_wav(source)
    info = inspect_source_wav(source)

    first, first_reused = clip_window(
        source,
        destination,
        _window("1", 1.0, 1.5),
        info,
    )
    first_bytes = destination.read_bytes()
    second, second_reused = clip_window(
        source,
        destination,
        _window("1", 1.0, 1.5),
        info,
    )

    assert first_reused is False
    assert second_reused is True
    assert first == second
    assert destination.read_bytes() == first_bytes
    assert first["sha256"] == sha256_file(destination)

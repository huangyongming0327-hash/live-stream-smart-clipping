"""Strict parser for the existing TASK-002 human-review comparison CSV."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path


CSV_HEADERS = (
    "窗口",
    "开始秒",
    "结束秒",
    "类型",
    "分歧分",
    "SenseVoice",
    "Paraformer",
    "Faster-Whisper",
)
CANDIDATE_COLUMNS = CSV_HEADERS[5:]
TIMESTAMP_ROUNDING_TOLERANCE_SECONDS = 0.0005


@dataclass(frozen=True, slots=True)
class ReviewWindow:
    window_id: str
    start: float
    end: float
    label: str
    disagreement: float
    candidate_texts: dict[str, str]


def _finite_float(value: str, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def parse_review_csv(
    path: str | Path,
    *,
    audio_duration: float,
    expected_count: int = 20,
) -> list[ReviewWindow]:
    """Parse without repairing headers, identifiers, text, or time ranges.

    The existing TASK-002 CSV stores seconds to three decimal places. Its final
    endpoint may therefore round upward by at most half a millisecond. That
    representational tolerance is accepted explicitly; the original value is
    preserved and the clipper still clamps actual frames to the WAV boundary.
    """

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if not math.isfinite(audio_duration) or audio_duration <= 0:
        raise ValueError("audio_duration must be finite and positive")
    if expected_count <= 0:
        raise ValueError("expected_count must be positive")

    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_HEADERS:
            raise ValueError(
                "CSV headers must exactly match the existing TASK-002 format"
            )
        rows = list(reader)

    if len(rows) != expected_count:
        raise ValueError(
            f"Expected exactly {expected_count} review windows, got {len(rows)}"
        )

    windows: list[ReviewWindow] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        window_id = str(row["窗口"])
        if not window_id:
            raise ValueError(f"row {row_number} has an empty window id")
        if window_id in seen:
            raise ValueError(f"duplicate window id: {window_id}")
        seen.add(window_id)

        start = _finite_float(row["开始秒"], f"row {row_number} start")
        end = _finite_float(row["结束秒"], f"row {row_number} end")
        disagreement = _finite_float(
            row["分歧分"], f"row {row_number} disagreement"
        )
        if start < 0:
            raise ValueError(f"row {row_number} start must be non-negative")
        if end <= start:
            raise ValueError(f"row {row_number} end must be after start")
        if end - audio_duration > TIMESTAMP_ROUNDING_TOLERANCE_SECONDS + 1e-12:
            raise ValueError(f"row {row_number} exceeds the WAV duration")

        texts = {name: row[name] for name in CANDIDATE_COLUMNS}
        if any(not isinstance(text, str) or text == "" for text in texts.values()):
            raise ValueError(f"row {row_number} has an empty candidate text")

        windows.append(
            ReviewWindow(
                window_id=window_id,
                start=start,
                end=end,
                label=row["类型"],
                disagreement=disagreement,
                candidate_texts=texts,
            )
        )
    return windows

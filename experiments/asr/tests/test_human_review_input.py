from __future__ import annotations

import csv
from pathlib import Path

import pytest

from experiments.asr.human_review.input_parser import (
    CSV_HEADERS,
    parse_review_csv,
)


def _rows(count: int = 20) -> list[dict[str, str]]:
    return [
        {
            "窗口": str(index + 1),
            "开始秒": f"{index * 0.5:.3f}",
            "结束秒": f"{index * 0.5 + 0.4:.3f}",
            "类型": "合成窗口",
            "分歧分": "0.1000",
            "SenseVoice": f"候选A-{index}",
            "Paraformer": f"候选B-{index}",
            "Faster-Whisper": f"候选C-{index}",
        }
        for index in range(count)
    ]


def _write_csv(
    path: Path,
    rows: list[dict[str, str]],
    headers: tuple[str, ...] = CSV_HEADERS,
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_parse_exact_20_windows(tmp_path: Path) -> None:
    path = tmp_path / "review.csv"
    _write_csv(path, _rows())

    windows = parse_review_csv(path, audio_duration=10.0)

    assert len(windows) == 20
    assert windows[0].window_id == "1"
    assert windows[-1].window_id == "20"
    assert windows[0].candidate_texts["SenseVoice"] == "候选A-0"


def test_missing_column_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "review.csv"
    headers = CSV_HEADERS[:-1]
    rows = [{key: value for key, value in row.items() if key in headers} for row in _rows()]
    _write_csv(path, rows, headers)

    with pytest.raises(ValueError, match="headers"):
        parse_review_csv(path, audio_duration=10.0)


def test_duplicate_window_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "review.csv"
    rows = _rows()
    rows[1]["窗口"] = rows[0]["窗口"]
    _write_csv(path, rows)

    with pytest.raises(ValueError, match="duplicate"):
        parse_review_csv(path, audio_duration=10.0)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("开始秒", "nan", "finite"),
        ("开始秒", "inf", "finite"),
        ("开始秒", "-0.1", "non-negative"),
        ("结束秒", "0.0", "after start"),
    ],
)
def test_invalid_time_is_rejected(
    tmp_path: Path,
    field: str,
    value: str,
    match: str,
) -> None:
    path = tmp_path / "review.csv"
    rows = _rows()
    rows[0][field] = value
    _write_csv(path, rows)

    with pytest.raises(ValueError, match=match):
        parse_review_csv(path, audio_duration=10.0)


def test_real_out_of_bounds_time_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "review.csv"
    rows = _rows()
    rows[-1]["结束秒"] = "10.001"
    _write_csv(path, rows)

    with pytest.raises(ValueError, match="exceeds"):
        parse_review_csv(path, audio_duration=10.0)


def test_three_decimal_rounding_boundary_is_explicitly_accepted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "review.csv"
    rows = _rows()
    rows[-1]["开始秒"] = "9.900"
    rows[-1]["结束秒"] = "10.000"
    _write_csv(path, rows)

    windows = parse_review_csv(path, audio_duration=9.9996875)

    assert windows[-1].end == 10.0

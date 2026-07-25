"""Schema construction and strict validation for local review exports."""

from __future__ import annotations

import math
from typing import Any, Iterable

from .input_parser import ReviewWindow


SCHEMA_VERSION = "1.0"
REVIEW_TYPE = "asr_human_listening_review"
MODEL_NAMES = ("SenseVoice", "Paraformer", "Faster-Whisper")
BEST_CANDIDATES = (
    "SenseVoice",
    "Paraformer",
    "Faster-Whisper",
    "tie",
    "none",
)
ERROR_TAGS = (
    "漏字/漏词",
    "多字/幻觉",
    "错字/替换",
    "人名/品牌/专名",
    "英文",
    "数字",
    "标点/可读性",
    "非中文异常字符",
    "切点/分段",
    "其他",
)


def initial_window_review(window: ReviewWindow) -> dict[str, Any]:
    return {
        "window_id": window.window_id,
        "start": window.start,
        "end": window.end,
        "best_candidate": None,
        "severity": {name: None for name in MODEL_NAMES},
        "error_tags": {name: [] for name in MODEL_NAMES},
        "reference_text": "",
        "audio_hard_to_hear": False,
        "notes": "",
        "reviewed": False,
    }


def build_export(
    windows: Iterable[ReviewWindow],
    *,
    source_manifest_sha256: str,
) -> dict[str, Any]:
    values = [initial_window_review(window) for window in windows]
    return {
        "schema_version": SCHEMA_VERSION,
        "review_type": REVIEW_TYPE,
        "source_manifest_sha256": source_manifest_sha256,
        "completed": False,
        "completed_window_count": 0,
        "total_window_count": len(values),
        "windows": values,
    }


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def validate_review_export(
    payload: dict[str, Any],
    expected_windows: Iterable[ReviewWindow],
) -> None:
    expected = {window.window_id: window for window in expected_windows}
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if payload.get("review_type") != REVIEW_TYPE:
        raise ValueError("unsupported review_type")
    if not isinstance(payload.get("source_manifest_sha256"), str):
        raise ValueError("source_manifest_sha256 must be a string")
    rows = payload.get("windows")
    if not isinstance(rows, list):
        raise ValueError("windows must be a list")
    if len(rows) != len(expected):
        raise ValueError("review export must include every manifest window exactly once")

    seen: set[str] = set()
    reviewed_count = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"windows[{index}] must be an object")
        window_id = row.get("window_id")
        if window_id not in expected:
            raise ValueError(f"unknown window_id: {window_id}")
        if window_id in seen:
            raise ValueError(f"duplicate window_id: {window_id}")
        seen.add(window_id)
        original = expected[window_id]
        if _finite_number(row.get("start"), f"{window_id}.start") != original.start:
            raise ValueError(f"{window_id}.start does not match the manifest")
        if _finite_number(row.get("end"), f"{window_id}.end") != original.end:
            raise ValueError(f"{window_id}.end does not match the manifest")

        candidate = row.get("best_candidate")
        if candidate is not None and candidate not in BEST_CANDIDATES:
            raise ValueError(f"{window_id} has an unknown best_candidate")
        severity = row.get("severity")
        tags = row.get("error_tags")
        if not isinstance(severity, dict) or set(severity) != set(MODEL_NAMES):
            raise ValueError(f"{window_id}.severity must contain the three models")
        if not isinstance(tags, dict) or set(tags) != set(MODEL_NAMES):
            raise ValueError(f"{window_id}.error_tags must contain the three models")
        for model in MODEL_NAMES:
            level = severity[model]
            if level is not None and (
                isinstance(level, bool)
                or not isinstance(level, int)
                or not 0 <= level <= 3
            ):
                raise ValueError(f"{window_id}.{model} severity must be 0..3")
            model_tags = tags[model]
            if (
                not isinstance(model_tags, list)
                or len(model_tags) != len(set(model_tags))
                or any(tag not in ERROR_TAGS for tag in model_tags)
            ):
                raise ValueError(f"{window_id}.{model} contains unknown error tags")
        if not isinstance(row.get("reference_text"), str):
            raise ValueError(f"{window_id}.reference_text must be a string")
        if not isinstance(row.get("audio_hard_to_hear"), bool):
            raise ValueError(f"{window_id}.audio_hard_to_hear must be boolean")
        if not isinstance(row.get("notes"), str):
            raise ValueError(f"{window_id}.notes must be a string")
        if not isinstance(row.get("reviewed"), bool):
            raise ValueError(f"{window_id}.reviewed must be boolean")
        if row["reviewed"]:
            reviewed_count += 1
            if candidate is None or any(severity[name] is None for name in MODEL_NAMES):
                raise ValueError(
                    f"{window_id} cannot be reviewed without candidate and severities"
                )

    if set(expected) != seen:
        raise ValueError("review export window ids do not match the manifest")
    completed = reviewed_count == len(expected)
    if payload.get("completed_window_count") != reviewed_count:
        raise ValueError("completed_window_count is inconsistent")
    if payload.get("total_window_count") != len(expected):
        raise ValueError("total_window_count is inconsistent")
    if payload.get("completed") is not completed:
        raise ValueError("completed flag is inconsistent")

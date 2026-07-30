"""Build and validate the TASK-003 millisecond timeline."""

from __future__ import annotations

import re
from typing import Any


class TimelineValidationError(ValueError):
    """Raised when a completed timeline would be unsafe to publish."""


def clean_text(text_raw: str) -> str:
    return re.sub(r"\s+", " ", text_raw).strip()


def canonical_segment(
    *,
    start_ms: int,
    end_ms: int,
    text_raw: str,
) -> dict[str, Any] | None:
    text = clean_text(text_raw)
    if not text:
        return None
    return {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "text_raw": text_raw,
        "text": text,
        "speaker": None,
        "is_question": text.endswith(("?", "？")),
        "is_uncertain": False,
    }


def build_timeline(
    *,
    file_name: str,
    duration_ms: int,
    source_sha256: str,
    engine: str,
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered = sorted(segments, key=lambda item: (item["start_ms"], item["end_ms"]))
    numbered = [{"id": index, **segment} for index, segment in enumerate(ordered, 1)]
    timeline = {
        "schema_version": "1.0",
        "source": {
            "file_name": file_name,
            "duration_ms": duration_ms,
            "sha256": source_sha256,
        },
        "asr": {
            "engine": engine,
            "language": "zh",
            "completed": True,
        },
        "segments": numbered,
    }
    validate_timeline(timeline)
    return timeline


def validate_timeline(timeline: dict[str, Any]) -> None:
    if timeline.get("schema_version") != "1.0":
        raise TimelineValidationError("timeline schema_version must be 1.0")
    source = timeline.get("source")
    asr = timeline.get("asr")
    segments = timeline.get("segments")
    if not isinstance(source, dict) or not isinstance(asr, dict):
        raise TimelineValidationError("timeline source and asr must be objects")
    duration_ms = source.get("duration_ms")
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms <= 0:
        raise TimelineValidationError("source.duration_ms must be a positive integer")
    if not isinstance(source.get("file_name"), str) or not source["file_name"]:
        raise TimelineValidationError("source.file_name must be non-empty")
    sha256 = source.get("sha256")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise TimelineValidationError("source.sha256 must be lowercase SHA-256")
    if asr.get("engine") not in {"paraformer", "sensevoice"}:
        raise TimelineValidationError("asr.engine is unsupported")
    if asr.get("language") != "zh" or asr.get("completed") is not True:
        raise TimelineValidationError("completed local Chinese ASR metadata is required")
    if not isinstance(segments, list):
        raise TimelineValidationError("segments must be a list")

    previous_end = 0
    for expected_id, segment in enumerate(segments, 1):
        if not isinstance(segment, dict) or segment.get("id") != expected_id:
            raise TimelineValidationError("segment ids must be continuous integers")
        start_ms = segment.get("start_ms")
        end_ms = segment.get("end_ms")
        if (
            isinstance(start_ms, bool)
            or isinstance(end_ms, bool)
            or not isinstance(start_ms, int)
            or not isinstance(end_ms, int)
            or start_ms < 0
            or end_ms <= start_ms
            or end_ms > duration_ms
        ):
            raise TimelineValidationError("segment has an invalid time range")
        if start_ms < previous_end:
            raise TimelineValidationError("segment time ranges must not overlap")
        previous_end = end_ms
        for key in ("text_raw", "text"):
            if not isinstance(segment.get(key), str) or not segment[key].strip():
                raise TimelineValidationError(f"segment.{key} must be non-empty")
        if segment.get("speaker") is not None:
            raise TimelineValidationError("speaker must be null without reliable evidence")
        if not isinstance(segment.get("is_question"), bool) or not isinstance(
            segment.get("is_uncertain"), bool
        ):
            raise TimelineValidationError("segment flags must be booleans")

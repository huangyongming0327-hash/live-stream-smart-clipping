"""Shared artifact, validation, and formatting helpers for TASK-002."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable


class TimelineUnavailableError(RuntimeError):
    """Raised after preserving artifacts for a result with no usable timeline."""


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: str | Path, text: str) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False, dir=target.parent,
        prefix=f".{target.name}.", suffix=".tmp"
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def atomic_write_json(path: str | Path, value: Any) -> Path:
    return atomic_write_text(
        path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )


def format_srt_timestamp(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("SRT timestamp must be finite and non-negative")
    total_ms = int(math.floor(seconds * 1000.0 + 0.5))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def render_srt(segments: Iterable[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        blocks.append(
            "\n".join(
                (
                    str(index),
                    f"{format_srt_timestamp(float(segment['start']))} --> "
                    f"{format_srt_timestamp(float(segment['end']))}",
                    text,
                )
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def new_segment(
    *,
    start: float,
    end: float,
    text: str,
    raw_text: str | None = None,
    confidence: float | None = None,
    language: str | None = None,
    speaker: str | None = None,
    events: list[str] | None = None,
    emotion: str | None = None,
    words: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": "",
        "start": float(start),
        "end": float(end),
        "text": text,
        "raw_text": text if raw_text is None else raw_text,
        "confidence": confidence,
        "language": language,
        "speaker": speaker,
        "events": list(events or []),
        "emotion": emotion,
        "words": list(words or []),
    }


def build_unified_result(
    *,
    candidate: str,
    model_name: str,
    model_revision: str,
    runtime_version: str,
    compute_type: str,
    input_sha256: str,
    segments: list[dict[str, Any]],
    warnings: list[Any] | None = None,
    errors: list[Any] | None = None,
) -> dict[str, Any]:
    ordered = sorted(segments, key=lambda item: (float(item["start"]), float(item["end"])))
    for index, segment in enumerate(ordered, start=1):
        segment["id"] = f"seg-{index:04d}"
    return {
        "candidate": candidate,
        "model_name": model_name,
        "model_revision": model_revision,
        "runtime_version": runtime_version,
        "device": "cpu",
        "compute_type": compute_type,
        "input_sha256": input_sha256,
        "segments": ordered,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def validate_unified_result(result: dict[str, Any], audio_duration: float) -> None:
    duration = _finite_number(audio_duration, "audio_duration")
    if duration <= 0:
        raise ValueError("audio_duration must be positive")
    required = {
        "candidate", "model_name", "model_revision", "runtime_version", "device",
        "compute_type", "input_sha256", "segments", "warnings", "errors"
    }
    missing = required.difference(result)
    if missing:
        raise ValueError(f"unified result is missing fields: {sorted(missing)}")
    if result["device"] != "cpu":
        raise ValueError("TASK-002 only accepts cpu results")
    if not isinstance(result["segments"], list):
        raise ValueError("segments must be a list")
    if not isinstance(result["warnings"], list) or not isinstance(result["errors"], list):
        raise ValueError("warnings and errors must be lists")
    timeline_status = result.get("timeline_status")
    if timeline_status not in (None, "partial", "unavailable"):
        raise ValueError("timeline_status must be partial or unavailable when present")
    if timeline_status == "unavailable" and result["segments"]:
        raise ValueError("an unavailable timeline cannot contain segments")
    if timeline_status == "partial" and not result["segments"]:
        raise ValueError("a partial timeline must contain at least one segment")
    seen_ids: set[str] = set()
    previous_start = -1.0
    previous_end = -1.0
    for index, segment in enumerate(result["segments"]):
        label = f"segments[{index}]"
        segment_id = segment.get("id")
        if not isinstance(segment_id, str) or not segment_id or segment_id in seen_ids:
            raise ValueError(f"{label}.id must be non-empty and unique")
        seen_ids.add(segment_id)
        start = _finite_number(segment.get("start"), f"{label}.start")
        end = _finite_number(segment.get("end"), f"{label}.end")
        if start < 0 or end <= start or end > duration + 0.001:
            raise ValueError(f"{label} has an invalid or out-of-bounds time range")
        if start < previous_start or end < previous_end:
            raise ValueError(f"{label} timestamps are not monotonic")
        previous_start, previous_end = start, end
        if not isinstance(segment.get("text"), str) or not isinstance(segment.get("raw_text"), str):
            raise ValueError(f"{label} text fields must be strings")
        confidence = segment.get("confidence")
        if confidence is not None:
            confidence = _finite_number(confidence, f"{label}.confidence")
            if not 0 <= confidence <= 1:
                raise ValueError(f"{label}.confidence must be within 0..1")
        words = segment.get("words")
        if not isinstance(words, list):
            raise ValueError(f"{label}.words must be a list")
        word_start = start
        word_end = start
        for word_index, word in enumerate(words):
            word_label = f"{label}.words[{word_index}]"
            ws = _finite_number(word.get("start"), f"{word_label}.start")
            we = _finite_number(word.get("end"), f"{word_label}.end")
            if ws < start - 0.001 or we <= ws or we > end + 0.001:
                raise ValueError(f"{word_label} is outside its segment")
            if ws < word_start - 0.001 or we < word_end - 0.001:
                raise ValueError(f"{word_label} timestamps are not monotonic")
            word_start, word_end = ws, we


def write_run_artifacts(
    output_dir: str | Path,
    *,
    raw: Any,
    unified: dict[str, Any],
    metrics: dict[str, Any],
    audio_duration: float,
) -> None:
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    validate_unified_result(unified, audio_duration)
    timeline_unavailable = unified.get("timeline_status") == "unavailable"
    written_metrics = dict(metrics)
    if timeline_unavailable:
        written_metrics["success"] = False
        written_metrics["timeline_status"] = "unavailable"
    atomic_write_json(destination / "raw.json", raw)
    atomic_write_json(destination / "unified.json", unified)
    atomic_write_json(destination / "metrics.json", written_metrics)
    srt_path = destination / "transcript.srt"
    if timeline_unavailable:
        srt_path.unlink(missing_ok=True)
    else:
        atomic_write_text(srt_path, render_srt(unified["segments"]))
    atomic_write_text(
        destination / "transcript.txt",
        "\n".join(segment["text"] for segment in unified["segments"] if segment["text"]).strip()
        + ("\n" if unified["segments"] else ""),
    )
    if timeline_unavailable:
        raise TimelineUnavailableError(
            "Candidate produced text but no usable model-provided timeline"
        )


def assess_silence(unified: dict[str, Any]) -> dict[str, Any]:
    texts = [str(item.get("text") or "").strip() for item in unified.get("segments", [])]
    nonempty = [text for text in texts if text]
    return {
        "hallucination_detected": bool(nonempty),
        "nonempty_segment_count": len(nonempty),
        "text": " ".join(nonempty),
    }


def tree_size(path: str | Path) -> int:
    root = Path(path)
    if not root.exists():
        return 0
    if root.is_file():
        return root.stat().st_size
    total = 0
    for item in root.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total

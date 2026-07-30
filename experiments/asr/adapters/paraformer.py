"""Official FunASR Paraformer/VAD/punctuation CPU adapter."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from liveclip.asr.adapters import ParaformerAdapter

from ..common import atomic_write_json, build_unified_result, new_segment, sha256_file
from .base import execute_run


_MISSING = object()


@dataclass(frozen=True)
class SegmentExtraction:
    segments: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    timeline_status: str | None


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    return str(value)


def _millisecond_range(
    start_value: Any,
    end_value: Any,
    duration: float,
    *,
    missing_reason: str,
    invalid_reason: str,
) -> tuple[tuple[float, float] | None, str | None]:
    if start_value is _MISSING or end_value is _MISSING:
        return None, missing_reason
    if start_value is None or end_value is None:
        return None, missing_reason
    if (
        isinstance(start_value, bool)
        or isinstance(end_value, bool)
        or not isinstance(start_value, (int, float))
        or not isinstance(end_value, (int, float))
    ):
        return None, invalid_reason
    start_ms = float(start_value)
    end_ms = float(end_value)
    if not math.isfinite(start_ms) or not math.isfinite(end_ms):
        return None, "timestamp_non_finite"
    if end_ms <= start_ms:
        return None, "timestamp_reversed"
    start = start_ms / 1000.0
    end = end_ms / 1000.0
    if start < 0 or end > duration:
        return None, "timestamp_out_of_bounds"
    return (start, end), None


def _timestamp_range(
    timestamps: Any,
    duration: float,
) -> tuple[tuple[float, float] | None, str, dict[str, float] | None]:
    if timestamps is _MISSING or timestamps is None:
        return None, "timestamp_missing", None
    if not isinstance(timestamps, list):
        return None, "timestamp_invalid_format", None
    if not timestamps:
        return None, "timestamp_empty", None

    parsed: list[tuple[float, float]] = []
    previous_range: tuple[float, float] | None = None
    for pair in timestamps:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            return None, "timestamp_invalid_format", None
        time_range, reason = _millisecond_range(
            pair[0],
            pair[1],
            duration,
            missing_reason="timestamp_invalid_format",
            invalid_reason="timestamp_invalid_format",
        )
        if reason is not None:
            return None, reason, None
        assert time_range is not None
        order_details = _source_order_issue_details(time_range, previous_range)
        if order_details is not None:
            return None, "timestamp_non_monotonic", order_details
        parsed.append(time_range)
        previous_range = time_range
    return (parsed[0][0], parsed[-1][1]), "", None


def _source_order_issue_details(
    current_range: tuple[float, float],
    previous_range: tuple[float, float] | None,
) -> dict[str, float] | None:
    if previous_range is None:
        return None
    start, end = current_range
    previous_start, previous_end = previous_range
    if start >= previous_start and end >= previous_end:
        return None
    return {
        "start": start,
        "end": end,
        "previous_start": previous_start,
        "previous_end": previous_end,
    }


def _issue(
    *,
    raw_index: int,
    reason: str,
    sentence_index: int | None = None,
    order_details: dict[str, float] | None = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {
        "raw_index": raw_index,
        "reason": reason,
        "raw_text_preserved": True,
    }
    if sentence_index is not None:
        issue["sentence_index"] = sentence_index
    if order_details is not None:
        issue.update(order_details)
        issue["timestamp_unit"] = "seconds"
    return issue


def _structured_issues(
    issues: list[dict[str, Any]],
    *,
    segment_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    if not issues:
        return [], [], None

    timeline_status = "partial" if segment_count else "unavailable"
    raw_indices = sorted({int(item["raw_index"]) for item in issues})
    warnings = [
        {
            "code": "PARAFORMER_UNTIMED_TEXT_EXCLUDED",
            "message": "Text without valid model timing was excluded from timeline segments.",
            "timeline_status": timeline_status,
            "untimed_text_count": len(issues),
            "raw_indices": raw_indices,
            "raw_text_preserved": True,
            "entries": issues,
        }
    ]
    errors: list[dict[str, Any]] = []
    missing_reasons = {"timestamp_missing", "timestamp_empty"}
    for code, selected in (
        (
            "PARAFORMER_TIMESTAMP_MISSING",
            [item for item in issues if item["reason"] in missing_reasons],
        ),
        (
            "PARAFORMER_TIMESTAMP_INVALID",
            [item for item in issues if item["reason"] not in missing_reasons],
        ),
    ):
        if not selected:
            continue
        errors.append(
            {
                "code": code,
                "message": "Paraformer text has no usable model-provided timestamp.",
                "timeline_status": timeline_status,
                "untimed_text_count": len(selected),
                "raw_indices": sorted({int(item["raw_index"]) for item in selected}),
                "entries": selected,
            }
        )
    return warnings, errors, timeline_status


def _segments_from_result(result: list[dict[str, Any]], duration: float) -> SegmentExtraction:
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    segments: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    previous_accepted_range: tuple[float, float] | None = None
    for raw_index, item in enumerate(result):
        sentence_info = item.get("sentence_info", _MISSING)
        if isinstance(sentence_info, list) and sentence_info:
            saw_sentence_text = False
            for sentence_index, sentence in enumerate(sentence_info):
                if not isinstance(sentence, dict):
                    continue
                text = str(sentence.get("text") or "").strip()
                if not text:
                    continue
                saw_sentence_text = True
                time_range, reason = _millisecond_range(
                    sentence.get("start", _MISSING),
                    sentence.get("end", _MISSING),
                    duration,
                    missing_reason="timestamp_missing",
                    invalid_reason="timestamp_invalid_format",
                )
                if reason is not None:
                    issues.append(
                        _issue(
                            raw_index=raw_index,
                            sentence_index=sentence_index,
                            reason=reason,
                        )
                    )
                    continue
                assert time_range is not None
                start, end = time_range
                order_details = _source_order_issue_details(
                    time_range,
                    previous_accepted_range,
                )
                if order_details is not None:
                    issues.append(
                        _issue(
                            raw_index=raw_index,
                            sentence_index=sentence_index,
                            reason="timestamp_non_monotonic",
                            order_details=order_details,
                        )
                    )
                    continue
                speaker = sentence.get("spk")
                segments.append(
                    new_segment(
                        start=start, end=end, text=text, raw_text=text,
                        speaker=(f"spk{speaker}" if speaker is not None else None),
                        words=[]
                    )
                )
                previous_accepted_range = time_range
            if saw_sentence_text:
                continue

        text = str(item.get("text") or "").strip()
        if not text:
            continue
        time_range, reason, order_details = _timestamp_range(
            item.get("timestamp", _MISSING),
            duration,
        )
        if time_range is None:
            issues.append(
                _issue(
                    raw_index=raw_index,
                    reason=reason,
                    order_details=order_details,
                )
            )
            continue
        start, end = time_range
        order_details = _source_order_issue_details(
            time_range,
            previous_accepted_range,
        )
        if order_details is not None:
            issues.append(
                _issue(
                    raw_index=raw_index,
                    reason="timestamp_non_monotonic",
                    order_details=order_details,
                )
            )
            continue
        segments.append(new_segment(start=start, end=end, text=text, words=[]))
        previous_accepted_range = time_range

    warnings, errors, timeline_status = _structured_issues(
        issues,
        segment_count=len(segments),
    )
    return SegmentExtraction(
        segments=segments,
        warnings=warnings,
        errors=errors,
        timeline_status=timeline_status,
    )


def _build_paraformer_unified(
    result: list[dict[str, Any]],
    duration: float,
    *,
    runtime_version: str,
    input_sha256: str,
) -> dict[str, Any]:
    extraction = _segments_from_result(result, duration)
    warnings: list[Any] = list(extraction.warnings)
    if extraction.segments and not any(item.get("sentence_info") for item in result):
        warnings.insert(
            0,
            "FunASR did not return sentence_info; fallback timestamp granularity was used.",
        )
    unified = build_unified_result(
        candidate="paraformer-zh-funasr",
        model_name="paraformer-zh + fsmn-vad + ct-punc",
        model_revision="paraformer-v2.0.9/vad-v2.0.4/punc-v2.0.4",
        runtime_version=runtime_version,
        compute_type="float32",
        input_sha256=input_sha256,
        segments=extraction.segments,
        warnings=warnings,
        errors=extraction.errors,
    )
    if extraction.timeline_status is not None:
        unified["timeline_status"] = extraction.timeline_status
    return unified


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-kind", choices=("cold", "warm", "offline"), required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--probe-audio", required=True)
    parser.add_argument("--silence", required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--vad-model", required=True)
    parser.add_argument("--punc-model", required=True)
    parser.add_argument("--hotwords", default="直播 智能切片 人工智能 AI")
    args = parser.parse_args()

    paths = [Path(value).resolve() for value in (args.model, args.vad_model, args.punc_model)]
    for required in paths:
        if not required.is_dir():
            raise FileNotFoundError(required)
    def load_model() -> tuple[Any, str]:
        adapter = ParaformerAdapter(paths[0].parent)
        return adapter, adapter.runtime_version

    def transcribe_factory(model: ParaformerAdapter):
        def transcribe(path: str | Path) -> tuple[Any, dict[str, Any]]:
            import wave

            with wave.open(str(path), "rb") as handle:
                duration = handle.getnframes() / handle.getframerate()
            safe_result = model.generate_raw(Path(path))
            unified = _build_paraformer_unified(
                safe_result,
                duration,
                runtime_version=getattr(funasr, "__version__", "1.3.22"),
                input_sha256=sha256_file(path),
            )
            return safe_result, unified

        return transcribe

    def extra_probe(model: ParaformerAdapter) -> dict[str, Any]:
        result = model.generate_raw(Path(args.probe_audio), hotword=args.hotwords)
        probe_path = Path(args.output_dir).resolve() / "hotword-probe.raw.json"
        atomic_write_json(probe_path, result)
        return {
            "hotwords": args.hotwords.split(),
            "audio": str(Path(args.probe_audio).resolve()),
            "raw_output": str(probe_path),
            "text": " ".join(str(item.get("text") or "") for item in result),
            "single_hotword_run": True,
        }

    execute_run(
        output_dir=args.output_dir, run_kind=args.run_kind, audio_path=args.audio,
        probe_audio_path=args.probe_audio, silence_path=args.silence,
        audio_duration=args.duration, load_model=load_model,
        transcribe_factory=transcribe_factory,
        candidate="paraformer-zh-funasr",
        model_name="paraformer-zh + fsmn-vad + ct-punc",
        model_revision="paraformer-v2.0.9/vad-v2.0.4/punc-v2.0.4",
        compute_type="float32", extra_probe=(extra_probe if args.run_kind == "warm" else None)
    )


if __name__ == "__main__":
    main()

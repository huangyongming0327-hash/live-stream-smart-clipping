"""Validation, score calculation, and timeline-derived analysis fields."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from liveclip.asr.timeline import validate_timeline


SCORE_LIMITS = {
    "content_value": 25,
    "problem_solving": 20,
    "emotion_or_reversal": 15,
    "information_density": 15,
    "hook_and_shareability": 15,
    "completeness": 10,
}
RISK_LIMIT = 30
MODEL_TOPIC_KEYS = {
    "start_segment_id",
    "end_segment_id",
    "title",
    "summary",
}
MODEL_CANDIDATE_KEYS = {
    "start_segment_id",
    "end_segment_id",
    "title",
    "reason",
    "quote_segment_id",
    *SCORE_LIMITS,
    "risk_penalty",
}


class AnalysisError(RuntimeError):
    """Base error that is safe to print as one line."""


class ModelResponseError(AnalysisError):
    """Raised when model JSON cannot be trusted."""


def load_timeline(path: str | Path) -> tuple[Path, dict[str, Any], bytes]:
    timeline_path = Path(path).expanduser().resolve()
    if not timeline_path.is_file():
        raise AnalysisError(f"timeline 不存在: {timeline_path}")
    try:
        raw = timeline_path.read_bytes()
        timeline = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"timeline 无法读取或 JSON 损坏: {type(exc).__name__}") from None
    if not isinstance(timeline, dict):
        raise AnalysisError("timeline 顶层必须是 JSON 对象")
    try:
        validate_timeline(timeline)
    except ValueError as exc:
        raise AnalysisError(f"timeline 校验失败: {exc}") from None
    return timeline_path, timeline, raw


def parse_model_response(
    content: str,
    *,
    window_segments: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {"```", "```json"}:
            text = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        raise ModelResponseError("模型输出不是合法 JSON") from None
    return validate_model_payload(payload, window_segments=window_segments)


def validate_model_payload(
    payload: Any,
    *,
    window_segments: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict) or set(payload) != {"topics", "candidates"}:
        raise ModelResponseError("模型输出必须且只能包含 topics 和 candidates")
    topics = payload["topics"]
    candidates = payload["candidates"]
    if not isinstance(topics, list) or not isinstance(candidates, list):
        raise ModelResponseError("topics 和 candidates 必须是数组")
    if len(candidates) > 3:
        raise ModelResponseError("每个窗口最多返回 3 个 candidates")

    segment_by_id = {segment["id"]: segment for segment in window_segments}
    if len(segment_by_id) != len(window_segments):
        raise ModelResponseError("窗口 segment ID 不唯一")

    clean_topics: list[dict[str, Any]] = []
    previous_end = 0
    for topic in topics:
        _require_exact_keys(topic, MODEL_TOPIC_KEYS, "topic")
        start_id, end_id = _validate_range(topic, segment_by_id, "topic")
        if clean_topics and start_id <= previous_end:
            raise ModelResponseError("同一窗口 topic 不得重叠")
        previous_end = end_id
        clean_topics.append(
            {
                "start_segment_id": start_id,
                "end_segment_id": end_id,
                "title": _nonempty_string(topic["title"], "topic.title"),
                "summary": _nonempty_string(topic["summary"], "topic.summary"),
            }
        )

    clean_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        _require_exact_keys(candidate, MODEL_CANDIDATE_KEYS, "candidate")
        start_id, end_id = _validate_range(candidate, segment_by_id, "candidate")
        quote_id = candidate["quote_segment_id"]
        if (
            isinstance(quote_id, bool)
            or not isinstance(quote_id, int)
            or quote_id < start_id
            or quote_id > end_id
        ):
            raise ModelResponseError("quote_segment_id 必须位于 candidate 范围内")
        containing_topics = [
            topic
            for topic in clean_topics
            if topic["start_segment_id"] <= start_id
            and topic["end_segment_id"] >= end_id
        ]
        if len(containing_topics) != 1:
            raise ModelResponseError("candidate 必须完整属于一个 topic")
        duration_ms = (
            segment_by_id[end_id]["end_ms"] - segment_by_id[start_id]["start_ms"]
        )
        if not 15_000 <= duration_ms <= 180_000:
            raise ModelResponseError("candidate 时长必须为 15—180 秒")

        clean_candidate: dict[str, Any] = {
            "start_segment_id": start_id,
            "end_segment_id": end_id,
            "title": _nonempty_string(candidate["title"], "candidate.title"),
            "reason": _nonempty_string(candidate["reason"], "candidate.reason"),
            "quote_segment_id": quote_id,
        }
        for name, maximum in SCORE_LIMITS.items():
            clean_candidate[name] = _bounded_number(candidate[name], name, maximum)
        clean_candidate["risk_penalty"] = _bounded_number(
            candidate["risk_penalty"],
            "risk_penalty",
            RISK_LIMIT,
        )
        clean_candidates.append(clean_candidate)
    return {"topics": clean_topics, "candidates": clean_candidates}


def score_candidate(candidate: dict[str, Any]) -> float | int:
    score = sum(candidate[name] for name in SCORE_LIMITS) - candidate["risk_penalty"]
    bounded = max(0, min(100, score))
    return int(bounded) if float(bounded).is_integer() else bounded


def validate_analysis(
    analysis: Any,
    *,
    timeline: dict[str, Any],
) -> None:
    if not isinstance(analysis, dict) or set(analysis) != {
        "schema_version",
        "source",
        "analysis",
        "topics",
        "candidates",
    }:
        raise AnalysisError("analysis 顶层结构无效")
    if analysis["schema_version"] != "1.0":
        raise AnalysisError("analysis schema_version 必须是 1.0")
    source = analysis["source"]
    metadata = analysis["analysis"]
    topics = analysis["topics"]
    candidates = analysis["candidates"]
    if not isinstance(source, dict) or not isinstance(metadata, dict):
        raise AnalysisError("analysis source 和 analysis 必须是对象")
    if set(source) != {
        "timeline_file_name",
        "timeline_sha256",
        "video_file_name",
        "duration_ms",
    }:
        raise AnalysisError("analysis source 字段结构无效")
    if (
        not isinstance(source["timeline_file_name"], str)
        or not source["timeline_file_name"]
        or not isinstance(source["video_file_name"], str)
        or not source["video_file_name"]
        or not isinstance(source["timeline_sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", source["timeline_sha256"]) is None
        or source["duration_ms"] != timeline["source"]["duration_ms"]
        or source["video_file_name"] != timeline["source"]["file_name"]
    ):
        raise AnalysisError("analysis source 元数据无效")
    if set(metadata) != {
        "provider",
        "model",
        "completed",
        "generated_at",
        "window_count",
    }:
        raise AnalysisError("analysis 元数据字段结构无效")
    if metadata.get("completed") is not True:
        raise AnalysisError("analysis 只有全部窗口完成后才能发布")
    if (
        metadata.get("provider") != "openai_compatible"
        or not isinstance(metadata.get("model"), str)
        or not metadata["model"]
        or isinstance(metadata.get("window_count"), bool)
        or not isinstance(metadata.get("window_count"), int)
        or metadata["window_count"] < 0
    ):
        raise AnalysisError("analysis 模型或窗口元数据无效")
    generated_at = metadata.get("generated_at")
    if not isinstance(generated_at, str):
        raise AnalysisError("analysis generated_at 必须是 UTC 时间")
    try:
        parsed_generated_at = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        raise AnalysisError("analysis generated_at 必须是 UTC 时间") from None
    if parsed_generated_at.utcoffset() is None or parsed_generated_at.utcoffset().total_seconds() != 0:
        raise AnalysisError("analysis generated_at 必须是 UTC 时间")
    if not isinstance(topics, list) or not isinstance(candidates, list):
        raise AnalysisError("analysis topics 和 candidates 必须是数组")

    segment_by_id = {segment["id"]: segment for segment in timeline["segments"]}
    topic_by_id: dict[str, dict[str, Any]] = {}
    previous_topic_end = 0
    for topic in topics:
        topic_id = topic.get("id") if isinstance(topic, dict) else None
        if not isinstance(topic, dict) or set(topic) != {
            "id",
            "start_segment_id",
            "end_segment_id",
            "start_ms",
            "end_ms",
            "title",
            "summary",
        }:
            raise AnalysisError("topic 字段结构无效")
        if not isinstance(topic_id, str) or not topic_id or topic_id in topic_by_id:
            raise AnalysisError("topic ID 必须是唯一非空字符串")
        _validate_derived_range(topic, segment_by_id, "topic")
        if topic["start_segment_id"] <= previous_topic_end:
            raise AnalysisError("topic 范围不得重叠")
        previous_topic_end = topic["end_segment_id"]
        for name in ("title", "summary"):
            _nonempty_string(topic.get(name), f"topic.{name}")
        topic_by_id[topic_id] = topic

    if len(candidates) > 20:
        raise AnalysisError("全视频最多 20 个 candidates")
    candidate_ids: set[str] = set()
    expected_order = sorted(
        candidates,
        key=lambda item: (-item["total_score"], item["start_ms"]),
    )
    if candidates != expected_order:
        raise AnalysisError("candidates 排序无效")
    for candidate in candidates:
        candidate_id = candidate.get("id") if isinstance(candidate, dict) else None
        expected_candidate_keys = {
            "id",
            "topic_id",
            "start_segment_id",
            "end_segment_id",
            "start_ms",
            "end_ms",
            "duration_ms",
            "title",
            "reason",
            "quote_segment_id",
            "quote",
            *SCORE_LIMITS,
            "risk_penalty",
            "total_score",
            "recommended",
        }
        if not isinstance(candidate, dict) or set(candidate) != expected_candidate_keys:
            raise AnalysisError("candidate 字段结构无效")
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in candidate_ids:
            raise AnalysisError("candidate ID 必须是唯一非空字符串")
        candidate_ids.add(candidate_id)
        _validate_derived_range(candidate, segment_by_id, "candidate")
        duration = candidate["end_ms"] - candidate["start_ms"]
        if candidate.get("duration_ms") != duration or not 15_000 <= duration <= 180_000:
            raise AnalysisError("candidate 时长必须为 15—180 秒")
        topic = topic_by_id.get(candidate.get("topic_id"))
        if (
            topic is None
            or candidate["start_segment_id"] < topic["start_segment_id"]
            or candidate["end_segment_id"] > topic["end_segment_id"]
        ):
            raise AnalysisError("candidate topic 引用无效")
        for name in ("title", "reason"):
            try:
                _nonempty_string(candidate.get(name), f"candidate.{name}")
            except ModelResponseError as exc:
                raise AnalysisError(str(exc)) from None
        quote_id = candidate.get("quote_segment_id")
        if (
            isinstance(quote_id, bool)
            or not isinstance(quote_id, int)
            or not candidate["start_segment_id"] <= quote_id <= candidate["end_segment_id"]
            or candidate.get("quote") != segment_by_id[quote_id]["text"]
        ):
            raise AnalysisError("candidate quote 必须来自真实范围内 segment")
        for name, maximum in SCORE_LIMITS.items():
            _bounded_number(candidate.get(name), name, maximum)
        _bounded_number(candidate.get("risk_penalty"), "risk_penalty", RISK_LIMIT)
        expected_score = score_candidate(candidate)
        if candidate.get("total_score") != expected_score:
            raise AnalysisError("candidate total_score 必须由程序计算")
        if candidate.get("recommended") is not (expected_score >= 75):
            raise AnalysisError("candidate recommended 与总分不一致")
        if expected_score < 60:
            raise AnalysisError("60 分以下 candidate 不得发布")

    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            if overlap_ratio(left, right) > 0.6:
                raise AnalysisError("发布 candidates 存在超过 60% 的重叠")


def overlap_ratio(left: dict[str, Any], right: dict[str, Any]) -> float:
    overlap = max(
        0,
        min(left["end_ms"], right["end_ms"])
        - max(left["start_ms"], right["start_ms"]),
    )
    shorter = min(left["duration_ms"], right["duration_ms"])
    return overlap / shorter if shorter else 0.0


def _require_exact_keys(value: Any, keys: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ModelResponseError(f"{label} 字段结构无效")


def _validate_range(
    value: dict[str, Any],
    segment_by_id: dict[int, dict[str, Any]],
    label: str,
) -> tuple[int, int]:
    start_id = value["start_segment_id"]
    end_id = value["end_segment_id"]
    if (
        isinstance(start_id, bool)
        or isinstance(end_id, bool)
        or not isinstance(start_id, int)
        or not isinstance(end_id, int)
        or start_id > end_id
        or start_id not in segment_by_id
        or end_id not in segment_by_id
    ):
        raise ModelResponseError(f"{label} segment 范围无效")
    expected = list(range(start_id, end_id + 1))
    if any(segment_id not in segment_by_id for segment_id in expected):
        raise ModelResponseError(f"{label} 必须引用连续 segment")
    return start_id, end_id


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelResponseError(f"{label} 必须是非空字符串")
    return value


def _bounded_number(value: Any, label: str, maximum: int) -> float | int:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        or value > maximum
    ):
        raise ModelResponseError(f"{label} 必须在 0—{maximum} 范围内")
    return value


def _validate_derived_range(
    value: dict[str, Any],
    segment_by_id: dict[int, dict[str, Any]],
    label: str,
) -> None:
    try:
        start_id, end_id = _validate_range(value, segment_by_id, label)
    except ModelResponseError as exc:
        raise AnalysisError(str(exc)) from None
    if (
        value.get("start_ms") != segment_by_id[start_id]["start_ms"]
        or value.get("end_ms") != segment_by_id[end_id]["end_ms"]
    ):
        raise AnalysisError(f"{label} 时间必须由真实 segment 计算")

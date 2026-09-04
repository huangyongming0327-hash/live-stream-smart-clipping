"""Sequential window analysis, recovery, merge, and three-version publishing."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from liveclip.asr.exporters import atomic_write_json, atomic_write_text

from .client import LLMConfig, OpenAICompatibleClient, load_config
from .schema import (
    AnalysisError,
    ModelResponseError,
    SCORE_LIMITS,
    load_timeline,
    overlap_ratio,
    parse_model_response,
    parse_repaired_model_response,
    score_candidate,
    validate_analysis,
    validate_model_payload,
)


MAX_WINDOW_DURATION_MS = 600_000
MAX_WINDOW_CHARACTERS = 12_000
MAX_CANDIDATES = 20
STATE_SCHEMA_VERSION = "1.0"
PRIVACY_NOTICE = "仅字幕文本会发送到你配置的文本模型API；视频和音频不会上传。"


class AnalysisClient(Protocol):
    config: LLMConfig
    request_count: int

    def analyze_window(
        self,
        segments: list[dict[str, Any]],
        *,
        repair_error: str | None = None,
        previous_response: str | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class AnalysisResult:
    output_path: Path
    window_count: int
    request_count: int
    elapsed_seconds: float
    topic_count: int
    candidate_count: int
    recommended_count: int
    resumed_from_window: int


def build_windows(
    segments: list[dict[str, Any]],
    *,
    max_duration_ms: int = MAX_WINDOW_DURATION_MS,
    max_characters: int = MAX_WINDOW_CHARACTERS,
) -> list[list[dict[str, Any]]]:
    if (
        isinstance(max_duration_ms, bool)
        or isinstance(max_characters, bool)
        or not isinstance(max_duration_ms, int)
        or not isinstance(max_characters, int)
        or max_duration_ms <= 0
        or max_characters <= 0
    ):
        raise AnalysisError("窗口参数必须是正整数")
    windows: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    characters = 0
    for segment in segments:
        text_length = len(segment["text"])
        exceeds = bool(current) and (
            segment["end_ms"] - current[0]["start_ms"] > max_duration_ms
            or characters + text_length > max_characters
        )
        if exceeds:
            windows.append(current)
            current = []
            characters = 0
        current.append(segment)
        characters += text_length
    if current:
        windows.append(current)
    return windows


def run_analysis(
    timeline_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    client: AnalysisClient | None = None,
    environ: Mapping[str, str] | None = None,
    progress: Callable[[str], None] = print,
) -> AnalysisResult:
    started = time.monotonic()
    resolved_timeline_path, timeline, raw_timeline = load_timeline(timeline_path)
    timeline_sha256 = hashlib.sha256(raw_timeline).hexdigest()
    destination = (
        Path(output_dir).expanduser().resolve()
        if output_dir is not None
        else resolved_timeline_path.parent
    )
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AnalysisError(f"输出目录不可写: {type(exc).__name__}") from None

    windows = build_windows(timeline["segments"])
    progress(
        f"输入检查: timeline 有效，segments={len(timeline['segments'])}，"
        f"windows={len(windows)}"
    )

    if windows:
        if client is None:
            config = load_config(environ)
            client = OpenAICompatibleClient(config)
        else:
            config = client.config
    else:
        configured_model = ""
        if environ is not None:
            configured_model = str(environ.get("LIVECLIP_LLM_MODEL", "")).strip()
        else:
            configured_model = os.environ.get("LIVECLIP_LLM_MODEL", "").strip()
        config = LLMConfig(
            endpoint="",
            api_key="",
            model=configured_model or "not_used",
            endpoint_host="",
        )

    fingerprint = {
        "timeline_sha256": timeline_sha256,
        "endpoint_host": config.endpoint_host,
        "model": config.model,
        "window_max_duration_ms": MAX_WINDOW_DURATION_MS,
        "window_max_characters": MAX_WINDOW_CHARACTERS,
    }
    work_dir = destination / ".analysis_work"
    state_path = work_dir / "analysis_state.json"
    state = _load_or_create_state(
        state_path,
        fingerprint=fingerprint,
        windows=windows,
    )
    completed = state["completed_window_count"]
    resumed_from = completed + 1 if windows else 0
    progress(
        "恢复位置: "
        + (f"窗口 {resumed_from}/{len(windows)}" if windows else "无需模型请求")
    )

    request_count_before = getattr(client, "request_count", 0) if client is not None else 0
    notice_printed = False
    for window_index in range(completed, len(windows)):
        if not notice_printed:
            progress(PRIVACY_NOTICE)
            notice_printed = True
        progress(f"分析窗口: {window_index + 1}/{len(windows)}")
        window = windows[window_index]
        assert client is not None
        content = client.analyze_window(window)
        try:
            parsed = parse_model_response(content, window_segments=window)
        except ModelResponseError as first_error:
            repair_content = client.analyze_window(
                window,
                repair_error=str(first_error),
                previous_response=content,
            )
            try:
                parsed = parse_repaired_model_response(
                    repair_content,
                    window_segments=window,
                )
            except ModelResponseError as second_error:
                raise AnalysisError(
                    f"模型输出修复重试后仍无效: {second_error}"
                ) from None
        state["window_results"].append(parsed)
        state["completed_window_count"] = window_index + 1
        try:
            work_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(state_path, state)
        except OSError as exc:
            raise AnalysisError(f"分析进度无法保存: {type(exc).__name__}") from None
        progress(
            f"窗口完成: {window_index + 1}/{len(windows)}，"
            f"已用时间={time.monotonic() - started:.2f}s"
        )

    output = _build_output(
        timeline=timeline,
        timeline_file_name=resolved_timeline_path.name,
        timeline_sha256=timeline_sha256,
        model=config.model,
        window_results=state["window_results"],
    )
    validate_analysis(output, timeline=timeline)
    output_path = publish_analysis(destination, output, timeline=timeline)
    _cleanup_work_state(work_dir, state_path)

    request_count_after = getattr(client, "request_count", 0) if client is not None else 0
    elapsed = time.monotonic() - started
    progress(
        f"分析完成: topics={len(output['topics'])}，"
        f"candidates={len(output['candidates'])}，已用时间={elapsed:.2f}s"
    )
    progress(f"输出: {output_path}")
    return AnalysisResult(
        output_path=output_path,
        window_count=len(windows),
        request_count=request_count_after - request_count_before,
        elapsed_seconds=elapsed,
        topic_count=len(output["topics"]),
        candidate_count=len(output["candidates"]),
        recommended_count=sum(
            1 for candidate in output["candidates"] if candidate["recommended"]
        ),
        resumed_from_window=resumed_from,
    )


def publish_analysis(
    output_dir: Path,
    analysis: dict[str, Any],
    *,
    timeline: dict[str, Any],
) -> Path:
    """Publish current plus at most two histories, rolling back ordinary failures."""

    output_dir = output_dir.resolve()
    current_path = output_dir / "current_analysis.json"
    history_dir = output_dir / "analysis_history"
    staging_path = output_dir / f".current_analysis.{uuid4().hex}.tmp"
    current_snapshot = current_path.read_bytes() if current_path.is_file() else None
    history_existed = history_dir.is_dir()
    history_snapshot = (
        {path.name: path.read_bytes() for path in history_dir.glob("*.json")}
        if history_existed
        else {}
    )
    try:
        atomic_write_json(staging_path, analysis)
        staged = json.loads(staging_path.read_text(encoding="utf-8"))
        validate_analysis(staged, timeline=timeline)

        if current_snapshot is not None:
            history_dir.mkdir(parents=True, exist_ok=True)
            history_name = _history_name(current_snapshot)
            atomic_write_text(
                history_dir / history_name,
                current_snapshot.decode("utf-8"),
            )
        _replace_file(staging_path, current_path)

        histories = sorted(
            history_dir.glob("*.json"),
            key=_history_sort_key,
            reverse=True,
        ) if history_dir.is_dir() else []
        for obsolete in histories[2:]:
            obsolete.unlink()
        return current_path
    except Exception as exc:
        rollback_error: Exception | None = None
        try:
            if current_snapshot is None:
                current_path.unlink(missing_ok=True)
            else:
                atomic_write_text(current_path, current_snapshot.decode("utf-8"))
            if history_dir.is_dir():
                for path in history_dir.glob("*.json"):
                    if path.name not in history_snapshot:
                        path.unlink(missing_ok=True)
            for name, content in history_snapshot.items():
                atomic_write_text(history_dir / name, content.decode("utf-8"))
            if not history_existed and history_dir.is_dir():
                try:
                    history_dir.rmdir()
                except OSError:
                    pass
        except Exception as rollback_exc:
            rollback_error = rollback_exc
        if rollback_error is not None:
            raise AnalysisError(
                "分析发布失败，且旧版本回滚失败: "
                f"{type(exc).__name__}/{type(rollback_error).__name__}"
            ) from None
        raise AnalysisError(f"分析发布失败: {type(exc).__name__}") from None
    finally:
        staging_path.unlink(missing_ok=True)


def _load_or_create_state(
    state_path: Path,
    *,
    fingerprint: dict[str, Any],
    windows: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    if not state_path.exists():
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "fingerprint": fingerprint,
            "completed_window_count": 0,
            "window_results": [],
        }
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"分析状态损坏: {type(exc).__name__}") from None
    if (
        not isinstance(state, dict)
        or set(state)
        != {
            "schema_version",
            "fingerprint",
            "completed_window_count",
            "window_results",
        }
        or state["schema_version"] != STATE_SCHEMA_VERSION
        or state["fingerprint"] != fingerprint
    ):
        raise AnalysisError("分析状态与 timeline、model、endpoint host 或窗口参数不匹配")
    completed = state["completed_window_count"]
    results = state["window_results"]
    if (
        isinstance(completed, bool)
        or not isinstance(completed, int)
        or completed < 0
        or completed > len(windows)
        or not isinstance(results, list)
        or len(results) != completed
    ):
        raise AnalysisError("分析状态损坏: 完成窗口记录无效")
    clean_results: list[dict[str, Any]] = []
    for index, result in enumerate(results):
        try:
            clean_results.append(
                validate_model_payload(result, window_segments=windows[index])
            )
        except ModelResponseError as exc:
            raise AnalysisError(f"分析状态损坏: {exc}") from None
    state["window_results"] = clean_results
    return state


def _build_output(
    *,
    timeline: dict[str, Any],
    timeline_file_name: str,
    timeline_sha256: str,
    model: str,
    window_results: list[dict[str, Any]],
) -> dict[str, Any]:
    segment_by_id = {segment["id"]: segment for segment in timeline["segments"]}
    topics: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    topics_by_window: list[list[dict[str, Any]]] = []

    for result in window_results:
        current_topics: list[dict[str, Any]] = []
        for raw_topic in result["topics"]:
            topic_id = f"topic-{len(topics) + 1:03d}"
            start_id = raw_topic["start_segment_id"]
            end_id = raw_topic["end_segment_id"]
            topic = {
                "id": topic_id,
                "start_segment_id": start_id,
                "end_segment_id": end_id,
                "start_ms": segment_by_id[start_id]["start_ms"],
                "end_ms": segment_by_id[end_id]["end_ms"],
                "title": raw_topic["title"],
                "summary": raw_topic["summary"],
            }
            topics.append(topic)
            current_topics.append(topic)
        topics_by_window.append(current_topics)

    for window_index, result in enumerate(window_results):
        for raw_candidate in result["candidates"]:
            start_id = raw_candidate["start_segment_id"]
            end_id = raw_candidate["end_segment_id"]
            start_ms = segment_by_id[start_id]["start_ms"]
            end_ms = segment_by_id[end_id]["end_ms"]
            duration_ms = end_ms - start_ms
            containing_topics = [
                topic
                for topic in topics_by_window[window_index]
                if topic["start_segment_id"] <= start_id
                and topic["end_segment_id"] >= end_id
            ]
            if len(containing_topics) != 1:
                raise AnalysisError("candidate topic 关联无效")
            candidate = {
                "topic_id": containing_topics[0]["id"],
                "start_segment_id": start_id,
                "end_segment_id": end_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": duration_ms,
                "title": raw_candidate["title"],
                "reason": raw_candidate["reason"],
                "quote_segment_id": raw_candidate["quote_segment_id"],
                "quote": segment_by_id[raw_candidate["quote_segment_id"]]["text"],
                **{
                    name: raw_candidate[name]
                    for name in (*SCORE_LIMITS, "risk_penalty")
                },
            }
            candidate["total_score"] = score_candidate(candidate)
            candidate["recommended"] = candidate["total_score"] >= 75
            if 15_000 <= duration_ms <= 180_000 and candidate["total_score"] >= 60:
                candidates.append(candidate)

    candidates.sort(key=lambda item: (-item["total_score"], item["start_ms"]))
    deduplicated: list[dict[str, Any]] = []
    for candidate in candidates:
        if any(overlap_ratio(candidate, kept) > 0.6 for kept in deduplicated):
            continue
        deduplicated.append(candidate)
        if len(deduplicated) == MAX_CANDIDATES:
            break
    final_candidates = [
        {"id": f"candidate-{index:03d}", **candidate}
        for index, candidate in enumerate(deduplicated, 1)
    ]
    return {
        "schema_version": "1.0",
        "source": {
            "timeline_file_name": timeline_file_name,
            "timeline_sha256": timeline_sha256,
            "video_file_name": timeline["source"]["file_name"],
            "duration_ms": timeline["source"]["duration_ms"],
        },
        "analysis": {
            "provider": "openai_compatible",
            "model": model,
            "completed": True,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "window_count": len(window_results),
        },
        "topics": topics,
        "candidates": final_candidates,
    }


def _history_name(content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()[:12]
    try:
        parsed = json.loads(content.decode("utf-8"))
        generated_at = str(parsed["analysis"]["generated_at"])
        stamp = "".join(character for character in generated_at if character.isdigit())[:14]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        stamp = ""
    if len(stamp) != 14:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"analysis_{stamp}_{digest}.json"


def _history_sort_key(path: Path) -> tuple[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        generated_at = str(value["analysis"]["generated_at"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        generated_at = ""
    return generated_at, path.name


def _replace_file(source: Path, target: Path) -> None:
    os.replace(source, target)


def _cleanup_work_state(work_dir: Path, state_path: Path) -> None:
    state_path.unlink(missing_ok=True)
    if work_dir.is_dir():
        try:
            work_dir.rmdir()
        except OSError as exc:
            raise AnalysisError(f"分析已发布，但工作状态清理失败: {type(exc).__name__}") from None

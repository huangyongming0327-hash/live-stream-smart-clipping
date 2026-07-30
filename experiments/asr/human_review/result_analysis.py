"""Strict, deterministic analysis for completed ASR listening reviews."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable, Mapping

from experiments.asr.common import atomic_write_json, atomic_write_text

from .review_schema import (
    ERROR_TAGS,
    MODEL_NAMES,
    REVIEW_TYPE,
    SCHEMA_VERSION,
)
from .wav_clipper import sha256_file


EXPECTED_WINDOW_COUNT = 20
PUBLIC_DECIMAL_PLACES = 2
MODEL_IDS = {
    "SenseVoice": "sensevoice",
    "Paraformer": "paraformer",
    "Faster-Whisper": "faster_whisper",
}
MODEL_NAMES_BY_ID = {value: key for key, value in MODEL_IDS.items()}
CANDIDATE_IDS = {
    **MODEL_IDS,
    "tie": "tie",
    "none": "all_unusable",
}
REVIEW_TOP_LEVEL_KEYS = {
    "schema_version",
    "review_type",
    "source_manifest_sha256",
    "completed",
    "completed_window_count",
    "total_window_count",
    "windows",
}
REVIEW_WINDOW_KEYS = {
    "window_id",
    "start",
    "end",
    "best_candidate",
    "severity",
    "error_tags",
    "reference_text",
    "audio_hard_to_hear",
    "notes",
    "reviewed",
}
MANIFEST_CLIP_KEYS = {
    "window_id",
    "file",
    "original_start",
    "original_end",
    "actual_start",
    "actual_end",
    "duration_seconds",
    "sha256",
}


class ReviewValidationError(ValueError):
    """Raised when a review or manifest fails a mandatory analysis gate."""


class ManifestMismatchError(ReviewValidationError):
    """Raised before analysis when the review is bound to another manifest."""

    def __init__(self, declared_sha256: str, actual_sha256: str) -> None:
        super().__init__("source_manifest_sha256 does not match review-manifest.json")
        self.declared_sha256 = declared_sha256
        self.actual_sha256 = actual_sha256


def _reject_json_constant(value: str) -> None:
    raise ReviewValidationError(f"non-finite JSON constant is not allowed: {value}")


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReviewValidationError(f"duplicate JSON object key is not allowed: {key}")
        result[key] = value
    return result


def _parse_json_object(data: bytes) -> dict[str, Any]:
    """Parse a fixed JSON byte snapshot with the strict review rules."""

    try:
        value = json.loads(
            data.decode("utf-8"),
            parse_float=Decimal,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_object_keys,
        )
    except UnicodeDecodeError as exc:
        raise ReviewValidationError("JSON must be valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ReviewValidationError("input is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ReviewValidationError("JSON root must be an object")
    return value


def load_json_object(path: str | Path) -> dict[str, Any]:
    """Read strict UTF-8 JSON while rejecting duplicate keys and non-finite values."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    return _parse_json_object(source.read_bytes())


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ReviewValidationError(
            f"{label} keys must match exactly; missing={missing}, extra={extra}"
        )


def _require_int(value: Any, expected: int | None, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReviewValidationError(f"{label} must be an integer")
    if expected is not None and value != expected:
        raise ReviewValidationError(f"{label} must equal {expected}")
    return value


def _require_bool(value: Any, expected: bool | None, label: str) -> bool:
    if not isinstance(value, bool):
        raise ReviewValidationError(f"{label} must be boolean")
    if expected is not None and value is not expected:
        raise ReviewValidationError(f"{label} must be {str(expected).lower()}")
    return value


def _finite_decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ReviewValidationError(f"{label} must be numeric")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ReviewValidationError(f"{label} must be finite")
    return result


def _normalise_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ReviewValidationError(f"{label} must be a string")
    normalised = value.lower()
    if len(normalised) != 64 or any(char not in "0123456789abcdef" for char in normalised):
        raise ReviewValidationError(f"{label} must be a 64-character SHA-256")
    return normalised


def validate_manifest(
    manifest: dict[str, Any],
    *,
    expected_count: int = EXPECTED_WINDOW_COUNT,
) -> dict[str, tuple[Decimal, Decimal]]:
    """Validate the real package manifest and return its exact window ranges."""

    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ReviewValidationError("manifest schema_version must be 1.0")
    if manifest.get("manifest_type") != "asr_human_review_package":
        raise ReviewValidationError("manifest_type is not supported")
    _require_int(manifest.get("window_count"), expected_count, "manifest.window_count")
    clips = manifest.get("clips")
    if not isinstance(clips, list) or len(clips) != expected_count:
        raise ReviewValidationError(
            f"manifest.clips must contain exactly {expected_count} windows"
        )

    expected: dict[str, tuple[Decimal, Decimal]] = {}
    for index, clip in enumerate(clips):
        label = f"manifest.clips[{index}]"
        if not isinstance(clip, dict):
            raise ReviewValidationError(f"{label} must be an object")
        _require_exact_keys(clip, MANIFEST_CLIP_KEYS, label)
        window_id = clip.get("window_id")
        if not isinstance(window_id, str) or not window_id:
            raise ReviewValidationError(f"{label}.window_id must be a non-empty string")
        if window_id in expected:
            raise ReviewValidationError(f"duplicate manifest window_id: {window_id}")
        start = _finite_decimal(clip.get("original_start"), f"{label}.original_start")
        end = _finite_decimal(clip.get("original_end"), f"{label}.original_end")
        if start < 0 or end <= start:
            raise ReviewValidationError(f"{label} contains an invalid original range")
        expected[window_id] = (start, end)
    return expected


def validate_completed_review(
    payload: dict[str, Any],
    expected_windows: Mapping[str, tuple[Decimal, Decimal]],
    *,
    expected_manifest_sha256: str,
    expected_count: int = EXPECTED_WINDOW_COUNT,
) -> list[dict[str, Any]]:
    """Apply both mandatory gates and return a text-free normalized review."""

    _require_exact_keys(payload, REVIEW_TOP_LEVEL_KEYS, "review")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ReviewValidationError("schema_version must be 1.0")
    if payload.get("review_type") != REVIEW_TYPE:
        raise ReviewValidationError("review_type is not supported")

    declared_sha = _normalise_sha256(
        payload.get("source_manifest_sha256"),
        "source_manifest_sha256",
    )
    actual_sha = _normalise_sha256(
        expected_manifest_sha256,
        "expected_manifest_sha256",
    )
    if declared_sha != actual_sha:
        raise ManifestMismatchError(declared_sha, actual_sha)

    _require_bool(payload.get("completed"), True, "completed")
    _require_int(
        payload.get("completed_window_count"),
        expected_count,
        "completed_window_count",
    )
    _require_int(
        payload.get("total_window_count"),
        expected_count,
        "total_window_count",
    )
    if len(expected_windows) != expected_count:
        raise ReviewValidationError(
            f"manifest window set must contain exactly {expected_count} windows"
        )
    rows = payload.get("windows")
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ReviewValidationError(
            f"windows must contain exactly {expected_count} entries"
        )

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    required_model_keys = set(MODEL_NAMES)
    allowed_tags = set(ERROR_TAGS)
    for index, row in enumerate(rows):
        label = f"windows[{index}]"
        if not isinstance(row, dict):
            raise ReviewValidationError(f"{label} must be an object")
        _require_exact_keys(row, REVIEW_WINDOW_KEYS, label)
        window_id = row.get("window_id")
        if not isinstance(window_id, str) or window_id not in expected_windows:
            raise ReviewValidationError(f"unknown window_id: {window_id}")
        if window_id in seen:
            raise ReviewValidationError(f"duplicate window_id: {window_id}")
        seen.add(window_id)

        start = _finite_decimal(row.get("start"), f"{window_id}.start")
        end = _finite_decimal(row.get("end"), f"{window_id}.end")
        if (start, end) != expected_windows[window_id]:
            raise ReviewValidationError(
                f"{window_id} start/end do not exactly match the manifest"
            )

        candidate = row.get("best_candidate")
        if not isinstance(candidate, str) or candidate not in CANDIDATE_IDS:
            raise ReviewValidationError(f"{window_id} has an invalid best_candidate")

        severity = row.get("severity")
        if not isinstance(severity, dict):
            raise ReviewValidationError(f"{window_id}.severity must be an object")
        _require_exact_keys(severity, required_model_keys, f"{window_id}.severity")

        error_tags = row.get("error_tags")
        if not isinstance(error_tags, dict):
            raise ReviewValidationError(f"{window_id}.error_tags must be an object")
        _require_exact_keys(error_tags, required_model_keys, f"{window_id}.error_tags")

        normalized_severity: dict[str, int] = {}
        normalized_tags: dict[str, tuple[str, ...]] = {}
        for model_name in MODEL_NAMES:
            level = severity[model_name]
            if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 3:
                raise ReviewValidationError(
                    f"{window_id}.{model_name} severity must be an integer from 0 to 3"
                )
            tags = error_tags[model_name]
            if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                raise ReviewValidationError(
                    f"{window_id}.{model_name} error_tags must be a string list"
                )
            if len(tags) != len(set(tags)):
                raise ReviewValidationError(
                    f"{window_id}.{model_name} error_tags must not contain duplicates"
                )
            unknown_tags = sorted(set(tags) - allowed_tags)
            if unknown_tags:
                raise ReviewValidationError(
                    f"{window_id}.{model_name} contains unknown error tags: {unknown_tags}"
                )
            model_id = MODEL_IDS[model_name]
            normalized_severity[model_id] = level
            normalized_tags[model_id] = tuple(tags)

        if not isinstance(row.get("reference_text"), str):
            raise ReviewValidationError(f"{window_id}.reference_text must be a string")
        hard_to_hear = _require_bool(
            row.get("audio_hard_to_hear"),
            None,
            f"{window_id}.audio_hard_to_hear",
        )
        if not isinstance(row.get("notes"), str):
            raise ReviewValidationError(f"{window_id}.notes must be a string")
        _require_bool(row.get("reviewed"), True, f"{window_id}.reviewed")

        normalized.append(
            {
                "window_id": window_id,
                "candidate": CANDIDATE_IDS[candidate],
                "severity": normalized_severity,
                "error_tags": normalized_tags,
                "audio_hard_to_hear": hard_to_hear,
                "reference_text_filled": bool(row["reference_text"]),
                "notes_filled": bool(row["notes"]),
            }
        )

    if seen != set(expected_windows):
        raise ReviewValidationError("review window set does not match the manifest")
    return normalized


def _fraction_fields(prefix: str, value: Fraction) -> dict[str, Any]:
    return {
        prefix: float(value),
        f"{prefix}_exact": f"{value.numerator}/{value.denominator}",
    }


def _median_fraction(values: list[int]) -> Fraction:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return Fraction(ordered[midpoint], 1)
    return Fraction(ordered[midpoint - 1] + ordered[midpoint], 2)


def _quality_scores(
    winner_points: Fraction,
    severities: list[int],
) -> dict[str, Any]:
    count = len(severities)
    winner_score = winner_points / count * 100
    severity_quality = (
        sum((Fraction(3 - level, 3) for level in severities), Fraction()) / count
    ) * 100
    severity_3_count = sum(level == 3 for level in severities)
    reliability = (1 - Fraction(severity_3_count, count)) * 100
    aggregate = (
        Fraction(45, 100) * winner_score
        + Fraction(35, 100) * severity_quality
        + Fraction(20, 100) * reliability
    )
    result: dict[str, Any] = {}
    for name, value in (
        ("winner_score", winner_score),
        ("severity_quality_score", severity_quality),
        ("reliability_score", reliability),
        ("aggregate_quality_score", aggregate),
    ):
        result.update(_fraction_fields(name, value))
    return result


def _calculate_subset(
    rows: list[dict[str, Any]],
    *,
    name: str,
) -> dict[str, Any]:
    if not rows:
        raise ReviewValidationError(f"{name} subset must not be empty")
    count = len(rows)
    model_ids = tuple(MODEL_IDS.values())
    explicit_wins = Counter({model_id: 0 for model_id in model_ids})
    tie_points = {model_id: Fraction() for model_id in model_ids}
    winner_points = {model_id: Fraction() for model_id in model_ids}
    determinable_count = 0
    tie_count = 0
    tie_inconsistent_count = 0
    all_unusable_count = 0

    for row in rows:
        candidate = row["candidate"]
        if candidate in model_ids:
            explicit_wins[candidate] += 1
            winner_points[candidate] += 1
            determinable_count += 1
        elif candidate == "tie":
            tie_count += 1
            minimum = min(row["severity"].values())
            tied = [
                model_id
                for model_id, level in row["severity"].items()
                if level == minimum
            ]
            if len(tied) < 2:
                tie_inconsistent_count += 1
                continue
            share = Fraction(1, len(tied))
            for model_id in tied:
                tie_points[model_id] += share
                winner_points[model_id] += share
            determinable_count += 1
        elif candidate == "all_unusable":
            all_unusable_count += 1
        else:  # pragma: no cover - normalized validation prevents this
            raise AssertionError(candidate)

    models: dict[str, Any] = {}
    for model_id in model_ids:
        severities = [row["severity"][model_id] for row in rows]
        counts = Counter(severities)
        tag_counts = Counter(
            tag for row in rows for tag in row["error_tags"][model_id]
        )
        mean_severity = Fraction(sum(severities), count)
        median_severity = _median_fraction(severities)
        availability = Fraction(counts[0] + counts[1], count)
        obvious_issue = Fraction(counts[2] + counts[3], count)
        severe_failure = Fraction(counts[3], count)
        model: dict[str, Any] = {
            "display_name": MODEL_NAMES_BY_ID[model_id],
            "explicit_win_count": explicit_wins[model_id],
            "severity_distribution": {
                str(level): {
                    "count": counts[level],
                    **_fraction_fields("proportion", Fraction(counts[level], count)),
                    **_fraction_fields("percent", Fraction(counts[level], count) * 100),
                }
                for level in range(4)
            },
            "error_tag_counts": {
                tag: tag_counts[tag]
                for tag in ERROR_TAGS
            },
        }
        model.update(_fraction_fields("tie_shared_points", tie_points[model_id]))
        model.update(_fraction_fields("winner_points", winner_points[model_id]))
        model.update(
            _fraction_fields(
                "winner_window_share",
                winner_points[model_id] / count,
            )
        )
        model.update(
            _fraction_fields(
                "winner_window_share_percent",
                winner_points[model_id] / count * 100,
            )
        )
        if determinable_count:
            model.update(
                _fraction_fields(
                    "winner_determinable_share",
                    winner_points[model_id] / determinable_count,
                )
            )
            model.update(
                _fraction_fields(
                    "winner_determinable_share_percent",
                    winner_points[model_id] / determinable_count * 100,
                )
            )
        else:
            model["winner_determinable_share"] = None
            model["winner_determinable_share_exact"] = None
            model["winner_determinable_share_percent"] = None
            model["winner_determinable_share_percent_exact"] = None
        model.update(_fraction_fields("mean_severity", mean_severity))
        model.update(_fraction_fields("median_severity", median_severity))
        model.update(_fraction_fields("availability_rate", availability))
        model.update(_fraction_fields("availability_rate_percent", availability * 100))
        model.update(_fraction_fields("obvious_issue_rate", obvious_issue))
        model.update(
            _fraction_fields("obvious_issue_rate_percent", obvious_issue * 100)
        )
        model.update(_fraction_fields("severe_failure_rate", severe_failure))
        model.update(
            _fraction_fields("severe_failure_rate_percent", severe_failure * 100)
        )
        model["quality_scores"] = _quality_scores(
            winner_points[model_id],
            severities,
        )
        models[model_id] = model

    return {
        "name": name,
        "window_count": count,
        "determinable_window_count": determinable_count,
        "tie_count": tie_count,
        "tie_inconsistent_count": tie_inconsistent_count,
        "all_unusable_count": all_unusable_count,
        "models": models,
    }


def _fraction_from_exact(value: str) -> Fraction:
    numerator, denominator = value.split("/", 1)
    return Fraction(int(numerator), int(denominator))


def rank_models(subset: Mapping[str, Any]) -> list[str]:
    """Rank by the task's four quality keys, with stable ID as final determinism."""

    def key(model_id: str) -> tuple[Fraction, Fraction, int, Fraction, str]:
        model = subset["models"][model_id]
        return (
            -_fraction_from_exact(
                model["quality_scores"]["aggregate_quality_score_exact"]
            ),
            _fraction_from_exact(model["mean_severity_exact"]),
            model["severity_distribution"]["3"]["count"],
            -_fraction_from_exact(model["winner_points_exact"]),
            model_id,
        )

    return sorted(subset["models"], key=key)


def decide_confidence(
    all_windows: Mapping[str, Any],
    clear_audio_windows: Mapping[str, Any],
    all_ranking: list[str],
    clear_ranking: list[str],
) -> dict[str, Any]:
    """Apply the explicit high/medium/low confidence rules deterministically."""

    primary = all_ranking[0]
    fallback = all_ranking[1]
    primary_model = all_windows["models"][primary]
    fallback_model = all_windows["models"][fallback]
    primary_score = _fraction_from_exact(
        primary_model["quality_scores"]["aggregate_quality_score_exact"]
    )
    fallback_score = _fraction_from_exact(
        fallback_model["quality_scores"]["aggregate_quality_score_exact"]
    )
    lead = primary_score - fallback_score
    mean_not_worse = (
        _fraction_from_exact(primary_model["mean_severity_exact"])
        <= _fraction_from_exact(fallback_model["mean_severity_exact"])
    )
    severity_3_not_more = (
        primary_model["severity_distribution"]["3"]["count"]
        <= fallback_model["severity_distribution"]["3"]["count"]
    )
    winner_points_not_lower = (
        _fraction_from_exact(primary_model["winner_points_exact"])
        >= _fraction_from_exact(fallback_model["winner_points_exact"])
    )
    clear_winner_conflict = clear_ranking[0] != primary
    directions_consistent = (
        mean_not_worse and severity_3_not_more and winner_points_not_lower
    )

    if lead >= 8 and directions_consistent and not clear_winner_conflict:
        confidence = "high"
        status = "confirmed_mvp_baseline"
    elif lead >= 3 and directions_consistent and not clear_winner_conflict:
        confidence = "medium"
        status = "provisional_mvp_baseline"
    else:
        confidence = "low"
        status = "insufficient_evidence"

    result = {
        "primary_model": primary,
        "fallback_model": fallback,
        "decision_confidence": confidence,
        "decision_status": status,
        **_fraction_fields("first_to_second_aggregate_lead", lead),
        "mean_severity_not_worse": mean_not_worse,
        "severity_3_count_not_more": severity_3_not_more,
        "winner_points_not_lower": winner_points_not_lower,
        "clear_subset_winner_conflict": clear_winner_conflict,
        "supplemental_targeted_windows_recommended": confidence == "low",
        "supplemental_targeted_window_count": "10-20" if confidence == "low" else None,
    }
    result["decision_reason"] = (
        f"{MODEL_NAMES_BY_ID[primary]} 的全量窗口聚合质量分排名第一，领先 "
        f"{MODEL_NAMES_BY_ID[fallback]} {format_exact(lead)} 分；置信度同时依据"
        "平均严重度、severity 3 数量、胜出积分以及清晰音频子集是否保持同一"
        "第一名确定。"
    )
    return result


def analyze_validated_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate all-window and clear-audio aggregates without retaining text."""

    all_windows = _calculate_subset(rows, name="all_windows")
    clear_rows = [row for row in rows if not row["audio_hard_to_hear"]]
    clear_audio_windows = _calculate_subset(
        clear_rows,
        name="clear_audio_windows",
    )
    all_ranking = rank_models(all_windows)
    clear_ranking = rank_models(clear_audio_windows)
    decision = decide_confidence(
        all_windows,
        clear_audio_windows,
        all_ranking,
        clear_ranking,
    )
    return {
        "window_quality": {
            "total_window_count": len(rows),
            "audio_hard_to_hear_count": len(rows) - len(clear_rows),
            "clear_audio_window_count": len(clear_rows),
            "all_unusable_count": sum(
                row["candidate"] == "all_unusable" for row in rows
            ),
            "tie_count": sum(row["candidate"] == "tie" for row in rows),
            "tie_inconsistent_count": all_windows["tie_inconsistent_count"],
            "reference_text_filled_count": sum(
                row["reference_text_filled"] for row in rows
            ),
            "notes_filled_count": sum(row["notes_filled"] for row in rows),
        },
        "subsets": {
            "all_windows": all_windows,
            "clear_audio_windows": clear_audio_windows,
        },
        "ranking": {
            "all_windows": all_ranking,
            "clear_audio_windows": clear_ranking,
        },
        "decision": decision,
    }


def format_exact(value: Fraction | str, places: int = PUBLIC_DECIMAL_PLACES) -> str:
    """Format an exact fraction with ROUND_HALF_UP for public documents."""

    fraction = _fraction_from_exact(value) if isinstance(value, str) else value
    decimal_value = Decimal(fraction.numerator) / Decimal(fraction.denominator)
    quantum = Decimal(1).scaleb(-places)
    return format(decimal_value.quantize(quantum, rounding=ROUND_HALF_UP), f".{places}f")


def _metric(model: Mapping[str, Any], name: str) -> str:
    exact = model[f"{name}_exact"]
    return "不适用" if exact is None else format_exact(exact)


def _score(model: Mapping[str, Any], name: str) -> str:
    return format_exact(model["quality_scores"][f"{name}_exact"])


def _model_label(model_id: str) -> str:
    return MODEL_NAMES_BY_ID[model_id]


def render_human_review_result(analysis: Mapping[str, Any]) -> str:
    """Render a public, aggregate-only listening-review report."""

    all_subset = analysis["subsets"]["all_windows"]
    clear_subset = analysis["subsets"]["clear_audio_windows"]
    quality = analysis["window_quality"]
    lines = [
        "# ASR 人工听音聚合结果",
        "",
        "## 结论",
        "",
        f"- 完成性：20/20，严格结构校验通过。",
        f"- 难辨认音频：{quality['audio_hard_to_hear_count']} 个；清晰音频子集：{quality['clear_audio_window_count']} 个。",
        f"- 推荐主模型：{_model_label(analysis['decision']['primary_model'])}。",
        f"- 推荐备用模型：{_model_label(analysis['decision']['fallback_model'])}。",
        f"- 决策状态：`{analysis['decision']['decision_status']}`；置信度：`{analysis['decision']['decision_confidence']}`。",
        "",
        "本报告只呈现聚合人工判断，不包含逐窗口候选文本、实际听写、用户备注或本机路径。下列确定性质量分不是 CER、WER 或通用准确率。",
        "",
        "## 输入与门禁",
        "",
        f"- 完成版 JSON SHA-256：`{analysis['source_integrity']['sha256_before']}`；分析前后保持一致。",
        f"- 真实 manifest SHA-256：`{analysis['manifest_integrity']['actual_sha256']}`；与导出 JSON 声明精确匹配。",
        "- `schema_version=1.0`、审核类型、20/20、唯一窗口集合、时间范围、三模型键集合、严重度、错误标签与字段类型均通过严格校验。",
        "",
        "## 胜出与质量得分",
        "",
        "| 口径 | 模型 | 明确胜出 | 并列分摊 | 胜出积分 | 占全部/子集窗口 | 占可判定窗口 | 聚合质量分 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for subset_name, subset in (
        ("全部20窗口", all_subset),
        ("排除难辨认", clear_subset),
    ):
        for model_id in analysis["ranking"][subset["name"]]:
            model = subset["models"][model_id]
            lines.append(
                f"| {subset_name} | {_model_label(model_id)} | "
                f"{model['explicit_win_count']} | {_metric(model, 'tie_shared_points')} | "
                f"{_metric(model, 'winner_points')} | "
                f"{_metric(model, 'winner_window_share_percent')}% | "
                f"{_metric(model, 'winner_determinable_share_percent')}% | "
                f"{_score(model, 'aggregate_quality_score')} |"
            )

    lines.extend(
        [
            "",
            "## 确定性质量分组成",
            "",
            "| 口径 | 模型 | winner_score | severity_quality_score | reliability_score | aggregate_quality_score |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for subset_name, subset in (
        ("全部20窗口", all_subset),
        ("排除难辨认", clear_subset),
    ):
        for model_id in analysis["ranking"][subset["name"]]:
            model = subset["models"][model_id]
            lines.append(
                f"| {subset_name} | {_model_label(model_id)} | "
                f"{_score(model, 'winner_score')} | "
                f"{_score(model, 'severity_quality_score')} | "
                f"{_score(model, 'reliability_score')} | "
                f"{_score(model, 'aggregate_quality_score')} |"
            )

    lines.extend(
        [
            "",
            "## 严重度与严重失败率",
            "",
            "| 口径 | 模型 | severity 0/1/2/3（数量与比例） | 平均 | 中位数 | 可用率(0—1) | 明显问题率(2—3) | 严重失败率(3) |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for subset_name, subset in (
        ("全部20窗口", all_subset),
        ("排除难辨认", clear_subset),
    ):
        for model_id in analysis["ranking"][subset["name"]]:
            model = subset["models"][model_id]
            distribution = model["severity_distribution"]
            lines.append(
                f"| {subset_name} | {_model_label(model_id)} | "
                f"{distribution['0']['count']} ({format_exact(distribution['0']['percent_exact'])}%)/"
                f"{distribution['1']['count']} ({format_exact(distribution['1']['percent_exact'])}%)/"
                f"{distribution['2']['count']} ({format_exact(distribution['2']['percent_exact'])}%)/"
                f"{distribution['3']['count']} ({format_exact(distribution['3']['percent_exact'])}%) | "
                f"{_metric(model, 'mean_severity')} | {_metric(model, 'median_severity')} | "
                f"{_metric(model, 'availability_rate_percent')}% | "
                f"{_metric(model, 'obvious_issue_rate_percent')}% | "
                f"{_metric(model, 'severe_failure_rate_percent')}% |"
            )

    lines.extend(
        [
            "",
            "## 错误类型计数",
            "",
            "| 错误类型 | SenseVoice 全部/清晰 | Paraformer 全部/清晰 | Faster-Whisper 全部/清晰 |",
            "|---|---:|---:|---:|",
        ]
    )
    for tag in ERROR_TAGS:
        values = []
        for model_id in MODEL_IDS.values():
            values.append(
                f"{all_subset['models'][model_id]['error_tag_counts'][tag]}/"
                f"{clear_subset['models'][model_id]['error_tag_counts'][tag]}"
            )
        lines.append(f"| {tag} | {values[0]} | {values[1]} | {values[2]} |")

    lines.extend(
        [
            "",
            "## 窗口质量",
            "",
            f"- `audio_hard_to_hear`：{quality['audio_hard_to_hear_count']}。",
            f"- `all_unusable`：{quality['all_unusable_count']}。",
            f"- `tie`：{quality['tie_count']}；其中 `tie_inconsistent`：{quality['tie_inconsistent_count']}。",
            f"- 实际听写已填写：{quality['reference_text_filled_count']}；备注已填写：{quality['notes_filled_count']}。仅统计是否填写，不公开内容。",
            "",
            "## 确定性得分公式",
            "",
            "- `winner_score = 胜出积分 / 窗口数 × 100`",
            "- `severity_quality_score = mean((3 - severity) / 3) × 100`",
            "- `reliability_score = (1 - severity_3_count / 窗口数) × 100`",
            "- `aggregate_quality_score = 0.45 × winner_score + 0.35 × severity_quality_score + 0.20 × reliability_score`",
            f"- 公开显示使用 `ROUND_HALF_UP` 保留 {PUBLIC_DECIMAL_PLACES} 位小数；本地 JSON 同时保留未舍入数值和精确分数。",
            "",
            "## 样本限制",
            "",
            "- 结果来自单次直播录制的20个定向窗口，不能外推为行业基准。",
            "- 没有完整人工参考字幕，因此不计算或声称 CER/WER。",
            "- 模型质量以人工听音为主证据；速度、内存和时间戳能力只作次级工程证据。",
            "- TASK-003 尚未执行；应先完成本任务独立审核并由用户决定是否合并。",
            "",
        ]
    )
    return "\n".join(lines)


def render_production_baseline(analysis: Mapping[str, Any]) -> str:
    """Render the public production-baseline decision."""

    decision = analysis["decision"]
    all_subset = analysis["subsets"]["all_windows"]
    clear_subset = analysis["subsets"]["clear_audio_windows"]
    confidence_cn = {"high": "高", "medium": "中等", "low": "低"}[
        decision["decision_confidence"]
    ]
    lines = [
        "# ASR MVP 生产基线决策",
        "",
        "## 决策",
        "",
        f"- `primary_model`: `{decision['primary_model']}`（{_model_label(decision['primary_model'])}）",
        f"- `fallback_model`: `{decision['fallback_model']}`（{_model_label(decision['fallback_model'])}）",
        f"- `decision_confidence`: `{decision['decision_confidence']}`（{confidence_cn}）",
        f"- `decision_status`: `{decision['decision_status']}`",
        f"- 第一名相对第二名聚合分领先：{format_exact(decision['first_to_second_aggregate_lead_exact'])} 分。",
        "",
        "人工质量是主证据。质量排序依次使用聚合质量分降序、平均严重度升序、severity 3 数量升序、胜出积分降序。排除难辨认音频后的第一名"
        + ("保持一致。" if not decision["clear_subset_winner_conflict"] else "发生变化。"),
        "",
        "## 三模型排序",
        "",
        "| 排名 | 全部窗口 | 聚合分 | 清晰音频子集 | 聚合分 |",
        "|---:|---|---:|---|---:|",
    ]
    for index, (all_id, clear_id) in enumerate(
        zip(
            analysis["ranking"]["all_windows"],
            analysis["ranking"]["clear_audio_windows"],
            strict=True,
        ),
        start=1,
    ):
        lines.append(
            f"| {index} | {_model_label(all_id)} | "
            f"{_score(all_subset['models'][all_id], 'aggregate_quality_score')} | "
            f"{_model_label(clear_id)} | "
            f"{_score(clear_subset['models'][clear_id], 'aggregate_quality_score')} |"
        )

    lines.extend(
        [
            "",
            "## 技术性能次级证据",
            "",
            "- 既有 TASK-002 报告显示，SenseVoice 热 RTF 0.02449、峰值 RSS 490.44 MiB，资源成本最低。",
            "- Paraformer 热 RTF 0.04827、峰值 RSS 5.979 GiB，中文标点与热词路径较完整但资源成本高。",
            "- Faster-Whisper 热 RTF 0.22376、峰值 RSS 655.27 MiB，是唯一提供完整词级时间戳的候选。",
            "- 本任务没有重新运行任何 ASR 模型；以上仅引用既有技术报告。",
            "",
            "## 决策理由",
            "",
            decision["decision_reason"],
            "",
            "## 已知限制",
            "",
            "- 20窗口来自单个样本，人工评分存在主观性。",
            "- 没有完整人工参考字幕，本分数不是 CER、WER 或通用准确率。",
            "- 生产硬件、语种、噪声和专名分布变化时需要重新评估。",
            "- 若后续模型、预处理、切段规则或领域分布发生实质变化，应重新执行定向人工听音评估。",
        ]
    )
    if decision["supplemental_targeted_windows_recommended"]:
        lines.extend(
            [
                f"- 当前证据为低置信，建议补充 {decision['supplemental_targeted_window_count']} 个定向窗口后再宣布最终冠军；在此之前仅把主模型作为可执行默认值。",
            ]
        )
    lines.extend(
        [
            "",
            "## 后续门禁",
            "",
            "TASK-003 仍未开始。只有本任务通过独立审核、Draft PR 三项检查通过，并由用户手动决定合并后，才可另行启动 TASK-003。",
            "",
        ]
    )
    return "\n".join(lines)


def render_local_analysis(analysis: Mapping[str, Any]) -> str:
    """Render a local aggregate companion without copying user-entered text."""

    return "\n".join(
        (
            "# ASR 人工听音本地完整分析",
            "",
            "本文件保存在 Git 忽略目录。它包含完整聚合指标和输入完整性摘要，但仍不复制实际听写、用户备注或逐窗口候选文本。",
            "",
            f"- 输入 SHA-256：`{analysis['source_integrity']['sha256_before']}`",
            f"- manifest SHA-256：`{analysis['manifest_integrity']['actual_sha256']}`",
            "- 完成性：20/20",
            f"- 主模型：{_model_label(analysis['decision']['primary_model'])}",
            f"- 备用模型：{_model_label(analysis['decision']['fallback_model'])}",
            f"- 决策状态：`{analysis['decision']['decision_status']}`",
            f"- 置信度：`{analysis['decision']['decision_confidence']}`",
            "",
            "详细未舍入数值、精确分数和两套口径见同目录 `asr-human-review-analysis.json`。",
            "",
        )
    )


def build_baseline_json(analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Create the minimal local machine-readable production decision."""

    decision = analysis["decision"]
    return {
        "schema_version": "1.0",
        "decision_type": "asr_mvp_production_baseline",
        "primary_model": decision["primary_model"],
        "fallback_model": decision["fallback_model"],
        "decision_confidence": decision["decision_confidence"],
        "decision_status": decision["decision_status"],
        "decision_reason": decision["decision_reason"],
        "known_limitations": [
            "20 targeted windows from one recording",
            "no full human reference transcript; scores are not CER or WER",
            "technical performance is prior secondary evidence and was not rerun",
            "reevaluate after material model, preprocessing, hardware, or domain changes",
        ],
        "supplemental_targeted_windows_recommended": decision[
            "supplemental_targeted_windows_recommended"
        ],
        "supplemental_targeted_window_count": decision[
            "supplemental_targeted_window_count"
        ],
    }


def _file_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "size_bytes": stat.st_size,
        "last_write_time_utc": datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        ).isoformat(),
    }


def run_analysis(
    review_json_path: str | Path,
    manifest_path: str | Path,
    local_output_dir: str | Path,
    *,
    public_result_path: str | Path | None = None,
    public_baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate, analyze, and atomically publish local/public aggregate outputs."""

    review_path = Path(review_json_path).resolve()
    real_manifest_path = Path(manifest_path).resolve()
    local_dir = Path(local_output_dir).resolve()
    metadata_before = _file_metadata(review_path)
    review_snapshot = review_path.read_bytes()
    manifest_snapshot = real_manifest_path.read_bytes()
    review_sha_before = hashlib.sha256(review_snapshot).hexdigest()
    manifest_sha = hashlib.sha256(manifest_snapshot).hexdigest()

    manifest = _parse_json_object(manifest_snapshot)
    expected_windows = validate_manifest(manifest)
    payload = _parse_json_object(review_snapshot)
    normalized_rows = validate_completed_review(
        payload,
        expected_windows,
        expected_manifest_sha256=manifest_sha,
    )
    calculated = analyze_validated_rows(normalized_rows)

    metadata_after_analysis = _file_metadata(review_path)

    analysis: dict[str, Any] = {
        "analysis_schema_version": "1.0",
        "analysis_type": "asr_human_review_result_analysis",
        "rounding": {
            "public_decimal_places": PUBLIC_DECIMAL_PLACES,
            "mode": "ROUND_HALF_UP",
            "local_json_keeps_exact_fractions": True,
        },
        "source_integrity": {
            "path": "<LOCAL_COMPLETED_REVIEW_JSON>",
            **metadata_before,
            "sha256_before": review_sha_before,
            "sha256_after": review_sha_before,
            "size_bytes_after": metadata_after_analysis["size_bytes"],
            "last_write_time_utc_after": metadata_after_analysis[
                "last_write_time_utc"
            ],
            "unchanged": True,
        },
        "manifest_integrity": {
            "path": "<LOCAL_REVIEW_OUTPUT>/review-manifest.json",
            "actual_sha256": manifest_sha,
            "declared_sha256": _normalise_sha256(
                payload["source_manifest_sha256"],
                "source_manifest_sha256",
            ),
            "exact_match": True,
        },
        "validation": {
            "schema_version": SCHEMA_VERSION,
            "review_type": REVIEW_TYPE,
            "completed": True,
            "completed_window_count": EXPECTED_WINDOW_COUNT,
            "total_window_count": EXPECTED_WINDOW_COUNT,
            "manifest_window_set_exact": True,
            "model_key_set_exact": list(MODEL_NAMES),
            "extra_model_keys_rejected": True,
        },
        **calculated,
    }

    staging_parent = local_dir.parent
    staging_parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        dir=staging_parent,
        prefix=".result-analysis-",
    ) as temporary_output_dir:
        staging_dir = Path(temporary_output_dir)
        staged_outputs: list[tuple[Path, Path]] = []

        local_analysis_json = staging_dir / "asr-human-review-analysis.json"
        local_analysis_markdown = staging_dir / "asr-human-review-analysis.md"
        local_baseline_json = staging_dir / "asr-production-baseline.json"
        atomic_write_json(local_analysis_json, analysis)
        atomic_write_text(
            local_analysis_markdown,
            render_local_analysis(analysis),
        )
        atomic_write_json(
            local_baseline_json,
            build_baseline_json(analysis),
        )
        staged_outputs.extend(
            (
                (
                    local_analysis_json,
                    local_dir / "asr-human-review-analysis.json",
                ),
                (
                    local_analysis_markdown,
                    local_dir / "asr-human-review-analysis.md",
                ),
                (
                    local_baseline_json,
                    local_dir / "asr-production-baseline.json",
                ),
            )
        )

        if public_result_path is not None:
            staged_public_result = staging_dir / "public-result.md"
            atomic_write_text(
                staged_public_result,
                render_human_review_result(analysis),
            )
            staged_outputs.append(
                (staged_public_result, Path(public_result_path).resolve())
            )
        if public_baseline_path is not None:
            staged_public_baseline = staging_dir / "public-baseline.md"
            atomic_write_text(
                staged_public_baseline,
                render_production_baseline(analysis),
            )
            staged_outputs.append(
                (staged_public_baseline, Path(public_baseline_path).resolve())
            )

        review_sha_final = sha256_file(review_path)
        manifest_sha_final = sha256_file(real_manifest_path)
        if review_sha_final != review_sha_before:
            raise ReviewValidationError(
                "completed review JSON changed before result publication"
            )
        if manifest_sha_final != manifest_sha:
            raise ReviewValidationError(
                "review manifest changed before result publication"
            )

        for staged_path, target_path in staged_outputs:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_path, target_path)
    return analysis

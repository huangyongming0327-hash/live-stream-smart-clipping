from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from liveclip.schemas import (
    CurrentAnalysis,
    ReviewCurrent,
    ScoreCalculation,
    TimeRange,
    Timeline,
    calculate_score,
    grade_for_score,
    round_score_for_display,
)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_are_rejected_everywhere(
    value: float,
    timeline_data: dict,
    analysis_data: dict,
    review_data: dict,
) -> None:
    with pytest.raises(ValidationError):
        TimeRange(start=value, end=1.0)
    with pytest.raises(ValidationError):
        TimeRange(start=0.0, end=value)

    video = deepcopy(timeline_data)
    video["video"]["duration"] = value
    with pytest.raises(ValidationError):
        Timeline.model_validate(video)

    for field in ("start", "end"):
        segment = deepcopy(timeline_data)
        segment["segments"][0][field] = value
        segment["segments"][0]["words"] = []
        with pytest.raises(ValidationError):
            Timeline.model_validate(segment)

        word = deepcopy(timeline_data)
        word["segments"][0]["words"][0][field] = value
        with pytest.raises(ValidationError):
            Timeline.model_validate(word)

    confidence = deepcopy(timeline_data)
    confidence["segments"][0]["words"][0]["confidence"] = value
    with pytest.raises(ValidationError):
        Timeline.model_validate(confidence)

    score = deepcopy(analysis_data)
    score["candidates"][0]["score"] = value
    with pytest.raises(ValidationError):
        CurrentAnalysis.model_validate(score)

    for field in ("start", "end"):
        candidate_range = deepcopy(analysis_data)
        candidate_range["candidates"][0]["ranges"]["core"][field] = value
        with pytest.raises(ValidationError):
            CurrentAnalysis.model_validate(candidate_range)

    analysis_duration = deepcopy(analysis_data)
    analysis_duration["video_duration"] = value
    with pytest.raises(ValidationError):
        CurrentAnalysis.model_validate(analysis_duration)

    for field in ("final_start", "final_end"):
        final_time = deepcopy(review_data)
        final_time["candidates"][0][field] = value
        with pytest.raises(ValidationError):
            ReviewCurrent.model_validate(final_time)

    for field in ("base_score", "risk_penalty", "final_score"):
        score_calculation = {
            "base_score": 100.0,
            "risk_penalty": 0.0,
            "final_score": 100.0,
        }
        score_calculation[field] = value
        with pytest.raises(ValidationError):
            ScoreCalculation.model_validate(score_calculation)


def test_non_finite_score_helper_inputs_are_rejected() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite"):
            calculate_score([15.0, 15.0, 15.0, 15.0, 15.0, value], 0.0)
        with pytest.raises(ValueError, match="finite"):
            calculate_score([15.0] * 6, value)


def test_assignment_cannot_introduce_non_finite_values() -> None:
    time_range = TimeRange(start=0.0, end=1.0)
    with pytest.raises(ValidationError):
        time_range.end = float("nan")


@pytest.mark.parametrize("invalid_version", ["999.0", "1", "", 1.0])
def test_only_schema_version_1_0_is_accepted(
    invalid_version: object,
    timeline_data: dict,
    analysis_data: dict,
    review_data: dict,
) -> None:
    for model, source in (
        (Timeline, timeline_data),
        (CurrentAnalysis, analysis_data),
        (ReviewCurrent, review_data),
    ):
        data = deepcopy(source)
        data["schema_version"] = invalid_version
        with pytest.raises(ValidationError):
            model.model_validate(data)


def test_schema_version_1_0_is_accepted(
    timeline_data: dict,
    analysis_data: dict,
    review_data: dict,
) -> None:
    assert Timeline.model_validate(timeline_data).schema_version == "1.0"
    assert CurrentAnalysis.model_validate(analysis_data).schema_version == "1.0"
    assert ReviewCurrent.model_validate(review_data).schema_version == "1.0"


def test_strict_types_reject_coercion(
    timeline_data: dict,
    analysis_data: dict,
) -> None:
    string_time = deepcopy(timeline_data)
    string_time["segments"][0]["start"] = "1.0"
    with pytest.raises(ValidationError):
        Timeline.model_validate(string_time)

    boolean_score = deepcopy(analysis_data)
    boolean_score["candidates"][0]["score"] = True
    with pytest.raises(ValidationError):
        CurrentAnalysis.model_validate(boolean_score)

    unknown_extra = deepcopy(timeline_data)
    unknown_extra["unexpected"] = "value"
    with pytest.raises(ValidationError, match="Extra inputs"):
        Timeline.model_validate(unknown_extra)


@pytest.mark.parametrize("value", [0, 1, "true"])
def test_visual_dependency_is_a_strict_boolean(
    value: object,
    analysis_data: dict,
) -> None:
    data = deepcopy(analysis_data)
    data["candidates"][0]["visual_dependency"] = value
    with pytest.raises(ValidationError):
        CurrentAnalysis.model_validate(data)


@pytest.mark.parametrize(
    ("contract", "field", "unknown"),
    [
        ("timeline", "risk_level", "低"),
        ("analysis", "content_type", "观点"),
        ("analysis", "subtitle_reliability", "高"),
        ("analysis", "status", "待审核"),
        ("review", "review_status", "选中"),
    ],
)
def test_unknown_or_legacy_enum_values_are_rejected(
    contract: str,
    field: str,
    unknown: str,
    timeline_data: dict,
    analysis_data: dict,
    review_data: dict,
) -> None:
    if contract == "timeline":
        data = deepcopy(timeline_data)
        data["segments"][0][field] = unknown
        model = Timeline
    elif contract == "analysis":
        data = deepcopy(analysis_data)
        data["candidates"][0][field] = unknown
        model = CurrentAnalysis
    else:
        data = deepcopy(review_data)
        data["candidates"][0][field] = unknown
        model = ReviewCurrent
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_topic_candidate_and_review_ids_are_unique(
    analysis_data: dict,
    review_data: dict,
) -> None:
    duplicate_topic = deepcopy(analysis_data)
    duplicate_topic["topics"].append(deepcopy(duplicate_topic["topics"][0]))
    with pytest.raises(ValidationError, match="topic ids must be unique"):
        CurrentAnalysis.model_validate(duplicate_topic)

    duplicate_candidate = deepcopy(analysis_data)
    duplicate_candidate["candidates"].append(
        deepcopy(duplicate_candidate["candidates"][0])
    )
    with pytest.raises(ValidationError, match="candidate ids must be unique"):
        CurrentAnalysis.model_validate(duplicate_candidate)

    duplicate_review = deepcopy(review_data)
    duplicate_review["candidates"].append(deepcopy(duplicate_review["candidates"][0]))
    with pytest.raises(ValidationError, match="review candidate ids must be unique"):
        ReviewCurrent.model_validate(duplicate_review)


def test_candidate_topic_reference_must_exist(analysis_data: dict) -> None:
    data = deepcopy(analysis_data)
    data["candidates"][0]["topic_id"] = "topic-missing"
    with pytest.raises(ValidationError, match="topic ids must exist"):
        CurrentAnalysis.model_validate(data)


def test_ids_reject_padding_instead_of_silently_trimming(timeline_data: dict) -> None:
    data = deepcopy(timeline_data)
    data["segments"][0]["id"] = " seg-001 "
    with pytest.raises(ValidationError, match="leading or trailing"):
        Timeline.model_validate(data)


def test_word_must_stay_inside_segment(timeline_data: dict) -> None:
    data = deepcopy(timeline_data)
    data["segments"][0]["words"][0]["start"] = 0.9
    with pytest.raises(ValidationError, match="inside"):
        Timeline.model_validate(data)


def test_words_must_be_ordered(timeline_data: dict) -> None:
    data = deepcopy(timeline_data)
    data["segments"][0]["words"][0].update(start=1.5, end=1.7)
    data["segments"][0]["words"][1].update(start=1.2, end=1.4)
    with pytest.raises(ValidationError, match="words must be ordered"):
        Timeline.model_validate(data)


def test_segment_must_not_exceed_video_duration(timeline_data: dict) -> None:
    data = deepcopy(timeline_data)
    data["segments"][1]["end"] = 120.1
    with pytest.raises(ValidationError, match="video duration"):
        Timeline.model_validate(data)


def test_segment_overlap_uses_fixed_tolerance(timeline_data: dict) -> None:
    allowed = deepcopy(timeline_data)
    allowed["segments"][1].update(start=3.95, end=6.0)
    Timeline.model_validate(allowed)

    rejected = deepcopy(timeline_data)
    rejected["segments"][1].update(start=3.94, end=6.0)
    with pytest.raises(ValidationError, match="0.05 seconds"):
        Timeline.model_validate(rejected)


def test_candidate_range_must_not_exceed_video_duration(analysis_data: dict) -> None:
    data = deepcopy(analysis_data)
    data["video_duration"] = 24.99
    with pytest.raises(ValidationError, match="video duration"):
        CurrentAnalysis.model_validate(data)


@pytest.mark.parametrize(
    ("score", "grade"),
    [
        (64.95, "不推荐"),
        (65.0, "B"),
        (74.95, "B"),
        (75.0, "A"),
        (84.95, "A"),
        (85.0, "S"),
    ],
)
def test_grade_boundaries_use_unrounded_score(
    score: float,
    grade: str,
    analysis_data: dict,
) -> None:
    assert grade_for_score(score) == grade
    data = deepcopy(analysis_data)
    data["candidates"][0]["score"] = score
    data["candidates"][0]["grade"] = grade
    CurrentAnalysis.model_validate(data)


def test_grade_must_match_score(analysis_data: dict) -> None:
    data = deepcopy(analysis_data)
    data["candidates"][0]["score"] = 84.95
    data["candidates"][0]["grade"] = "S"
    with pytest.raises(ValidationError, match="does not match score"):
        CurrentAnalysis.model_validate(data)


def test_score_display_rounding_is_half_up() -> None:
    assert round_score_for_display(64.95) == 65.0
    assert round_score_for_display(74.95) == 75.0
    assert round_score_for_display(84.95) == 85.0


def test_each_score_component_is_bounded() -> None:
    with pytest.raises(ValueError, match="between 0 and 15"):
        calculate_score([15.01, 0.0, 0.0, 0.0, 0.0, 0.0], 0.0)


def test_updated_at_requires_timezone_and_normalizes_to_utc(review_data: dict) -> None:
    utc_data = deepcopy(review_data)
    utc_data["candidates"][0]["updated_at"] = datetime(
        2026, 7, 18, 8, 0, tzinfo=timezone.utc
    )
    utc_review = ReviewCurrent.model_validate(utc_data)
    assert utc_review.candidates[0].updated_at.utcoffset() == timedelta(0)

    offset_data = deepcopy(review_data)
    offset_data["candidates"][0]["updated_at"] = datetime(
        2026, 7, 18, 16, 0, tzinfo=timezone(timedelta(hours=8))
    )
    offset_review = ReviewCurrent.model_validate(offset_data)
    assert offset_review.candidates[0].updated_at.isoformat() == "2026-07-18T08:00:00+00:00"
    assert '"updated_at":"2026-07-18T08:00:00Z"' in offset_review.model_dump_json()

    naive_data = deepcopy(review_data)
    naive_data["candidates"][0]["updated_at"] = datetime(2026, 7, 18, 8, 0)
    with pytest.raises(ValidationError, match="timezone"):
        ReviewCurrent.model_validate(naive_data)


def test_text_fields_preserve_whitespace_and_newlines(
    timeline_data: dict,
    analysis_data: dict,
    review_data: dict,
) -> None:
    raw_text = "  原始字幕第一行\n原始字幕第二行  "
    clean_text = "  清洗文本\n仍需原样保留  "
    transcript = "  候选逐字稿\n第二行  "
    user_notes = "  用户备注\n不要裁剪  "
    edited_text = "  修改字幕\n保留空格  "

    timeline_payload = deepcopy(timeline_data)
    timeline_payload["segments"][0]["raw_text"] = raw_text
    timeline_payload["segments"][0]["clean_text"] = clean_text
    timeline = Timeline.model_validate_json(
        Timeline.model_validate(timeline_payload).model_dump_json()
    )
    assert timeline.segments[0].raw_text == raw_text
    assert timeline.segments[0].clean_text == clean_text

    analysis_payload = deepcopy(analysis_data)
    analysis_payload["candidates"][0]["transcript"] = transcript
    analysis = CurrentAnalysis.model_validate_json(
        CurrentAnalysis.model_validate(analysis_payload).model_dump_json()
    )
    assert analysis.candidates[0].transcript == transcript

    review_payload = deepcopy(review_data)
    review_payload["candidates"][0]["user_notes"] = user_notes
    review_payload["candidates"][0]["subtitle_edits"][0]["edited_text"] = edited_text
    review = ReviewCurrent.model_validate_json(
        ReviewCurrent.model_validate(review_payload).model_dump_json()
    )
    assert review.candidates[0].user_notes == user_notes
    assert review.candidates[0].subtitle_edits[0].edited_text == edited_text


def test_json_file_round_trip_on_chinese_and_space_paths(
    tmp_path: Path,
    timeline_data: dict,
    analysis_data: dict,
    review_data: dict,
) -> None:
    cases = (
        (
            Timeline,
            timeline_data,
            tmp_path / "测试 直播项目" / "字幕 数据" / "timeline.json",
        ),
        (
            CurrentAnalysis,
            analysis_data,
            tmp_path / "测试 直播项目" / "分析 数据" / "current_analysis.json",
        ),
        (
            ReviewCurrent,
            review_data,
            tmp_path / "测试 直播项目" / "审核 数据" / "review_current.json",
        ),
    )

    for model, payload, path in cases:
        contract = model.model_validate(payload)
        encoded = contract.model_dump_json(indent=2)
        assert "NaN" not in encoded
        assert "Infinity" not in encoded
        assert ": null" not in encoded

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded, encoding="utf-8")
        assert path.is_file()

        restored = model.model_validate_json(path.read_text(encoding="utf-8"))
        assert restored == contract

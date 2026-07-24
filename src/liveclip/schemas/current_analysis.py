"""Pydantic contract and scoring helper for current_analysis.json."""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from pydantic import Field, model_validator

from .common import (
    NonNegativeFiniteFloat,
    PositiveFiniteFloat,
    SchemaVersion,
    ScoreValue,
    StrictModel,
    TimeRange,
    TrimmedNonEmptyStr,
)


Grade = Literal["S", "A", "B", "不推荐"]
ContentType = Literal[
    "viewpoint",
    "story",
    "emotional_resonance",
    "qa",
    "humor",
    "product",
    "transition",
    "low_value",
]
SubtitleReliability = Literal["high", "medium", "low", "unknown"]
CandidateStatus = Literal["pending_review", "submitted", "excluded"]


class ModelUsage(StrictModel):
    provider: TrimmedNonEmptyStr
    model: TrimmedNonEmptyStr
    purpose: TrimmedNonEmptyStr
    local: bool = True


class Topic(StrictModel):
    topic_id: TrimmedNonEmptyStr
    name: TrimmedNonEmptyStr
    summary: str = ""


class CandidateRanges(StrictModel):
    core: TimeRange
    recommended: TimeRange
    extended: TimeRange

    @model_validator(mode="after")
    def validate_nesting(self) -> "CandidateRanges":
        if not self.recommended.contains(self.core):
            raise ValueError("recommended range must contain core range")
        if not self.extended.contains(self.recommended):
            raise ValueError("extended range must contain recommended range")
        return self


class Candidate(StrictModel):
    candidate_id: TrimmedNonEmptyStr
    topic_id: TrimmedNonEmptyStr
    content_type: ContentType
    grade: Grade
    score: ScoreValue
    ranges: CandidateRanges
    transcript: str
    titles: list[TrimmedNonEmptyStr] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    recommendation_reason: str
    subtitle_reliability: SubtitleReliability
    visual_dependency: bool
    risks: list[str] = Field(default_factory=list)
    status: CandidateStatus

    @model_validator(mode="after")
    def validate_grade(self) -> "Candidate":
        expected_grade = grade_for_score(self.score)
        if self.grade != expected_grade:
            raise ValueError(
                f"grade {self.grade!r} does not match score; expected {expected_grade!r}"
            )
        return self


class CurrentAnalysis(StrictModel):
    schema_version: SchemaVersion
    project_id: TrimmedNonEmptyStr
    analysis_version: TrimmedNonEmptyStr
    video_duration: PositiveFiniteFloat
    model_usage: list[ModelUsage]
    topics: list[Topic]
    candidates: list[Candidate]

    @model_validator(mode="after")
    def validate_references(self) -> "CurrentAnalysis":
        topic_ids = [topic.topic_id for topic in self.topics]
        if len(topic_ids) != len(set(topic_ids)):
            raise ValueError("topic ids must be unique")

        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate ids must be unique")

        known_topics = set(topic_ids)
        missing_topics = {
            candidate.topic_id
            for candidate in self.candidates
            if candidate.topic_id not in known_topics
        }
        if missing_topics:
            raise ValueError(f"candidate topic ids must exist: {sorted(missing_topics)}")

        outside_video = [
            candidate.candidate_id
            for candidate in self.candidates
            if candidate.ranges.extended.end > self.video_duration
        ]
        if outside_video:
            raise ValueError(
                "candidate ranges must not exceed video duration: "
                f"{sorted(outside_video)}"
            )
        return self


class ScoreCalculation(StrictModel):
    base_score: ScoreValue
    risk_penalty: NonNegativeFiniteFloat
    final_score: ScoreValue

    @property
    def base_score_display(self) -> float:
        return round_score_for_display(self.base_score)

    @property
    def final_score_display(self) -> float:
        return round_score_for_display(self.final_score)


def grade_for_score(score: float) -> Grade:
    """Return the V1 grade using the unrounded final score."""

    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise TypeError("score must be a number")
    numeric = float(score)
    if not math.isfinite(numeric) or numeric < 0 or numeric > 100:
        raise ValueError("score must be finite and between 0 and 100")
    if numeric >= 85:
        return "S"
    if numeric >= 75:
        return "A"
    if numeric >= 65:
        return "B"
    return "不推荐"


def round_score_for_display(score: float) -> float:
    """Round a finite score to one decimal using decimal ROUND_HALF_UP."""

    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise TypeError("score must be a number")
    numeric = float(score)
    if not math.isfinite(numeric):
        raise ValueError("score must be finite")
    return float(Decimal(str(numeric)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def calculate_score(
    first_six_scores: Sequence[float], risk_penalty: float
) -> ScoreCalculation:
    """Apply the frozen TASK-000 score formula.

    The six component scores must be finite, non-negative, and total no more
    than the documented maximum of 90 points.
    """

    if len(first_six_scores) != 6:
        raise ValueError("exactly six component scores are required")

    numeric_scores: list[float] = []
    for value in first_six_scores:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("component scores must be numbers")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0 or numeric > 15:
            raise ValueError(
                "component scores must be finite and between 0 and 15"
            )
        numeric_scores.append(numeric)

    if isinstance(risk_penalty, bool) or not isinstance(risk_penalty, (int, float)):
        raise TypeError("risk penalty must be a number")
    penalty = float(risk_penalty)
    if not math.isfinite(penalty) or penalty < 0:
        raise ValueError("risk penalty must be finite and non-negative")

    total = sum(numeric_scores)
    if total > 90:
        raise ValueError("the first six component scores must total at most 90")

    base_score = total / 90 * 100
    final_score = max(0.0, min(100.0, base_score - penalty))
    return ScoreCalculation(
        base_score=base_score,
        risk_penalty=penalty,
        final_score=final_score,
    )

"""Pydantic contract for review_current.json."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .common import (
    FiniteFloat,
    NonNegativeFiniteFloat,
    SchemaVersion,
    StrictModel,
    TrimmedNonEmptyStr,
)


ReviewStatus = Literal["unreviewed", "selected", "undecided", "skipped", "exported"]


class SubtitleEdit(StrictModel):
    segment_id: TrimmedNonEmptyStr
    original_text: str
    edited_text: str


class ReviewCandidate(StrictModel):
    candidate_id: TrimmedNonEmptyStr
    review_status: ReviewStatus
    final_start: NonNegativeFiniteFloat
    final_end: FiniteFloat
    final_title: TrimmedNonEmptyStr
    subtitle_edits: list[SubtitleEdit] = Field(default_factory=list)
    needs_reanalysis: bool = False
    user_notes: str = ""
    updated_at: AwareDatetime

    @field_validator("updated_at", mode="after")
    @classmethod
    def normalize_updated_at_to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_final_range(self) -> "ReviewCandidate":
        if self.final_end <= self.final_start:
            raise ValueError("final_end must be greater than final_start")
        return self


class ReviewCurrent(StrictModel):
    schema_version: SchemaVersion
    project_id: TrimmedNonEmptyStr
    source_analysis_version: TrimmedNonEmptyStr
    candidates: list[ReviewCandidate]

    @model_validator(mode="after")
    def validate_candidates(self) -> "ReviewCurrent":
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("review candidate ids must be unique")
        return self

"""Pydantic contract for timeline.json."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import (
    PositiveFiniteFloat,
    SchemaVersion,
    StrictModel,
    TimeRange,
    TrimmedNonEmptyStr,
    UnitFiniteFloat,
)


RiskLevel = Literal["red", "yellow", "none"]
SEGMENT_OVERLAP_TOLERANCE_SECONDS = 0.05


class VideoInfo(StrictModel):
    path: TrimmedNonEmptyStr
    duration: PositiveFiniteFloat
    file_name: TrimmedNonEmptyStr | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)


class ModelInfo(StrictModel):
    provider: TrimmedNonEmptyStr
    model: TrimmedNonEmptyStr
    version: TrimmedNonEmptyStr | None = None
    local: bool = True


class Word(TimeRange):
    text: str = Field(min_length=1)
    confidence: UnitFiniteFloat | None = None


class TimelineSegment(TimeRange):
    id: TrimmedNonEmptyStr
    speaker: TrimmedNonEmptyStr
    raw_text: str
    clean_text: str
    risk_level: RiskLevel
    risk_reasons: list[str] = Field(default_factory=list)
    words: list[Word] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_word_ranges(self) -> "TimelineSegment":
        previous_start = self.start
        for word in self.words:
            if word.start < self.start or word.end > self.end:
                raise ValueError("word range must be inside its segment range")
            if word.start < previous_start:
                raise ValueError("words must be ordered by start time")
            previous_start = word.start
        return self


class Timeline(StrictModel):
    schema_version: SchemaVersion
    project_id: TrimmedNonEmptyStr
    video: VideoInfo
    model_info: ModelInfo
    segments: list[TimelineSegment]

    @model_validator(mode="after")
    def validate_segments(self) -> "Timeline":
        ids = [segment.id for segment in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("segment ids must be unique")

        previous_start = -1.0
        previous_end: float | None = None
        for segment in self.segments:
            if segment.start < previous_start:
                raise ValueError("segments must be ordered by start time")
            if (
                previous_end is not None
                and segment.start + SEGMENT_OVERLAP_TOLERANCE_SECONDS < previous_end
            ):
                raise ValueError(
                    "segment overlap must not exceed "
                    f"{SEGMENT_OVERLAP_TOLERANCE_SECONDS:.2f} seconds"
                )
            if segment.end > self.video.duration:
                raise ValueError("segment range must not exceed video duration")
            previous_start = segment.start
            previous_end = segment.end
        return self

"""Shared schema primitives and strict contract types."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


SchemaVersion = Literal["1.0"]


def _require_trimmed_non_empty(value: str) -> str:
    """Reject blank or padded identifiers without modifying their contents."""

    if not value or not value.strip():
        raise ValueError("value must not be empty or whitespace")
    if value != value.strip():
        raise ValueError("value must not have leading or trailing whitespace")
    return value


TrimmedNonEmptyStr = Annotated[
    str,
    Field(strict=True),
    AfterValidator(_require_trimmed_non_empty),
]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[
    float,
    Field(strict=True, ge=0, allow_inf_nan=False),
]
PositiveFiniteFloat = Annotated[
    float,
    Field(strict=True, gt=0, allow_inf_nan=False),
]
UnitFiniteFloat = Annotated[
    float,
    Field(strict=True, ge=0, le=1, allow_inf_nan=False),
]
ScoreValue = Annotated[
    float,
    Field(strict=True, ge=0, le=100, allow_inf_nan=False),
]


class StrictModel(BaseModel):
    """Base model with strict types, finite numbers, and forbidden extras."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
        allow_inf_nan=False,
    )


class TimeRange(StrictModel):
    """Half-open-style media time range measured in seconds."""

    start: NonNegativeFiniteFloat
    end: FiniteFloat

    @model_validator(mode="after")
    def validate_order(self) -> "TimeRange":
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self

    def contains(self, other: "TimeRange") -> bool:
        return self.start <= other.start and self.end >= other.end

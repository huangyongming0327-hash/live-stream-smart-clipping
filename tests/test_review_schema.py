from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from liveclip.schemas import ReviewCurrent


def test_valid_review_sample(review_data: dict) -> None:
    review = ReviewCurrent.model_validate(review_data)
    assert review.candidates[0].review_status == "selected"
    assert review.candidates[0].subtitle_edits[0].edited_text == "修订字幕"


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1.0, 1.0), (1.0, 1.0), (2.0, 1.0)],
)
def test_invalid_final_time_range(
    review_data: dict, start: float, end: float
) -> None:
    data = deepcopy(review_data)
    data["candidates"][0]["final_start"] = start
    data["candidates"][0]["final_end"] = end
    with pytest.raises(ValidationError):
        ReviewCurrent.model_validate(data)


@pytest.mark.parametrize("status", ["选中", "完成", ""])
def test_invalid_review_status(review_data: dict, status: str) -> None:
    data = deepcopy(review_data)
    data["candidates"][0]["review_status"] = status
    with pytest.raises(ValidationError):
        ReviewCurrent.model_validate(data)


def test_review_json_round_trip_preserves_datetime(review_data: dict) -> None:
    review = ReviewCurrent.model_validate(review_data)
    encoded = review.model_dump_json()
    restored = ReviewCurrent.model_validate_json(encoded)
    assert restored == review
    assert restored.candidates[0].updated_at.utcoffset() is not None

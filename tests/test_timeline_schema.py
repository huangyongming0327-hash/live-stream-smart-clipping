from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from liveclip.schemas import Timeline


def test_valid_timeline_sample(timeline_data: dict) -> None:
    timeline = Timeline.model_validate(timeline_data)
    assert timeline.segments[0].clean_text == "大家好"
    assert timeline.segments[1].words == []


@pytest.mark.parametrize(
    ("start", "end"),
    [(-0.1, 1.0), (1.0, 1.0), (2.0, 1.0)],
)
def test_invalid_segment_time_range(
    timeline_data: dict, start: float, end: float
) -> None:
    data = deepcopy(timeline_data)
    data["segments"][0]["start"] = start
    data["segments"][0]["end"] = end
    data["segments"][0]["words"] = []
    with pytest.raises(ValidationError):
        Timeline.model_validate(data)


def test_segment_ids_must_be_unique(timeline_data: dict) -> None:
    data = deepcopy(timeline_data)
    data["segments"][1]["id"] = data["segments"][0]["id"]
    with pytest.raises(ValidationError, match="unique"):
        Timeline.model_validate(data)


def test_segments_must_be_chronological(timeline_data: dict) -> None:
    data = deepcopy(timeline_data)
    data["segments"][1]["start"] = 0.0
    data["segments"][1]["end"] = 0.5
    with pytest.raises(ValidationError, match="ordered"):
        Timeline.model_validate(data)


def test_timeline_json_round_trip_preserves_chinese(timeline_data: dict) -> None:
    timeline = Timeline.model_validate(timeline_data)
    encoded = timeline.model_dump_json()
    restored = Timeline.model_validate_json(encoded)
    assert "测试直播" in restored.video.path
    assert restored.project_id == "项目-中文路径"
    assert restored == timeline

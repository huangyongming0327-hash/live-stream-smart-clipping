from __future__ import annotations

import math

import pytest

from experiments.asr.common import (
    assess_silence,
    build_unified_result,
    new_segment,
    validate_unified_result,
)


def _result(segments):
    return build_unified_result(
        candidate="test", model_name="test", model_revision="1",
        runtime_version="1", compute_type="int8", input_sha256="a" * 64,
        segments=segments
    )


def test_unified_output_accepts_finite_monotonic_ranges():
    result = _result([
        new_segment(start=0.1, end=1.0, text="一"),
        new_segment(start=1.0, end=2.0, text="二"),
    ])
    validate_unified_result(result, 2.0)
    assert [item["id"] for item in result["segments"]] == ["seg-0001", "seg-0002"]


@pytest.mark.parametrize(
    "segments,duration",
    [
        ([new_segment(start=0.0, end=math.inf, text="x")], 2.0),
        ([new_segment(start=0.0, end=2.1, text="x")], 2.0),
        ([new_segment(start=1.0, end=1.0, text="x")], 2.0),
    ],
)
def test_unified_output_rejects_invalid_times(segments, duration):
    with pytest.raises(ValueError):
        validate_unified_result(_result(segments), duration)


def test_unified_output_rejects_non_monotonic_end_times():
    result = _result([
        new_segment(start=0.0, end=2.0, text="x"),
        new_segment(start=1.0, end=1.5, text="y"),
    ])
    with pytest.raises(ValueError, match="monotonic"):
        validate_unified_result(result, 3.0)


def test_silence_output_judgement():
    assert assess_silence(_result([]))["hallucination_detected"] is False
    assert assess_silence(_result([new_segment(start=0.0, end=1.0, text="幻觉")]))[
        "hallucination_detected"
    ] is True

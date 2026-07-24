from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from liveclip.schemas import CurrentAnalysis, calculate_score


def test_valid_analysis_sample(analysis_data: dict) -> None:
    analysis = CurrentAnalysis.model_validate(analysis_data)
    assert analysis.candidates[0].ranges.extended.contains(
        analysis.candidates[0].ranges.recommended
    )


def test_recommended_range_must_contain_core(analysis_data: dict) -> None:
    data = deepcopy(analysis_data)
    data["candidates"][0]["ranges"]["recommended"] = {
        "start": 11.0,
        "end": 19.0,
    }
    with pytest.raises(ValidationError, match="contain core"):
        CurrentAnalysis.model_validate(data)


def test_extended_range_must_contain_recommended(analysis_data: dict) -> None:
    data = deepcopy(analysis_data)
    data["candidates"][0]["ranges"]["extended"] = {
        "start": 9.0,
        "end": 21.0,
    }
    with pytest.raises(ValidationError, match="contain recommended"):
        CurrentAnalysis.model_validate(data)


@pytest.mark.parametrize("grade", ["C", "优秀", ""])
def test_invalid_grade_is_rejected(analysis_data: dict, grade: str) -> None:
    data = deepcopy(analysis_data)
    data["candidates"][0]["grade"] = grade
    with pytest.raises(ValidationError):
        CurrentAnalysis.model_validate(data)


@pytest.mark.parametrize("score", [-0.01, 100.01])
def test_candidate_score_is_bounded(analysis_data: dict, score: float) -> None:
    data = deepcopy(analysis_data)
    data["candidates"][0]["score"] = score
    with pytest.raises(ValidationError):
        CurrentAnalysis.model_validate(data)


def test_score_formula_boundaries() -> None:
    minimum = calculate_score([0, 0, 0, 0, 0, 0], 50)
    maximum = calculate_score([15, 15, 15, 15, 15, 15], 0)
    clamped = calculate_score([15, 15, 15, 15, 15, 15], 150)
    assert minimum.base_score == 0
    assert minimum.final_score == 0
    assert maximum.base_score == pytest.approx(100)
    assert maximum.final_score == pytest.approx(100)
    assert clamped.final_score == 0


def test_score_formula_rejects_invalid_components() -> None:
    with pytest.raises(ValueError, match="six"):
        calculate_score([10, 10], 0)
    with pytest.raises(ValueError, match="between 0 and 15"):
        calculate_score([20, 20, 20, 20, 20, 20], 0)
    with pytest.raises(ValueError, match="finite and non-negative"):
        calculate_score([15, 15, 15, 15, 15, 15], -1)


def test_analysis_json_round_trip(analysis_data: dict) -> None:
    analysis = CurrentAnalysis.model_validate(analysis_data)
    restored = CurrentAnalysis.model_validate_json(analysis.model_dump_json())
    assert restored == analysis
    assert restored.candidates[0].titles == ["中文标题候选"]

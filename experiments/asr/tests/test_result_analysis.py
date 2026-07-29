from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from experiments.asr.human_review.result_analysis import (
    ERROR_TAGS,
    MODEL_IDS,
    MODEL_NAMES,
    ManifestMismatchError,
    ReviewValidationError,
    analyze_validated_rows,
    decide_confidence,
    load_json_object,
    rank_models,
    render_human_review_result,
    render_production_baseline,
    run_analysis,
    validate_completed_review,
    validate_manifest,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _manifest() -> dict:
    clips = []
    for index in range(20):
        start = float(index * 2)
        end = start + 1.5
        clips.append(
            {
                "window_id": str(index + 1),
                "file": f"clips/window-{index + 1:03d}.wav",
                "original_start": start,
                "original_end": end,
                "actual_start": max(0.0, start - 0.8),
                "actual_end": end + 0.8,
                "duration_seconds": end - start + 1.6,
                "sha256": f"{index + 1:064x}",
            }
        )
    return {
        "schema_version": "1.0",
        "manifest_type": "asr_human_review_package",
        "source": {},
        "padding_seconds": 0.8,
        "window_count": 20,
        "clips": clips,
    }


def _review(manifest_sha: str) -> dict:
    windows = []
    for index in range(20):
        start = float(index * 2)
        end = start + 1.5
        windows.append(
            {
                "window_id": str(index + 1),
                "start": start,
                "end": end,
                "best_candidate": "SenseVoice",
                "severity": {
                    "SenseVoice": 0,
                    "Paraformer": 1,
                    "Faster-Whisper": 2,
                },
                "error_tags": {
                    "SenseVoice": [],
                    "Paraformer": ["标点/可读性"],
                    "Faster-Whisper": ["错字/替换"],
                },
                "reference_text": "",
                "audio_hard_to_hear": False,
                "notes": "",
                "reviewed": True,
            }
        )
    return {
        "schema_version": "1.0",
        "review_type": "asr_human_listening_review",
        "source_manifest_sha256": manifest_sha,
        "completed": True,
        "completed_window_count": 20,
        "total_window_count": 20,
        "windows": windows,
    }


def _files(tmp_path: Path) -> tuple[Path, Path, dict]:
    manifest_path = tmp_path / "review-manifest.json"
    _write_json(manifest_path, _manifest())
    review = _review(_sha(manifest_path))
    review_path = tmp_path / "completed.json"
    _write_json(review_path, review)
    return review_path, manifest_path, review


def _normalized(tmp_path: Path) -> list[dict]:
    review_path, manifest_path, _ = _files(tmp_path)
    manifest_sha = _sha(manifest_path)
    expected = validate_manifest(load_json_object(manifest_path))
    return validate_completed_review(
        load_json_object(review_path),
        expected,
        expected_manifest_sha256=manifest_sha,
    )


def _mutated_validation(
    tmp_path: Path,
    mutate,
) -> None:
    review_path, manifest_path, review = _files(tmp_path)
    mutate(review)
    _write_json(review_path, review)
    expected = validate_manifest(load_json_object(manifest_path))
    validate_completed_review(
        load_json_object(review_path),
        expected,
        expected_manifest_sha256=_sha(manifest_path),
    )


def test_normal_completed_20_window_review_and_manifest_match(tmp_path: Path) -> None:
    rows = _normalized(tmp_path)

    assert len(rows) == 20
    assert all(row["candidate"] == "sensevoice" for row in rows)


def test_manifest_mismatch_blocks_before_outputs(tmp_path: Path) -> None:
    review_path, manifest_path, review = _files(tmp_path)
    review["source_manifest_sha256"] = "f" * 64
    _write_json(review_path, review)
    output = tmp_path / "analysis"

    with pytest.raises(ManifestMismatchError):
        run_analysis(review_path, manifest_path, output)

    assert not output.exists()


def test_completed_false_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewValidationError, match="completed must be true"):
        _mutated_validation(
            tmp_path,
            lambda payload: payload.update(completed=False),
        )


def test_19_of_20_is_rejected(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["windows"].pop()
        payload["completed_window_count"] = 19
        payload["total_window_count"] = 19

    with pytest.raises(ReviewValidationError, match="completed_window_count"):
        _mutated_validation(tmp_path, mutate)


def test_duplicate_window_is_rejected(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["windows"][1]["window_id"] = "1"
        payload["windows"][1]["start"] = payload["windows"][0]["start"]
        payload["windows"][1]["end"] = payload["windows"][0]["end"]

    with pytest.raises(ReviewValidationError, match="duplicate window_id"):
        _mutated_validation(tmp_path, mutate)


def test_unknown_window_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewValidationError, match="unknown window_id"):
        _mutated_validation(
            tmp_path,
            lambda payload: payload["windows"][0].update(window_id="999"),
        )


def test_severity_extra_model_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewValidationError, match="extra=.*ExtraModel"):
        _mutated_validation(
            tmp_path,
            lambda payload: payload["windows"][0]["severity"].update(
                ExtraModel=0
            ),
        )


def test_error_tags_extra_model_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewValidationError, match="extra=.*ExtraModel"):
        _mutated_validation(
            tmp_path,
            lambda payload: payload["windows"][0]["error_tags"].update(
                ExtraModel=[]
            ),
        )


@pytest.mark.parametrize("value", [True, 1.5, "1", 4, -1])
def test_invalid_severity_is_rejected(tmp_path: Path, value: object) -> None:
    with pytest.raises(ReviewValidationError, match="severity"):
        _mutated_validation(
            tmp_path,
            lambda payload: payload["windows"][0]["severity"].update(
                SenseVoice=value
            ),
        )


@pytest.mark.parametrize("tags", [["其他", "其他"], ["未知标签"], "其他"])
def test_duplicate_or_unknown_error_tags_are_rejected(
    tmp_path: Path,
    tags: object,
) -> None:
    with pytest.raises(ReviewValidationError, match="error_tags|unknown"):
        _mutated_validation(
            tmp_path,
            lambda payload: payload["windows"][0]["error_tags"].update(
                SenseVoice=tags
            ),
        )


def test_explicit_winner_points_are_counted(tmp_path: Path) -> None:
    analysis = analyze_validated_rows(_normalized(tmp_path))
    model = analysis["subsets"]["all_windows"]["models"]["sensevoice"]

    assert model["explicit_win_count"] == 20
    assert model["winner_points_exact"] == "20/1"
    assert model["winner_window_share_percent_exact"] == "100/1"


def test_consistent_tie_splits_across_lowest_severity_models(
    tmp_path: Path,
) -> None:
    rows = _normalized(tmp_path)
    rows[0]["candidate"] = "tie"
    rows[0]["severity"] = {
        "sensevoice": 0,
        "paraformer": 0,
        "faster_whisper": 2,
    }
    subset = analyze_validated_rows(rows)["subsets"]["all_windows"]

    assert subset["models"]["sensevoice"]["tie_shared_points_exact"] == "1/2"
    assert subset["models"]["paraformer"]["tie_shared_points_exact"] == "1/2"
    assert subset["tie_inconsistent_count"] == 0


def test_inconsistent_tie_gets_no_winner_points(tmp_path: Path) -> None:
    rows = _normalized(tmp_path)
    rows[0]["candidate"] = "tie"
    rows[0]["severity"] = {
        "sensevoice": 0,
        "paraformer": 1,
        "faster_whisper": 2,
    }
    subset = analyze_validated_rows(rows)["subsets"]["all_windows"]

    assert subset["tie_inconsistent_count"] == 1
    assert subset["determinable_window_count"] == 19
    assert subset["models"]["sensevoice"]["winner_points_exact"] == "19/1"


def test_all_unusable_has_no_winner_but_keeps_quality(tmp_path: Path) -> None:
    rows = _normalized(tmp_path)
    rows[0]["candidate"] = "all_unusable"
    rows[0]["severity"] = {
        "sensevoice": 3,
        "paraformer": 3,
        "faster_whisper": 3,
    }
    subset = analyze_validated_rows(rows)["subsets"]["all_windows"]

    assert subset["all_unusable_count"] == 1
    assert subset["determinable_window_count"] == 19
    assert subset["models"]["sensevoice"]["severity_distribution"]["3"]["count"] == 1


def test_hard_to_hear_subset_is_calculated_separately(tmp_path: Path) -> None:
    rows = _normalized(tmp_path)
    rows[0]["audio_hard_to_hear"] = True
    rows[0]["candidate"] = "faster_whisper"
    result = analyze_validated_rows(rows)

    assert result["window_quality"]["audio_hard_to_hear_count"] == 1
    assert result["subsets"]["all_windows"]["window_count"] == 20
    assert result["subsets"]["clear_audio_windows"]["window_count"] == 19
    assert (
        result["subsets"]["clear_audio_windows"]["models"]["faster_whisper"][
            "explicit_win_count"
        ]
        == 0
    )


def test_aggregate_formula_keeps_exact_fraction(tmp_path: Path) -> None:
    analysis = analyze_validated_rows(_normalized(tmp_path))
    sensevoice = analysis["subsets"]["all_windows"]["models"]["sensevoice"]
    paraformer = analysis["subsets"]["all_windows"]["models"]["paraformer"]

    assert sensevoice["quality_scores"]["aggregate_quality_score_exact"] == "100/1"
    assert paraformer["quality_scores"]["aggregate_quality_score_exact"] == "130/3"


def _ranking_subset(
    aggregates: tuple[int, int, int],
    means: tuple[int, int, int] = (0, 0, 0),
    severe: tuple[int, int, int] = (0, 0, 0),
    wins: tuple[int, int, int] = (0, 0, 0),
) -> dict:
    model_ids = tuple(MODEL_IDS.values())
    return {
        "models": {
            model_id: {
                "quality_scores": {
                    "aggregate_quality_score_exact": f"{aggregates[index]}/1"
                },
                "mean_severity_exact": f"{means[index]}/1",
                "severity_distribution": {"3": {"count": severe[index]}},
                "winner_points_exact": f"{wins[index]}/1",
            }
            for index, model_id in enumerate(model_ids)
        }
    }


def test_ranking_uses_mean_severity_then_severity3_then_wins() -> None:
    subset = _ranking_subset(
        (80, 80, 80),
        means=(1, 0, 0),
        severe=(0, 2, 1),
        wins=(20, 20, 10),
    )

    assert rank_models(subset) == [
        "faster_whisper",
        "paraformer",
        "sensevoice",
    ]


def _decision_subset(
    primary_score: int,
    second_score: int,
    *,
    primary_mean: int = 0,
    second_mean: int = 1,
    primary_severe: int = 0,
    second_severe: int = 1,
    primary_wins: int = 10,
    second_wins: int = 8,
) -> dict:
    return {
        "models": {
            "sensevoice": {
                "quality_scores": {
                    "aggregate_quality_score_exact": f"{primary_score}/1"
                },
                "mean_severity_exact": f"{primary_mean}/1",
                "severity_distribution": {"3": {"count": primary_severe}},
                "winner_points_exact": f"{primary_wins}/1",
            },
            "paraformer": {
                "quality_scores": {
                    "aggregate_quality_score_exact": f"{second_score}/1"
                },
                "mean_severity_exact": f"{second_mean}/1",
                "severity_distribution": {"3": {"count": second_severe}},
                "winner_points_exact": f"{second_wins}/1",
            },
            "faster_whisper": {
                "quality_scores": {"aggregate_quality_score_exact": "0/1"},
                "mean_severity_exact": "3/1",
                "severity_distribution": {"3": {"count": 20}},
                "winner_points_exact": "0/1",
            },
        }
    }


def test_high_confidence_rule() -> None:
    subset = _decision_subset(90, 80)
    decision = decide_confidence(
        subset,
        subset,
        ["sensevoice", "paraformer", "faster_whisper"],
        ["sensevoice", "paraformer", "faster_whisper"],
    )

    assert decision["decision_confidence"] == "high"
    assert decision["decision_status"] == "confirmed_mvp_baseline"


def test_medium_confidence_rule() -> None:
    subset = _decision_subset(85, 80)
    decision = decide_confidence(
        subset,
        subset,
        ["sensevoice", "paraformer", "faster_whisper"],
        ["sensevoice", "paraformer", "faster_whisper"],
    )

    assert decision["decision_confidence"] == "medium"
    assert decision["decision_status"] == "provisional_mvp_baseline"


def test_low_confidence_rule_for_small_lead_or_clear_subset_conflict() -> None:
    subset = _decision_subset(82, 80)
    decision = decide_confidence(
        subset,
        subset,
        ["sensevoice", "paraformer", "faster_whisper"],
        ["paraformer", "sensevoice", "faster_whisper"],
    )

    assert decision["decision_confidence"] == "low"
    assert decision["decision_status"] == "insufficient_evidence"
    assert decision["supplemental_targeted_windows_recommended"] is True


def test_public_reports_exclude_user_text_and_paths(tmp_path: Path) -> None:
    review_path, manifest_path, review = _files(tmp_path)
    review["windows"][0]["reference_text"] = "SENSITIVE_TRANSCRIPT"
    review["windows"][0]["notes"] = "SENSITIVE_NOTE"
    _write_json(review_path, review)
    analysis = run_analysis(review_path, manifest_path, tmp_path / "analysis")

    public = render_human_review_result(analysis) + render_production_baseline(analysis)

    assert "SENSITIVE_TRANSCRIPT" not in public
    assert "SENSITIVE_NOTE" not in public
    assert str(tmp_path) not in public
    assert "C:\\" not in public


def test_local_outputs_are_deterministic(tmp_path: Path) -> None:
    review_path, manifest_path, _ = _files(tmp_path)
    output = tmp_path / "analysis"
    public_result = tmp_path / "public-result.md"
    public_baseline = tmp_path / "public-baseline.md"

    first = run_analysis(
        review_path,
        manifest_path,
        output,
        public_result_path=public_result,
        public_baseline_path=public_baseline,
    )
    files = [
        output / "asr-human-review-analysis.json",
        output / "asr-human-review-analysis.md",
        output / "asr-production-baseline.json",
        public_result,
        public_baseline,
    ]
    first_hashes = [_sha(path) for path in files]
    second = run_analysis(
        review_path,
        manifest_path,
        output,
        public_result_path=public_result,
        public_baseline_path=public_baseline,
    )

    assert [_sha(path) for path in files] == first_hashes
    assert first["decision"] == second["decision"]


def test_original_review_hash_is_unchanged(tmp_path: Path) -> None:
    review_path, manifest_path, _ = _files(tmp_path)
    before = _sha(review_path)

    analysis = run_analysis(review_path, manifest_path, tmp_path / "analysis")

    assert _sha(review_path) == before
    assert analysis["source_integrity"]["sha256_before"] == before
    assert analysis["source_integrity"]["sha256_after"] == before


def test_duplicate_json_object_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":"1.0","schema_version":"2.0"}', encoding="utf-8")

    with pytest.raises(ReviewValidationError, match="duplicate JSON object key"):
        load_json_object(path)

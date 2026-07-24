from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from experiments.asr.adapters.paraformer import (
    _build_paraformer_unified,
    _segments_from_result,
)
from experiments.asr.common import (
    TimelineUnavailableError,
    render_srt,
    write_run_artifacts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FULL_DURATION = 827.690688


def _unified(raw: list[dict]) -> dict:
    return _build_paraformer_unified(
        raw,
        FULL_DURATION,
        runtime_version="1.3.22",
        input_sha256="a" * 64,
    )


def _assert_non_monotonic_issue(
    issue: dict,
    *,
    raw_index: int,
    sentence_index: int | None,
    start: float,
    end: float,
    previous_start: float,
    previous_end: float,
) -> None:
    expected = {
        "raw_index": raw_index,
        "reason": "timestamp_non_monotonic",
        "raw_text_preserved": True,
        "start": start,
        "end": end,
        "previous_start": previous_start,
        "previous_end": previous_end,
        "timestamp_unit": "seconds",
    }
    if sentence_index is not None:
        expected["sentence_index"] = sentence_index
    assert issue == expected


@pytest.mark.parametrize(
    "item,expected_code,expected_reason",
    [
        ({"text": "测试文本"}, "PARAFORMER_TIMESTAMP_MISSING", "timestamp_missing"),
        (
            {"text": "测试文本", "timestamp": None},
            "PARAFORMER_TIMESTAMP_MISSING",
            "timestamp_missing",
        ),
        (
            {"text": "测试文本", "timestamp": []},
            "PARAFORMER_TIMESTAMP_MISSING",
            "timestamp_empty",
        ),
        (
            {"text": "测试文本", "timestamp": "invalid"},
            "PARAFORMER_TIMESTAMP_INVALID",
            "timestamp_invalid_format",
        ),
        (
            {"text": "测试文本", "timestamp": [[0, math.nan]]},
            "PARAFORMER_TIMESTAMP_INVALID",
            "timestamp_non_finite",
        ),
        (
            {"text": "测试文本", "timestamp": [[2_000, 1_000]]},
            "PARAFORMER_TIMESTAMP_INVALID",
            "timestamp_reversed",
        ),
        (
            {"text": "测试文本", "timestamp": [[0, FULL_DURATION * 1_000 + 1]]},
            "PARAFORMER_TIMESTAMP_INVALID",
            "timestamp_out_of_bounds",
        ),
        (
            {"text": "测试文本", "timestamp": [[100, 200], [50, 300]]},
            "PARAFORMER_TIMESTAMP_INVALID",
            "timestamp_non_monotonic",
        ),
    ],
)
def test_untimed_top_level_text_never_becomes_a_forged_segment(
    item: dict,
    expected_code: str,
    expected_reason: str,
) -> None:
    extraction = _segments_from_result([item], FULL_DURATION)

    assert extraction.segments == []
    assert extraction.timeline_status == "unavailable"
    assert extraction.warnings[0]["code"] == "PARAFORMER_UNTIMED_TEXT_EXCLUDED"
    assert extraction.warnings[0]["raw_indices"] == [0]
    assert extraction.warnings[0]["raw_text_preserved"] is True
    assert extraction.errors[0]["code"] == expected_code
    entry = extraction.errors[0]["entries"][0]
    assert entry["raw_index"] == 0
    assert entry["reason"] == expected_reason
    assert entry["raw_text_preserved"] is True
    if expected_reason == "timestamp_non_monotonic":
        _assert_non_monotonic_issue(
            entry,
            raw_index=0,
            sentence_index=None,
            start=0.05,
            end=0.3,
            previous_start=0.1,
            previous_end=0.2,
        )


@pytest.mark.parametrize(
    "sentence,expected_code,expected_reason",
    [
        ({"text": "测试文本"}, "PARAFORMER_TIMESTAMP_MISSING", "timestamp_missing"),
        (
            {"text": "测试文本", "start": None, "end": 1_000},
            "PARAFORMER_TIMESTAMP_MISSING",
            "timestamp_missing",
        ),
        (
            {"text": "测试文本", "start": "0", "end": 1_000},
            "PARAFORMER_TIMESTAMP_INVALID",
            "timestamp_invalid_format",
        ),
        (
            {"text": "测试文本", "start": 0, "end": math.inf},
            "PARAFORMER_TIMESTAMP_INVALID",
            "timestamp_non_finite",
        ),
        (
            {"text": "测试文本", "start": 1_000, "end": 1_000},
            "PARAFORMER_TIMESTAMP_INVALID",
            "timestamp_reversed",
        ),
        (
            {"text": "测试文本", "start": 0, "end": FULL_DURATION * 1_000 + 1},
            "PARAFORMER_TIMESTAMP_INVALID",
            "timestamp_out_of_bounds",
        ),
    ],
)
def test_invalid_sentence_info_time_never_enters_the_timeline(
    sentence: dict,
    expected_code: str,
    expected_reason: str,
) -> None:
    extraction = _segments_from_result(
        [{"text": "测试文本", "sentence_info": [sentence]}],
        FULL_DURATION,
    )

    assert extraction.segments == []
    assert extraction.timeline_status == "unavailable"
    assert extraction.errors[0]["code"] == expected_code
    assert extraction.errors[0]["entries"] == [
        {
            "raw_index": 0,
            "reason": expected_reason,
            "raw_text_preserved": True,
            "sentence_index": 0,
        }
    ]


def test_reversed_sentence_info_entry_is_excluded_before_common_sorting() -> None:
    raw = [{
        "text": "测试文本",
        "sentence_info": [
            {"text": "后句", "start": 1_000, "end": 2_000},
            {"text": "前句", "start": 100, "end": 500},
        ],
    }]
    unified = _unified(raw)

    assert [(item["start"], item["end"], item["text"]) for item in unified["segments"]] == [
        (1.0, 2.0, "后句")
    ]
    assert unified["timeline_status"] == "partial"
    assert unified["warnings"][0]["code"] == "PARAFORMER_UNTIMED_TEXT_EXCLUDED"
    assert unified["errors"][0]["code"] == "PARAFORMER_TIMESTAMP_INVALID"
    _assert_non_monotonic_issue(
        unified["errors"][0]["entries"][0],
        raw_index=0,
        sentence_index=1,
        start=0.1,
        end=0.5,
        previous_start=1.0,
        previous_end=2.0,
    )
    srt = render_srt(unified["segments"])
    assert "后句" in srt
    assert "前句" not in srt


def test_sentence_info_end_regression_is_structurally_excluded(tmp_path: Path) -> None:
    raw = [{
        "sentence_info": [
            {"text": "第一句", "start": 0, "end": 2_000},
            {"text": "第二句", "start": 1_000, "end": 1_500},
        ],
    }]
    unified = _unified(raw)

    assert [item["text"] for item in unified["segments"]] == ["第一句"]
    assert unified["timeline_status"] == "partial"
    _assert_non_monotonic_issue(
        unified["errors"][0]["entries"][0],
        raw_index=0,
        sentence_index=1,
        start=1.0,
        end=1.5,
        previous_start=0.0,
        previous_end=2.0,
    )
    write_run_artifacts(
        tmp_path,
        raw=raw,
        unified=unified,
        metrics={"success": True},
        audio_duration=FULL_DURATION,
    )
    assert json.loads((tmp_path / "raw.json").read_text(encoding="utf-8")) == raw
    written_unified = json.loads(
        (tmp_path / "unified.json").read_text(encoding="utf-8")
    )
    assert written_unified["errors"][0]["entries"][0]["reason"] == (
        "timestamp_non_monotonic"
    )
    assert "第二句" not in (tmp_path / "transcript.srt").read_text(encoding="utf-8")


def test_cross_raw_sentence_info_regression_is_excluded() -> None:
    unified = _unified([
        {
            "text": "后段",
            "sentence_info": [{"text": "后段", "start": 1_000, "end": 2_000}],
        },
        {
            "text": "前段",
            "sentence_info": [{"text": "前段", "start": 100, "end": 500}],
        },
    ])

    assert [item["text"] for item in unified["segments"]] == ["后段"]
    assert unified["timeline_status"] == "partial"
    _assert_non_monotonic_issue(
        unified["errors"][0]["entries"][0],
        raw_index=1,
        sentence_index=0,
        start=0.1,
        end=0.5,
        previous_start=1.0,
        previous_end=2.0,
    )


def test_later_sentence_can_recover_against_last_accepted_segment() -> None:
    unified = _unified([{
        "sentence_info": [
            {"text": "正常一", "start": 1_000, "end": 2_000},
            {"text": "倒序", "start": 100, "end": 500},
            {"text": "正常二", "start": 2_000, "end": 2_500},
        ],
    }])

    assert [item["text"] for item in unified["segments"]] == ["正常一", "正常二"]
    assert unified["timeline_status"] == "partial"
    issue = unified["errors"][0]["entries"][0]
    assert issue["reason"] == "timestamp_non_monotonic"
    assert (issue["previous_start"], issue["previous_end"]) == (1.0, 2.0)


def test_all_unusable_non_monotonic_timing_preserves_failure_artifacts(
    tmp_path: Path,
) -> None:
    raw = [{"text": "全部异常", "timestamp": [[1_000, 2_000], [100, 500]]}]
    unified = _unified(raw)

    assert unified["segments"] == []
    assert unified["timeline_status"] == "unavailable"
    _assert_non_monotonic_issue(
        unified["errors"][0]["entries"][0],
        raw_index=0,
        sentence_index=None,
        start=0.1,
        end=0.5,
        previous_start=1.0,
        previous_end=2.0,
    )
    with pytest.raises(TimelineUnavailableError):
        write_run_artifacts(
            tmp_path,
            raw=raw,
            unified=unified,
            metrics={"success": True},
            audio_duration=FULL_DURATION,
        )
    assert (tmp_path / "raw.json").exists()
    assert (tmp_path / "unified.json").exists()
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "transcript.txt").exists()
    assert not (tmp_path / "transcript.srt").exists()


def test_empty_paraformer_result_is_normal_and_not_timeline_unavailable(
    tmp_path: Path,
) -> None:
    extraction = _segments_from_result([], FULL_DURATION)
    unified = _unified([])

    assert extraction.segments == []
    assert extraction.warnings == []
    assert extraction.errors == []
    assert extraction.timeline_status is None
    assert unified["segments"] == []
    assert unified["warnings"] == []
    assert unified["errors"] == []
    assert "timeline_status" not in unified

    write_run_artifacts(
        tmp_path,
        raw=[],
        unified=unified,
        metrics={"success": True},
        audio_duration=FULL_DURATION,
    )
    assert (tmp_path / "transcript.srt").read_text(encoding="utf-8") == ""
    assert json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))[
        "success"
    ] is True


def test_no_timestamp_preserves_raw_trace_but_fails_without_srt(tmp_path: Path) -> None:
    raw = [{"text": "测试文本"}]
    unified = _unified(raw)

    assert unified["segments"] == []
    assert unified["timeline_status"] == "unavailable"
    assert unified["errors"][0]["code"] == "PARAFORMER_TIMESTAMP_MISSING"
    assert all(
        not (segment.get("start") == 0 and segment.get("end") == FULL_DURATION)
        for segment in unified["segments"]
    )

    with pytest.raises(TimelineUnavailableError, match="no usable"):
        write_run_artifacts(
            tmp_path,
            raw=raw,
            unified=unified,
            metrics={"candidate": "paraformer-zh-funasr"},
            audio_duration=FULL_DURATION,
        )

    assert json.loads((tmp_path / "raw.json").read_text(encoding="utf-8")) == raw
    written_unified = json.loads((tmp_path / "unified.json").read_text(encoding="utf-8"))
    assert written_unified["warnings"][0]["raw_indices"] == [0]
    assert written_unified["errors"][0]["timeline_status"] == "unavailable"
    assert json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))[
        "success"
    ] is False
    assert (tmp_path / "transcript.txt").read_text(encoding="utf-8") == ""
    assert not (tmp_path / "transcript.srt").exists()


def test_partial_timestamps_keep_only_evidenced_segments_and_record_indices(
    tmp_path: Path,
) -> None:
    raw = [
        {"sentence_info": [{"text": "有时间", "start": 100, "end": 900}]},
        {"text": "无时间"},
        {"text": "时间无效", "timestamp": [[2_000, 1_000]]},
    ]
    unified = _unified(raw)

    assert [(item["start"], item["end"], item["text"]) for item in unified["segments"]] == [
        (0.1, 0.9, "有时间")
    ]
    assert unified["timeline_status"] == "partial"
    assert unified["warnings"][0]["untimed_text_count"] == 2
    assert unified["warnings"][0]["raw_indices"] == [1, 2]
    assert {item["code"] for item in unified["errors"]} == {
        "PARAFORMER_TIMESTAMP_MISSING",
        "PARAFORMER_TIMESTAMP_INVALID",
    }

    write_run_artifacts(
        tmp_path,
        raw=raw,
        unified=unified,
        metrics={"candidate": "paraformer-zh-funasr"},
        audio_duration=FULL_DURATION,
    )
    srt = (tmp_path / "transcript.srt").read_text(encoding="utf-8")
    assert "有时间" in srt
    assert "无时间" not in srt
    assert "时间无效" not in srt


def test_valid_top_level_timestamp_is_used_without_guessing() -> None:
    unified = _unified(
        [{"text": "真实范围", "timestamp": [[100, 300], [350, 800]]}]
    )

    assert [(item["start"], item["end"], item["text"]) for item in unified["segments"]] == [
        (0.1, 0.8, "真实范围")
    ]
    assert "timeline_status" not in unified
    assert unified["errors"] == []
    assert unified["warnings"] == [
        "FunASR did not return sentence_info; fallback timestamp granularity was used."
    ]


@pytest.mark.parametrize("run_kind", ["cold", "warm"])
def test_existing_399_sentence_info_result_is_byte_for_byte_reproducible(
    run_kind: str,
    tmp_path: Path,
) -> None:
    result_dir = (
        PROJECT_ROOT / "runtime" / "asr-benchmark" / "results" / "paraformer" / run_kind
    )
    raw = json.loads((result_dir / "raw.json").read_text(encoding="utf-8"))
    expected = json.loads((result_dir / "unified.json").read_text(encoding="utf-8"))
    actual = _build_paraformer_unified(
        raw,
        FULL_DURATION,
        runtime_version=expected["runtime_version"],
        input_sha256=expected["input_sha256"],
    )

    assert actual == expected
    assert len(actual["segments"]) == 399
    assert sum(item["end"] - item["start"] for item in actual["segments"]) == pytest.approx(
        696.75
    )
    assert render_srt(actual["segments"]) == (result_dir / "transcript.srt").read_text(
        encoding="utf-8"
    )
    expected_txt = (result_dir / "transcript.txt").read_text(encoding="utf-8")
    actual_txt = "\n".join(item["text"] for item in actual["segments"]) + "\n"
    assert actual_txt == expected_txt

    write_run_artifacts(
        tmp_path,
        raw=raw,
        unified=actual,
        metrics={},
        audio_duration=FULL_DURATION,
    )
    assert (tmp_path / "unified.json").read_bytes() == (result_dir / "unified.json").read_bytes()
    assert (tmp_path / "transcript.srt").read_bytes() == (result_dir / "transcript.srt").read_bytes()
    assert (tmp_path / "transcript.txt").read_bytes() == (result_dir / "transcript.txt").read_bytes()

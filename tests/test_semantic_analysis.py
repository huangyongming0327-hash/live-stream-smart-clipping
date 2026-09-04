from __future__ import annotations

import hashlib
import json
import urllib.error
from pathlib import Path
from typing import Any, Callable

import pytest

from liveclip.analysis import pipeline
from liveclip.analysis.client import (
    AnalysisClientError,
    LLMConfig,
    OpenAICompatibleClient,
    load_config,
)
from liveclip.analysis.pipeline import build_windows, run_analysis
from liveclip.analysis.schema import (
    AnalysisError,
    ModelResponseError,
    parse_model_response,
    validate_analysis,
)
from liveclip.cli import main


SECRET = "SYNTHETIC_TEST_API_KEY"


def make_timeline(
    segment_count: int = 4,
    *,
    segment_ms: int = 10_000,
    text: str = "这是用于测试的字幕文本",
) -> dict[str, Any]:
    duration_ms = max(1, segment_count * segment_ms)
    return {
        "schema_version": "1.0",
        "source": {
            "file_name": "真实样本.mp4",
            "duration_ms": duration_ms,
            "sha256": "a" * 64,
        },
        "asr": {
            "engine": "paraformer",
            "language": "zh",
            "completed": True,
        },
        "segments": [
            {
                "id": index,
                "start_ms": (index - 1) * segment_ms,
                "end_ms": index * segment_ms,
                "text_raw": f"{text}{index}",
                "text": f"{text}{index}",
                "speaker": None,
                "is_question": False,
                "is_uncertain": False,
            }
            for index in range(1, segment_count + 1)
        ],
    }


def write_timeline(path: Path, timeline: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(timeline, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return path


def model_payload(
    segments: list[dict[str, Any]],
    *,
    score: int = 75,
    candidate_range: tuple[int, int] | None = None,
) -> str:
    start_id = segments[0]["id"]
    end_id = segments[-1]["id"]
    candidate_start, candidate_end = candidate_range or (
        start_id,
        min(start_id + 1, end_id),
    )
    content_value = min(score, 25)
    remaining = score - content_value
    problem_solving = min(max(remaining, 0), 20)
    remaining -= problem_solving
    emotion = min(max(remaining, 0), 15)
    remaining -= emotion
    density = min(max(remaining, 0), 15)
    remaining -= density
    hook = min(max(remaining, 0), 15)
    remaining -= hook
    completeness = min(max(remaining, 0), 10)
    candidate = {
        "start_segment_id": candidate_start,
        "end_segment_id": candidate_end,
        "title": "候选标题",
        "reason": "内容完整且具有独立传播价值",
        "quote_segment_id": candidate_start,
        "content_value": content_value,
        "problem_solving": problem_solving,
        "emotion_or_reversal": emotion,
        "information_density": density,
        "hook_and_shareability": hook,
        "completeness": completeness,
        "risk_penalty": 0,
    }
    duration_ms = (
        segments[candidate_end - start_id]["end_ms"]
        - segments[candidate_start - start_id]["start_ms"]
    )
    payload = {
        "topics": [
            {
                "start_segment_id": start_id,
                "end_segment_id": end_id,
                "title": "窗口话题",
                "summary": "窗口摘要",
            }
        ],
        "candidates": (
            [candidate]
            if candidate_range is not None or duration_ms >= 15_000
            else []
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


def make_candidate(
    segments: list[dict[str, Any]],
    start_id: int,
    end_id: int,
    *,
    title: str,
) -> dict[str, Any]:
    candidate = json.loads(
        model_payload(segments, candidate_range=(start_id, end_id))
    )["candidates"][0]
    candidate["title"] = title
    return candidate


def make_topics(
    *ranges: tuple[int, int],
) -> list[dict[str, Any]]:
    return [
        {
            "start_segment_id": start_id,
            "end_segment_id": end_id,
            "title": f"话题{index}",
            "summary": f"话题{index}摘要",
        }
        for index, (start_id, end_id) in enumerate(ranges, 1)
    ]


def repaired_client(payload: Any) -> "FakeClient":
    repaired = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False)
    )
    return FakeClient(
        lambda _segments, call: "首次输出无效" if call == 1 else repaired
    )


class FakeClient:
    def __init__(
        self,
        responder: Callable[[list[dict[str, Any]], int], str | BaseException],
        *,
        model: str = "fake-model",
        host: str = "fake.invalid",
    ) -> None:
        self.config = LLMConfig(
            endpoint=f"https://{host}/v1/chat/completions",
            api_key=SECRET,
            model=model,
            endpoint_host=host,
        )
        self.responder = responder
        self.request_count = 0
        self.calls: list[dict[str, Any]] = []

    def analyze_window(
        self,
        segments: list[dict[str, Any]],
        *,
        repair_error: str | None = None,
        previous_response: str | None = None,
    ) -> str:
        self.request_count += 1
        self.calls.append(
            {
                "ids": [segment["id"] for segment in segments],
                "repair_error": repair_error,
                "previous_response": previous_response,
            }
        )
        result = self.responder(segments, self.request_count)
        if isinstance(result, BaseException):
            raise result
        return result


def always_valid(segments: list[dict[str, Any]], _: int) -> str:
    return model_payload(segments)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(schema_version="2.0"),
        lambda value: value["asr"].update(completed=False),
        lambda value: value["segments"][1].update(id=3),
        lambda value: value["segments"][1].update(start_ms=5_000),
        lambda value: value["segments"][0].update(text=""),
    ],
)
def test_timeline_input_validation_rejects_invalid_data(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    timeline = make_timeline()
    mutate(timeline)
    path = write_timeline(tmp_path / "timeline.json", timeline)
    with pytest.raises(AnalysisError, match="timeline 校验失败"):
        run_analysis(path, client=FakeClient(always_valid), progress=lambda _: None)


def test_empty_timeline_skips_api_and_supports_chinese_path_without_config(
    tmp_path: Path,
) -> None:
    path = write_timeline(
        tmp_path / "中文 路径 (测试)" / "timeline.json",
        make_timeline(0),
    )
    result = run_analysis(path, environ={}, progress=lambda _: None)
    output = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert result.window_count == 0
    assert result.request_count == 0
    assert output["topics"] == []
    assert output["candidates"] == []
    assert output["analysis"]["model"] == "not_used"


def test_windows_split_by_time_and_characters_without_overlap() -> None:
    time_segments = make_timeline(62)["segments"]
    time_windows = build_windows(time_segments)
    assert [len(window) for window in time_windows] == [60, 2]
    assert time_windows[0][-1]["id"] + 1 == time_windows[1][0]["id"]

    character_segments = make_timeline(3, text="字" * 6_000)["segments"]
    character_windows = build_windows(character_segments)
    assert [len(window) for window in character_windows] == [1, 1, 1]


def test_single_large_segment_is_not_split() -> None:
    segments = make_timeline(1, segment_ms=700_000, text="字" * 13_000)["segments"]
    assert build_windows(segments) == [segments]


def test_missing_environment_variables_are_named() -> None:
    with pytest.raises(
        AnalysisClientError,
        match=(
            "LIVECLIP_LLM_ENDPOINT, LIVECLIP_LLM_API_KEY, LIVECLIP_LLM_MODEL"
        ),
    ):
        load_config({})


def test_endpoint_must_be_complete_https_url() -> None:
    environment = {
        "LIVECLIP_LLM_ENDPOINT": "http://example.invalid/v1/chat/completions",
        "LIVECLIP_LLM_API_KEY": SECRET,
        "LIVECLIP_LLM_MODEL": "test-model",
    }
    with pytest.raises(AnalysisClientError, match="HTTPS"):
        load_config(environment)


def test_api_key_never_enters_progress_or_state(tmp_path: Path) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline(61))

    def interrupt_second(
        segments: list[dict[str, Any]],
        call: int,
    ) -> str | BaseException:
        return model_payload(segments) if call == 1 else KeyboardInterrupt()

    messages: list[str] = []
    with pytest.raises(KeyboardInterrupt):
        run_analysis(
            path,
            client=FakeClient(interrupt_second),
            progress=messages.append,
        )
    state_text = (
        tmp_path / ".analysis_work" / "analysis_state.json"
    ).read_text(encoding="utf-8")
    assert SECRET not in state_text
    assert all(SECRET not in message for message in messages)


def test_invalid_json_gets_exactly_one_repair_retry(tmp_path: Path) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline())
    client = FakeClient(
        lambda segments, call: "not-json" if call == 1 else model_payload(segments)
    )
    result = run_analysis(path, client=client, progress=lambda _: None)
    assert result.request_count == 2
    assert client.calls[0]["repair_error"] is None
    assert "合法 JSON" in client.calls[1]["repair_error"]


def test_second_invalid_json_stops_and_keeps_no_completed_output(tmp_path: Path) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline())
    client = FakeClient(lambda _segments, _call: "still-not-json")
    with pytest.raises(AnalysisError, match="修复重试后仍无效"):
        run_analysis(path, client=client, progress=lambda _: None)
    assert client.request_count == 2
    assert not (tmp_path / "current_analysis.json").exists()


def test_repair_keeps_valid_candidate_and_discards_bad_duration_and_cross_topic(
    tmp_path: Path,
) -> None:
    timeline = make_timeline(6)
    segments = timeline["segments"]
    valid = make_candidate(segments, 1, 2, title="合法候选")
    too_short = make_candidate(segments, 3, 3, title="时长错误")
    cross_topic = make_candidate(segments, 3, 4, title="跨话题")
    payload = {
        "topics": make_topics((1, 3), (4, 6)),
        "candidates": [valid, too_short, cross_topic],
    }
    path = write_timeline(tmp_path / "timeline.json", timeline)
    client = repaired_client(payload)

    result = run_analysis(path, client=client, progress=lambda _: None)
    output = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert result.request_count == 2
    assert [candidate["title"] for candidate in output["candidates"]] == ["合法候选"]
    validate_analysis(output, timeline=timeline)


def test_first_response_stays_strict_before_candidate_tolerant_repair(
    tmp_path: Path,
) -> None:
    timeline = make_timeline(4)
    segments = timeline["segments"]
    valid = make_candidate(segments, 1, 2, title="合法候选")
    too_short = make_candidate(segments, 3, 3, title="时长错误")
    payload = json.dumps(
        {
            "topics": make_topics((1, 4)),
            "candidates": [valid, too_short],
        },
        ensure_ascii=False,
    )
    path = write_timeline(tmp_path / "timeline.json", timeline)
    client = FakeClient(lambda _segments, _call: payload)

    output_path = run_analysis(
        path,
        client=client,
        progress=lambda _: None,
    ).output_path
    output = json.loads(output_path.read_text(encoding="utf-8"))

    assert client.request_count == 2
    assert "15—180" in client.calls[1]["repair_error"]
    assert len(output["candidates"]) == 1


def test_repair_discards_only_candidate_with_quote_outside_range(
    tmp_path: Path,
) -> None:
    timeline = make_timeline(6)
    segments = timeline["segments"]
    valid = make_candidate(segments, 1, 2, title="合法候选")
    bad_quote = make_candidate(segments, 3, 4, title="引用越界")
    bad_quote["quote_segment_id"] = 5
    payload = {
        "topics": make_topics((1, 6)),
        "candidates": [valid, bad_quote],
    }
    path = write_timeline(tmp_path / "timeline.json", timeline)

    output_path = run_analysis(
        path,
        client=repaired_client(payload),
        progress=lambda _: None,
    ).output_path
    output = json.loads(output_path.read_text(encoding="utf-8"))

    assert [candidate["title"] for candidate in output["candidates"]] == ["合法候选"]
    validate_analysis(output, timeline=timeline)


def test_repair_discards_only_candidate_with_score_out_of_range(
    tmp_path: Path,
) -> None:
    timeline = make_timeline(6)
    segments = timeline["segments"]
    valid = make_candidate(segments, 1, 2, title="合法候选")
    bad_score = make_candidate(segments, 3, 4, title="分数越界")
    bad_score["content_value"] = 26
    payload = {
        "topics": make_topics((1, 6)),
        "candidates": [valid, bad_score],
    }
    path = write_timeline(tmp_path / "timeline.json", timeline)

    output_path = run_analysis(
        path,
        client=repaired_client(payload),
        progress=lambda _: None,
    ).output_path
    output = json.loads(output_path.read_text(encoding="utf-8"))

    assert [candidate["title"] for candidate in output["candidates"]] == ["合法候选"]
    validate_analysis(output, timeline=timeline)


def test_repair_discards_only_candidate_with_invalid_fields(tmp_path: Path) -> None:
    timeline = make_timeline(6)
    segments = timeline["segments"]
    valid = make_candidate(segments, 1, 2, title="合法候选")
    bad_fields = make_candidate(segments, 3, 4, title="字段错误")
    del bad_fields["reason"]
    payload = {
        "topics": make_topics((1, 6)),
        "candidates": [valid, bad_fields],
    }
    path = write_timeline(tmp_path / "timeline.json", timeline)

    output_path = run_analysis(
        path,
        client=repaired_client(payload),
        progress=lambda _: None,
    ).output_path
    output = json.loads(output_path.read_text(encoding="utf-8"))

    assert [candidate["title"] for candidate in output["candidates"]] == ["合法候选"]
    validate_analysis(output, timeline=timeline)


def test_repair_with_all_candidates_invalid_completes_with_empty_candidates(
    tmp_path: Path,
) -> None:
    timeline = make_timeline(6)
    segments = timeline["segments"]
    too_short = make_candidate(segments, 1, 1, title="时长错误")
    bad_quote = make_candidate(segments, 2, 3, title="引用越界")
    bad_quote["quote_segment_id"] = 4
    bad_score = make_candidate(segments, 4, 5, title="分数越界")
    bad_score["risk_penalty"] = 31
    payload = {
        "topics": make_topics((1, 6)),
        "candidates": [too_short, bad_quote, bad_score],
    }
    path = write_timeline(tmp_path / "timeline.json", timeline)
    client = repaired_client(payload)

    result = run_analysis(path, client=client, progress=lambda _: None)
    output = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert client.request_count == 2
    assert output["candidates"] == []
    validate_analysis(output, timeline=timeline)


@pytest.mark.parametrize(
    ("repaired", "message"),
    [
        ("repair-json-is-broken", "合法 JSON"),
        (
            {"topics": make_topics((1, 4), (4, 6)), "candidates": []},
            "topic 不得重叠",
        ),
        (
            {"topics": make_topics((1, 99)), "candidates": []},
            "topic segment 范围无效",
        ),
        ({"topics": make_topics((1, 6)), "candidates": {}}, "必须是数组"),
    ],
    ids=[
        "broken-json",
        "overlapping-topics",
        "topic-unknown-segment",
        "candidates-not-array",
    ],
)
def test_repair_keeps_structural_and_topic_failures_fatal_without_third_request(
    tmp_path: Path,
    repaired: Any,
    message: str,
) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline(6))
    client = repaired_client(repaired)

    with pytest.raises(AnalysisError, match=message):
        run_analysis(path, client=client, progress=lambda _: None)

    assert client.request_count == 2
    assert not (tmp_path / "current_analysis.json").exists()


def test_repair_with_more_than_three_candidates_remains_fatal(tmp_path: Path) -> None:
    timeline = make_timeline(8)
    segments = timeline["segments"]
    payload = {
        "topics": make_topics((1, 8)),
        "candidates": [
            make_candidate(segments, start_id, start_id + 1, title=f"候选{index}")
            for index, start_id in enumerate((1, 3, 5, 7), 1)
        ],
    }
    path = write_timeline(tmp_path / "timeline.json", timeline)
    client = repaired_client(payload)

    with pytest.raises(AnalysisError, match="最多返回 3"):
        run_analysis(path, client=client, progress=lambda _: None)

    assert client.request_count == 2
    assert not (tmp_path / "current_analysis.json").exists()


def test_filtered_repair_saves_state_and_resumes_from_next_window(
    tmp_path: Path,
) -> None:
    timeline = make_timeline(61)
    path = write_timeline(tmp_path / "timeline.json", timeline)

    def interrupt_after_filtered_window(
        segments: list[dict[str, Any]],
        call: int,
    ) -> str | BaseException:
        if call == 1:
            return "首次输出无效"
        if call == 2:
            valid = make_candidate(segments, 1, 2, title="合法候选")
            invalid = make_candidate(segments, 3, 3, title="时长错误")
            return json.dumps(
                {
                    "topics": make_topics((1, 60)),
                    "candidates": [valid, invalid],
                },
                ensure_ascii=False,
            )
        return KeyboardInterrupt()

    first_client = FakeClient(interrupt_after_filtered_window)
    with pytest.raises(KeyboardInterrupt):
        run_analysis(path, client=first_client, progress=lambda _: None)

    state_path = tmp_path / ".analysis_work" / "analysis_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert first_client.request_count == 3
    assert [call["ids"][0] for call in first_client.calls] == [1, 1, 61]
    assert state["completed_window_count"] == 1
    assert len(state["window_results"][0]["candidates"]) == 1

    resumed_client = FakeClient(always_valid)
    result = run_analysis(path, client=resumed_client, progress=lambda _: None)
    output = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert result.resumed_from_window == 2
    assert resumed_client.request_count == 1
    assert resumed_client.calls[0]["ids"] == [61]
    assert len(output["candidates"]) == 1
    validate_analysis(output, timeline=timeline)
    assert not (tmp_path / ".analysis_work").exists()


def test_unknown_segment_id_triggers_repair_retry() -> None:
    segments = make_timeline()["segments"]
    payload = json.loads(model_payload(segments))
    payload["candidates"][0]["end_segment_id"] = 99
    with pytest.raises(ModelResponseError, match="segment 范围无效"):
        parse_model_response(json.dumps(payload), window_segments=segments)


@pytest.mark.parametrize("duration_ms", [14_999, 180_001])
def test_candidate_duration_must_be_15_to_180_seconds(duration_ms: int) -> None:
    segments = make_timeline(1, segment_ms=duration_ms)["segments"]
    with pytest.raises(ModelResponseError, match="15—180"):
        parse_model_response(
            model_payload(segments, candidate_range=(1, 1)),
            window_segments=segments,
        )


def test_score_bounds_and_program_total_score(tmp_path: Path) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline())
    result = run_analysis(path, client=FakeClient(always_valid), progress=lambda _: None)
    output = json.loads(result.output_path.read_text(encoding="utf-8"))
    candidate = output["candidates"][0]
    assert candidate["total_score"] == 75
    assert candidate["recommended"] is True

    invalid = json.loads(model_payload(make_timeline()["segments"]))
    invalid["candidates"][0]["content_value"] = 26
    with pytest.raises(ModelResponseError, match="0—25"):
        parse_model_response(
            json.dumps(invalid),
            window_segments=make_timeline()["segments"],
        )


def test_candidates_below_60_are_filtered(tmp_path: Path) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline())
    client = FakeClient(lambda segments, _call: model_payload(segments, score=59))
    output_path = run_analysis(path, client=client, progress=lambda _: None).output_path
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["candidates"] == []


def test_global_candidate_limit_is_20() -> None:
    timeline = make_timeline(21, segment_ms=15_000)
    results = []
    for index in range(1, 22):
        segment = [timeline["segments"][index - 1]]
        results.append(
            json.loads(model_payload(segment, candidate_range=(index, index)))
        )
    output = pipeline._build_output(
        timeline=timeline,
        timeline_file_name="timeline.json",
        timeline_sha256="b" * 64,
        model="fake-model",
        window_results=results,
    )
    assert len(output["candidates"]) == 20
    validate_analysis(output, timeline=timeline)


def test_over_60_percent_overlap_keeps_higher_score() -> None:
    timeline = make_timeline(4)
    segments = timeline["segments"]
    first = json.loads(model_payload(segments, score=80, candidate_range=(1, 3)))
    second_candidate = json.loads(
        model_payload(segments, score=70, candidate_range=(2, 4))
    )["candidates"][0]
    first["candidates"].append(second_candidate)
    output = pipeline._build_output(
        timeline=timeline,
        timeline_file_name="timeline.json",
        timeline_sha256="b" * 64,
        model="fake-model",
        window_results=[first],
    )
    assert len(output["candidates"]) == 1
    assert output["candidates"][0]["start_segment_id"] == 1


def test_quote_and_times_are_copied_from_real_segments(tmp_path: Path) -> None:
    timeline = make_timeline()
    path = write_timeline(tmp_path / "timeline.json", timeline)
    output_path = run_analysis(
        path,
        client=FakeClient(always_valid),
        progress=lambda _: None,
    ).output_path
    output = json.loads(output_path.read_text(encoding="utf-8"))
    topic = output["topics"][0]
    candidate = output["candidates"][0]
    assert topic["start_ms"] == timeline["segments"][0]["start_ms"]
    assert topic["end_ms"] == timeline["segments"][-1]["end_ms"]
    assert candidate["start_ms"] == timeline["segments"][0]["start_ms"]
    assert candidate["end_ms"] == timeline["segments"][1]["end_ms"]
    assert candidate["quote"] == timeline["segments"][0]["text"]


def test_interruption_resumes_from_next_window(tmp_path: Path) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline(61))

    def interrupt_second(
        segments: list[dict[str, Any]],
        call: int,
    ) -> str | BaseException:
        return model_payload(segments) if call == 1 else KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_analysis(
            path,
            client=FakeClient(interrupt_second),
            progress=lambda _: None,
        )
    state_before = (
        tmp_path / ".analysis_work" / "analysis_state.json"
    ).read_bytes()
    client = FakeClient(always_valid)
    result = run_analysis(path, client=client, progress=lambda _: None)
    assert result.resumed_from_window == 2
    assert client.calls[0]["ids"] == [61]
    assert hashlib.sha256(state_before).hexdigest()
    assert not (tmp_path / ".analysis_work").exists()


@pytest.mark.parametrize("change", ["timeline", "model", "host"])
def test_changed_fingerprint_rejects_old_state(tmp_path: Path, change: str) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline(61))

    def interrupt_second(
        segments: list[dict[str, Any]],
        call: int,
    ) -> str | BaseException:
        return model_payload(segments) if call == 1 else KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_analysis(
            path,
            client=FakeClient(interrupt_second),
            progress=lambda _: None,
        )
    if change == "timeline":
        timeline = make_timeline(61)
        timeline["segments"][0]["text"] = "内容已改变"
        timeline["segments"][0]["text_raw"] = "内容已改变"
        write_timeline(path, timeline)
        client = FakeClient(always_valid)
    elif change == "model":
        client = FakeClient(always_valid, model="other-model")
    else:
        client = FakeClient(always_valid, host="other.invalid")
    with pytest.raises(AnalysisError, match="不匹配"):
        run_analysis(path, client=client, progress=lambda _: None)
    assert client.request_count == 0


def test_publish_failure_keeps_old_current_and_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline(0))
    run_analysis(path, environ={}, progress=lambda _: None)
    current = tmp_path / "current_analysis.json"
    current_before = current.read_bytes()
    history_before = sorted(
        (item.name, item.read_bytes())
        for item in (tmp_path / "analysis_history").glob("*.json")
    ) if (tmp_path / "analysis_history").is_dir() else []

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic publish failure")

    monkeypatch.setattr(pipeline, "_replace_file", fail_replace)
    with pytest.raises(AnalysisError, match="分析发布失败"):
        run_analysis(path, environ={}, progress=lambda _: None)
    assert current.read_bytes() == current_before
    history_after = sorted(
        (item.name, item.read_bytes())
        for item in (tmp_path / "analysis_history").glob("*.json")
    ) if (tmp_path / "analysis_history").is_dir() else []
    assert history_after == history_before


def test_only_three_complete_versions_are_retained(tmp_path: Path) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline(0))
    for _ in range(5):
        run_analysis(path, environ={}, progress=lambda _: None)
    history = list((tmp_path / "analysis_history").glob("*.json"))
    assert (tmp_path / "current_analysis.json").is_file()
    assert len(history) == 2
    assert len(history) + 1 == 3


def test_http_client_retries_timeout_once_and_sends_only_subtitle_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = LLMConfig(
        endpoint="https://fake.invalid/v1/chat/completions",
        api_key=SECRET,
        model="fake-model",
        endpoint_host="fake.invalid",
    )
    client = OpenAICompatibleClient(config)
    calls: list[Any] = []

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {"message": {"content": '{"topics":[],"candidates":[]}'}}
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request: Any, *, timeout: float) -> Response:
        calls.append((request, timeout))
        if len(calls) == 1:
            raise TimeoutError()
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    segment = make_timeline(1)["segments"][0]
    assert json.loads(client.analyze_window([segment])) == {
        "topics": [],
        "candidates": [],
    }
    assert client.request_count == 2
    body = json.loads(calls[-1][0].data.decode("utf-8"))
    serialized = json.dumps(body, ensure_ascii=False)
    assert "真实样本.mp4" not in serialized
    assert SECRET not in serialized
    user_content = json.loads(body["messages"][1]["content"])
    assert set(user_content["segments"][0]) == {"id", "start_ms", "end_ms", "text"}
    assert calls[-1][0].headers["Authorization"] == f"Bearer {SECRET}"


def test_http_401_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAICompatibleClient(
        LLMConfig(
            endpoint="https://fake.invalid/v1/chat/completions",
            api_key=SECRET,
            model="fake-model",
            endpoint_host="fake.invalid",
        )
    )

    def unauthorized(*_args: Any, **_kwargs: Any) -> None:
        raise urllib.error.HTTPError(
            "https://fake.invalid",
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", unauthorized)
    with pytest.raises(AnalysisClientError, match="鉴权失败"):
        client.analyze_window(make_timeline(1)["segments"])
    assert client.request_count == 1


def test_cli_reports_missing_environment_as_one_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write_timeline(tmp_path / "timeline.json", make_timeline())
    for name in (
        "LIVECLIP_LLM_ENDPOINT",
        "LIVECLIP_LLM_API_KEY",
        "LIVECLIP_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    assert main(["analyze", "--timeline", str(path)]) == 1
    captured = capsys.readouterr()
    error_lines = captured.err.splitlines()
    assert len(error_lines) == 1
    assert "缺少环境变量" in error_lines[0]
    assert "Traceback" not in captured.err

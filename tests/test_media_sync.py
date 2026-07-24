from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

import pytest

from liveclip.media import SyncTolerances, parse_sync_probe_json
from liveclip.media.errors import ProbeError


def sync_payloads(
    *,
    video_start: str = "0.080",
    audio_start: str = "0.018",
    video_duration: str = "6.360",
    audio_duration: str = "6.421333",
    container_duration: str = "6.422",
) -> tuple[dict, dict, dict]:
    streams = {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "start_time": video_start,
                "duration": video_duration,
            },
            {
                "index": 1,
                "codec_type": "audio",
                "start_time": audio_start,
                "duration": audio_duration,
            },
        ],
        "format": {"start_time": audio_start, "duration": container_duration},
    }
    video = {
        "frames": [
            {"pts_time": video_start, "best_effort_timestamp_time": video_start}
        ]
    }
    audio = {"packets": [{"pts_time": audio_start, "dts_time": audio_start}]}
    return streams, video, audio


def parse_case(
    payloads: tuple[dict, dict, dict],
    *,
    target_duration: float = 6.4,
    tolerances: SyncTolerances | None = None,
):
    return parse_sync_probe_json(
        *payloads,
        Path(r"D:\媒体 测试\精准 裁切.mp4"),
        target_duration=target_duration,
        tolerances=tolerances,
    )


def test_ffprobe_sync_json_parses_structured_metrics() -> None:
    result = parse_case(sync_payloads())
    assert result.video_start_time == pytest.approx(0.080)
    assert result.audio_start_time == pytest.approx(0.018)
    assert result.av_start_offset_ms == pytest.approx(-62.0)
    assert result.video_duration == pytest.approx(6.360)
    assert result.audio_duration == pytest.approx(6.421333)
    assert result.stream_duration_delta_ms == pytest.approx(61.333)
    assert result.container_duration == pytest.approx(6.422)
    assert result.target_duration == pytest.approx(6.4)
    assert result.target_duration_delta_ms == pytest.approx(22.0)
    assert result.sync_within_tolerance
    assert result.duration_within_tolerance
    assert result.warnings == ()


def test_missing_first_start_time_is_rejected() -> None:
    streams, video, audio = sync_payloads()
    video["frames"][0].pop("pts_time")
    video["frames"][0].pop("best_effort_timestamp_time")
    with pytest.raises(ProbeError, match="start time"):
        parse_case((streams, video, audio))


@pytest.mark.parametrize(
    ("location", "value"),
    [
        ("video_start", "NaN"),
        ("audio_start", "Infinity"),
        ("video_duration", "-Infinity"),
        ("audio_duration", "NaN"),
        ("container_duration", "Infinity"),
    ],
)
def test_non_finite_ffprobe_values_are_rejected(location: str, value: str) -> None:
    values = {
        "video_start": "0.080",
        "audio_start": "0.018",
        "video_duration": "6.360",
        "audio_duration": "6.421333",
        "container_duration": "6.422",
    }
    values[location] = value
    with pytest.raises(ProbeError, match="finite"):
        parse_case(sync_payloads(**values))


@pytest.mark.parametrize("target", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_target_duration_is_rejected(target: float) -> None:
    with pytest.raises(ProbeError, match="finite"):
        parse_case(sync_payloads(), target_duration=target)


@pytest.mark.parametrize(
    ("video_start", "audio_start", "expected"),
    [("0.000", "0.075", 75.0), ("0.080", "0.018", -62.0)],
)
def test_positive_and_negative_av_offsets(
    video_start: str, audio_start: str, expected: float
) -> None:
    result = parse_case(
        sync_payloads(video_start=video_start, audio_start=audio_start)
    )
    assert result.av_start_offset_ms == pytest.approx(expected)
    assert result.sync_within_tolerance


def test_tolerance_boundaries_are_inclusive() -> None:
    tolerances = SyncTolerances(
        av_start_offset_ms=100.0,
        stream_duration_delta_ms=150.0,
        target_duration_delta_ms=150.0,
    )
    result = parse_case(
        sync_payloads(
            video_start="0.000",
            audio_start="0.100",
            video_duration="6.250",
            audio_duration="6.400",
            container_duration="6.550",
        ),
        tolerances=tolerances,
    )
    assert result.sync_within_tolerance
    assert result.duration_within_tolerance


def test_stream_duration_failure_is_structured() -> None:
    result = parse_case(
        sync_payloads(video_duration="6.000", audio_duration="6.200")
    )
    assert result.stream_duration_delta_ms == pytest.approx(200.0)
    assert not result.sync_within_tolerance
    assert any("Stream duration delta" in warning for warning in result.warnings)


def test_target_duration_failure_is_structured() -> None:
    result = parse_case(sync_payloads(container_duration="6.600"))
    assert result.target_duration_delta_ms == pytest.approx(200.0)
    assert not result.duration_within_tolerance
    assert any("Target duration delta" in warning for warning in result.warnings)


def test_all_structured_numeric_results_are_finite() -> None:
    result = parse_case(sync_payloads())
    payload = result.as_dict()
    numeric_keys = (
        "video_start_time",
        "audio_start_time",
        "av_start_offset_ms",
        "video_duration",
        "audio_duration",
        "stream_duration_delta_ms",
        "container_duration",
        "target_duration",
        "target_duration_delta_ms",
    )
    assert all(math.isfinite(payload[key]) for key in numeric_keys)


def test_invalid_tolerances_are_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        SyncTolerances(av_start_offset_ms=float("nan"))
    with pytest.raises(ValueError, match="non-negative"):
        SyncTolerances(stream_duration_delta_ms=-1.0)

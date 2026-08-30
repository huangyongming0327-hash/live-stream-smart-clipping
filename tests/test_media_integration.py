from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import pytest

from liveclip.media import (
    burn_subtitles,
    extract_asr_wav,
    parse_srt_text,
    probe_media,
    probe_media_sync,
    resolve_ffmpeg_paths,
    retime_srt,
    trim_video_precise,
    validate_export,
)
from liveclip.media.process_runner import run_process
from liveclip.review.exporter import export_review_clip, render_timeline_srt
from liveclip.review.schema import bind_review_inputs, sha256_file


SRT_TEXT = """1
00:00:00,500 --> 00:00:03,000
这是第一条中文字幕。

2
00:00:03,500 --> 00:00:07,500
直播智能切片 FFmpeg 测试。

3
00:00:08,000 --> 00:00:12,000
字幕路径包含中文和空格。
"""


def test_complete_media_pipeline_on_chinese_space_paths(tmp_path: Path) -> None:
    paths = resolve_ffmpeg_paths()
    project_drive = Path(__file__).resolve().drive.casefold()
    assert tmp_path.resolve().drive.casefold() == project_drive

    work = tmp_path / "媒体 测试" / "中文 空格路径"
    work.mkdir(parents=True)
    source = work / "输入 视频.mp4"
    source_srt = work / "原始 中文 字幕.srt"
    wav = work / "提取 音频.wav"
    trimmed = work / "精准 裁切.mp4"
    retimed_srt = work / "重计时 中文 字幕.srt"
    burned = work / "字幕 烧录.mp4"

    run_process(
        paths.ffmpeg,
        (
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=48000",
            "-t",
            "12",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            source,
        ),
        timeout_seconds=120,
    )
    source_srt.write_text(SRT_TEXT, encoding="utf-8", newline="\n")

    source_probe = probe_media(source, paths=paths, require_audio=True)
    assert source_probe.container_format.startswith("mov")
    assert source_probe.duration_seconds == pytest.approx(12.0, abs=0.05)
    assert source_probe.video_stream_count == 1
    assert source_probe.audio_stream_count == 1
    assert source_probe.video_streams[0].codec_name == "h264"
    assert source_probe.video_streams[0].width == 640
    assert source_probe.video_streams[0].height == 360
    assert source_probe.video_streams[0].frame_rate == pytest.approx(25.0)
    assert source_probe.audio_streams[0].codec_name == "aac"
    source_sync = probe_media_sync(source, target_duration=12.0, paths=paths)
    assert source_sync.video_start_time == pytest.approx(0.0, abs=0.001)
    assert source_sync.audio_start_time == pytest.approx(-0.021333, abs=0.001)
    assert source_sync.av_start_offset_ms == pytest.approx(-21.333, abs=1.0)
    assert source_sync.sync_within_tolerance, source_sync.warnings
    assert source_sync.duration_within_tolerance, source_sync.warnings

    wav_probe = extract_asr_wav(source, wav, paths=paths)
    assert wav_probe.audio_streams[0].codec_name == "pcm_s16le"
    assert wav_probe.audio_streams[0].sample_rate == 16000
    assert wav_probe.audio_streams[0].channels == 1
    assert wav_probe.duration_seconds == pytest.approx(12.0, abs=0.05)

    trim_probe = trim_video_precise(source, trimmed, 2.3, 8.7, paths=paths)
    assert trim_probe.duration_seconds == pytest.approx(6.4, abs=0.15)
    assert trim_probe.video_streams[0].codec_name == "h264"
    assert trim_probe.audio_streams[0].codec_name == "aac"
    trim_sync = probe_media_sync(trimmed, target_duration=6.4, paths=paths)
    assert trim_sync.video_start_time == pytest.approx(0.080, abs=0.001)
    assert trim_sync.audio_start_time == pytest.approx(0.018, abs=0.001)
    assert trim_sync.av_start_offset_ms == pytest.approx(-62.0, abs=1.0)
    assert trim_sync.stream_duration_delta_ms == pytest.approx(61.333, abs=2.0)
    assert trim_sync.target_duration_delta_ms == pytest.approx(22.0, abs=2.0)
    assert trim_sync.sync_within_tolerance, trim_sync.warnings
    assert trim_sync.duration_within_tolerance, trim_sync.warnings

    retimed = retime_srt(source_srt, retimed_srt, 2.3, 8.7)
    assert [(cue.start_seconds, cue.end_seconds) for cue in retimed] == [
        (0.0, 0.7),
        (1.2, 5.2),
        (5.7, 6.4),
    ]
    assert "直播智能切片 FFmpeg 测试。" in retimed_srt.read_text(encoding="utf-8")
    assert SRT_TEXT == source_srt.read_text(encoding="utf-8")

    burned_probe = burn_subtitles(trimmed, retimed_srt, burned, paths=paths)
    assert burned_probe.duration_seconds == pytest.approx(6.4, abs=0.15)
    assert burned_probe.video_stream_count == 1
    assert burned_probe.audio_stream_count == 1

    trimmed_validation = validate_export(
        trimmed,
        expected_duration_seconds=6.4,
        duration_tolerance_seconds=0.15,
        require_audio=True,
        srt_path=retimed_srt,
        paths=paths,
    )
    burned_validation = validate_export(
        burned,
        expected_duration_seconds=6.4,
        duration_tolerance_seconds=0.15,
        require_audio=True,
        paths=paths,
    )
    assert trimmed_validation.ok, trimmed_validation.errors
    assert trimmed_validation.srt_within_duration
    assert trimmed_validation.video_start_time == pytest.approx(0.080, abs=0.001)
    assert trimmed_validation.audio_start_time == pytest.approx(0.018, abs=0.001)
    assert trimmed_validation.av_start_offset_ms == pytest.approx(-62.0, abs=1.0)
    assert trimmed_validation.video_duration == pytest.approx(6.360, abs=0.001)
    assert trimmed_validation.audio_duration == pytest.approx(6.421333, abs=0.001)
    assert trimmed_validation.stream_duration_delta_ms == pytest.approx(61.333, abs=2.0)
    assert trimmed_validation.container_duration == pytest.approx(6.422, abs=0.002)
    assert trimmed_validation.target_duration == pytest.approx(6.4)
    assert trimmed_validation.target_duration_delta_ms == pytest.approx(22.0, abs=2.0)
    assert trimmed_validation.sync_within_tolerance
    assert trimmed_validation.duration_within_tolerance
    assert trimmed_validation.warnings == ()
    assert burned_validation.ok, burned_validation.errors
    assert burned_validation.sync_within_tolerance
    assert burned_validation.duration_within_tolerance


@pytest.mark.skipif(os.name != "nt", reason="Windows drive and path escaping regression")
def test_review_export_burns_subtitles_from_windows_apostrophe_path(
    tmp_path: Path,
) -> None:
    paths = resolve_ffmpeg_paths()
    project_drive = Path(__file__).resolve().drive.casefold()
    assert tmp_path.resolve().drive.casefold() == project_drive
    special = tmp_path / "中文 空格 & (括号) '单引号'"
    special.mkdir(parents=True)
    source = special / "输入 视频.mp4"
    timeline_path = special / "timeline.json"
    analysis_path = special / "current_analysis.json"
    output_dir = special / "导出 结果"

    run_process(
        paths.ffmpeg,
        (
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:size=640x360:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=48000",
            "-t",
            "15",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            source,
        ),
        timeout_seconds=120,
    )
    source_probe = probe_media(source, paths=paths, require_audio=True)
    duration_ms = int(round(source_probe.duration_seconds * 1000))
    timeline = {
        "schema_version": "1.0",
        "source": {
            "file_name": source.name,
            "duration_ms": duration_ms,
            "sha256": sha256_file(source),
        },
        "asr": {"engine": "sensevoice", "language": "zh", "completed": True},
        "segments": [
            {
                "id": 1,
                "start_ms": 0,
                "end_ms": 15_000,
                "text_raw": "合成测试字幕",
                "text": "合成测试字幕",
                "speaker": None,
                "is_question": False,
                "is_uncertain": False,
            }
        ],
    }
    timeline_raw = (
        json.dumps(timeline, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    timeline_path.write_bytes(timeline_raw)
    analysis = {
        "schema_version": "1.0",
        "source": {
            "timeline_file_name": timeline_path.name,
            "timeline_sha256": hashlib.sha256(timeline_raw).hexdigest(),
            "video_file_name": source.name,
            "duration_ms": duration_ms,
        },
        "analysis": {
            "provider": "openai_compatible",
            "model": "synthetic-integration-test",
            "completed": True,
            "generated_at": "2026-08-11T00:00:00Z",
            "window_count": 1,
        },
        "topics": [
            {
                "id": "topic-001",
                "start_segment_id": 1,
                "end_segment_id": 1,
                "start_ms": 0,
                "end_ms": 15_000,
                "title": "合成主题",
                "summary": "只用于本地集成测试。",
            }
        ],
        "candidates": [
            {
                "id": "clip-001",
                "topic_id": "topic-001",
                "start_segment_id": 1,
                "end_segment_id": 1,
                "start_ms": 0,
                "end_ms": 15_000,
                "duration_ms": 15_000,
                "title": "合成候选",
                "reason": "验证特殊路径字幕烧录。",
                "quote_segment_id": 1,
                "quote": "合成测试字幕",
                "content_value": 25,
                "problem_solving": 20,
                "emotion_or_reversal": 10,
                "information_density": 15,
                "hook_and_shareability": 10,
                "completeness": 10,
                "risk_penalty": 5,
                "total_score": 85,
                "recommended": True,
            }
        ],
    }
    analysis_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    inputs = bind_review_inputs(
        source,
        timeline_path,
        analysis_path,
        output_dir=output_dir,
        paths=paths,
    )
    input_hashes = {
        source: sha256_file(source),
        timeline_path: sha256_file(timeline_path),
        analysis_path: sha256_file(analysis_path),
    }

    result = export_review_clip(
        inputs,
        candidate_id="clip-001",
        start_ms=0,
        end_ms=15_000,
        confirmed=True,
        paths=paths,
        timeout_seconds=120,
    )

    expected_srt, expected_count = render_timeline_srt(inputs.timeline, 0, 15_000)
    assert expected_count == 1
    assert result.subtitle_count == expected_count
    assert result.subtitles_burned_in is True
    assert result.subtitle_path.read_text(encoding="utf-8") == expected_srt
    assert len(parse_srt_text(expected_srt)) == 1
    output_probe = probe_media(result.video_path, paths=paths, require_audio=True)
    assert output_probe.video_streams[0].codec_name == "h264"
    assert output_probe.audio_streams[0].codec_name == "aac"
    assert result.subtitle_path.resolve().drive.endswith(":")
    assert "中文 空格 & (括号) '单引号'" in str(result.subtitle_path)

    held_subtitle = result.subtitle_path.with_name(result.subtitle_path.name + ".hold")
    result.subtitle_path.replace(held_subtitle)
    try:
        assert not result.subtitle_path.exists()
        stats = run_process(
            paths.ffmpeg,
            (
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "info",
                "-ss",
                "7.500",
                "-i",
                result.video_path,
                "-vf",
                "signalstats,metadata=print",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ),
            timeout_seconds=30,
        )
        match = re.search(
            r"lavfi\.signalstats\.YMAX=(\d+)",
            stats.stdout + "\n" + stats.stderr,
        )
        assert match is not None
        assert int(match.group(1)) > 100
    finally:
        held_subtitle.replace(result.subtitle_path)

    assert {path: sha256_file(path) for path in input_hashes} == input_hashes
    assert not list(special.rglob("*.part"))

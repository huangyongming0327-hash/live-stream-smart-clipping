from __future__ import annotations

from pathlib import Path

import pytest

from liveclip.media import (
    burn_subtitles,
    extract_asr_wav,
    probe_media,
    probe_media_sync,
    resolve_ffmpeg_paths,
    retime_srt,
    trim_video_precise,
    validate_export,
)
from liveclip.media.process_runner import run_process


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

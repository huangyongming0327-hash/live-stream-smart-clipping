from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from liveclip.media import (
    MediaFileNotFoundError,
    MediaToolNotFoundError,
    NoAudioStreamError,
    OutputExistsError,
    ProbeError,
    SubtitleCue,
    parse_frame_rate,
    parse_srt_text,
    probe_media,
    resolve_ffmpeg_paths,
    retime_cues,
    validate_export,
)
from liveclip.media.errors import ProcessExecutionError, SubtitleError
from liveclip.media.outputs import prepare_output
from liveclip.media.probe import parse_probe_json
from liveclip.media.process_runner import decode_process_output, run_process
from liveclip.media.subtitles import (
    escape_subtitles_path,
    format_srt_timestamp,
    parse_srt_timestamp,
    render_srt,
    write_srt,
)


def sample_probe_payload(*, audio: bool = True) -> dict:
    streams = [
        {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "width": 640,
            "height": 360,
            "avg_frame_rate": "30000/1001",
        }
    ]
    if audio:
        streams.append(
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "channel_layout": "stereo",
            }
        )
    return {
        "streams": streams,
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "12.000000",
            "size": "123456",
        },
    }


def test_ffprobe_json_parsing_and_stream_counts(tmp_path: Path) -> None:
    source = tmp_path / "中文 路径" / "输入 视频.mp4"
    probe = parse_probe_json(json.dumps(sample_probe_payload()), source)
    assert probe.path == source.resolve()
    assert probe.container_format.startswith("mov")
    assert probe.duration_seconds == 12.0
    assert probe.file_size_bytes == 123456
    assert probe.video_stream_count == 1
    assert probe.audio_stream_count == 1
    assert probe.has_audio
    assert probe.video_streams[0].width == 640
    assert probe.video_streams[0].height == 360
    assert probe.video_streams[0].frame_rate == pytest.approx(29.97002997)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("25/1", 25.0), ("30000/1001", 29.97002997), ("0/0", None), ("bad", None)],
)
def test_frame_rate_parsing(value: str, expected: float | None) -> None:
    if expected is None:
        assert parse_frame_rate(value) is None
    else:
        assert parse_frame_rate(value) == pytest.approx(expected)


def test_probe_missing_file_returns_clear_error(tmp_path: Path) -> None:
    with pytest.raises(MediaFileNotFoundError, match="does not exist"):
        probe_media(tmp_path / "不存在 视频.mp4")


def test_probe_corrupt_file_returns_clear_error(tmp_path: Path) -> None:
    corrupt = tmp_path / "损坏 视频.mp4"
    corrupt.write_bytes(b"this is not a media container")
    with pytest.raises(ProbeError, match="ffprobe could not read"):
        probe_media(corrupt)


def test_missing_project_local_tools_return_clear_error(tmp_path: Path) -> None:
    with pytest.raises(MediaToolNotFoundError, match="Project-local FFmpeg"):
        resolve_ffmpeg_paths(root=tmp_path)


def test_probe_json_can_require_an_audio_stream(tmp_path: Path) -> None:
    with pytest.raises(NoAudioStreamError, match="no audio stream"):
        parse_probe_json(
            sample_probe_payload(audio=False),
            tmp_path / "无音轨.mp4",
            require_audio=True,
        )


def test_malformed_probe_json_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="malformed JSON"):
        parse_probe_json("{not-json", tmp_path / "损坏.mp4")


def test_process_runner_preserves_chinese_output() -> None:
    result = run_process(
        Path(sys.executable),
        ("-c", "print('中文子进程输出')"),
        timeout_seconds=5,
    )
    assert result.returncode == 0
    assert "中文子进程输出" in result.stdout
    assert result.stdout_details.raw_byte_length > 0
    assert result.stdout_details.encoding_used in {"utf-8", "cp936"}
    assert not result.stdout_details.replacement_occurred


def test_process_runner_decodes_utf8_chinese() -> None:
    raw = "中文输出".encode("utf-8")
    decoded = decode_process_output(raw, ansi_encoding="cp936")
    assert decoded.raw_byte_length == len(raw)
    assert decoded.text == "中文输出"
    assert decoded.encoding_used == "utf-8"
    assert not decoded.replacement_occurred


def test_process_runner_decodes_cp936_chinese() -> None:
    raw = "中文输出".encode("cp936")
    decoded = decode_process_output(raw, ansi_encoding="cp936")
    assert decoded.raw_byte_length == len(raw)
    assert decoded.text == "中文输出"
    assert decoded.encoding_used == "cp936"
    assert not decoded.replacement_occurred


def test_process_runner_decodes_utf8_bom() -> None:
    raw = b"\xef\xbb\xbf" + "带 BOM".encode("utf-8")
    decoded = decode_process_output(raw, ansi_encoding="cp936")
    assert decoded.text == "带 BOM"
    assert decoded.encoding_used == "utf-8-sig"
    assert not decoded.replacement_occurred


def test_process_runner_preserves_ascii_with_invalid_utf8_via_ansi() -> None:
    raw = b"path: " + "中文路径错误".encode("cp936")
    decoded = decode_process_output(raw, ansi_encoding="cp936")
    assert decoded.text == "path: 中文路径错误"
    assert decoded.encoding_used == "cp936"
    assert not decoded.replacement_occurred


def test_process_runner_safely_replaces_bytes_invalid_in_utf8_and_cp936() -> None:
    raw = b"failure: \xff\xff"
    decoded = decode_process_output(raw, ansi_encoding="cp936")
    assert decoded.raw_byte_length == len(raw)
    assert decoded.text.startswith("failure: ")
    assert "\ufffd" in decoded.text
    assert decoded.encoding_used == "cp936-replace"
    assert decoded.replacement_occurred


def test_process_runner_unknown_ansi_encoding_still_returns_safe_text() -> None:
    decoded = decode_process_output(b"bad: \xff", ansi_encoding="not-a-codec")
    assert decoded.text.startswith("bad: ")
    assert decoded.encoding_used == "utf-8-replace"
    assert decoded.replacement_occurred


def test_process_runner_returns_structured_nonzero_failure() -> None:
    with pytest.raises(ProcessExecutionError) as caught:
        run_process(
            Path(sys.executable),
            ("-c", "import sys; print('失败信息', file=sys.stderr); sys.exit(7)"),
            timeout_seconds=5,
        )
    assert caught.value.failure.returncode == 7
    assert not caught.value.failure.timed_out
    assert "失败信息" in caught.value.failure.stderr
    assert caught.value.failure.stderr_details.raw_byte_length > 0
    assert caught.value.failure.stderr_details.encoding_used in {"utf-8", "cp936"}
    assert not caught.value.failure.stderr_details.replacement_occurred


def test_process_runner_returns_structured_timeout() -> None:
    with pytest.raises(ProcessExecutionError) as caught:
        run_process(
            Path(sys.executable),
            ("-c", "import time; time.sleep(2)"),
            timeout_seconds=0.05,
        )
    assert caught.value.failure.timed_out
    assert caught.value.failure.returncode is None


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("00:00:00,000", 0.0), ("01:02:03,456", 3723.456)],
)
def test_srt_timestamp_parse_and_format(text: str, seconds: float) -> None:
    assert parse_srt_timestamp(text) == pytest.approx(seconds)
    assert format_srt_timestamp(seconds) == text


def test_srt_timestamp_rounds_to_nearest_millisecond() -> None:
    assert format_srt_timestamp(1.2345) == "00:00:01,235"
    with pytest.raises(SubtitleError):
        format_srt_timestamp(-0.001)


def test_srt_parse_preserves_multiline_chinese_and_utf8_bom() -> None:
    cues = parse_srt_text(
        "\ufeff1\r\n00:00:00,500 --> 00:00:03,000\r\n"
        "第一行中文\r\n第二行 保留空格\r\n"
    )
    assert len(cues) == 1
    assert cues[0].text == "第一行中文\n第二行 保留空格"


def test_srt_retime_clips_edges_and_discards_outside_cues() -> None:
    cues = [
        SubtitleCue(1, 0.5, 3.0, "跨越开头"),
        SubtitleCue(2, 3.5, 7.5, "完全在内\n多行中文"),
        SubtitleCue(3, 8.0, 12.0, "跨越结尾"),
        SubtitleCue(4, 0.0, 2.0, "完全在外-前"),
        SubtitleCue(5, 9.0, 10.0, "完全在外-后"),
    ]
    result = retime_cues(cues, 2.3, 8.7)
    assert [cue.text for cue in result] == [
        "跨越开头",
        "完全在内\n多行中文",
        "跨越结尾",
    ]
    assert [(cue.start_seconds, cue.end_seconds) for cue in result] == [
        (0.0, 0.7),
        (1.2, 5.2),
        (5.7, 6.4),
    ]
    assert [cue.index for cue in result] == [1, 2, 3]


def test_empty_srt_stays_empty() -> None:
    assert parse_srt_text("") == []
    assert retime_cues([], 2.3, 8.7) == []
    assert render_srt([]) == ""


def test_srt_write_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "中文 字幕.srt"
    output.write_text("用户已有内容", encoding="utf-8")
    with pytest.raises(OutputExistsError, match="overwrite"):
        write_srt([SubtitleCue(1, 0.0, 1.0, "新内容")], output)
    assert output.read_text(encoding="utf-8") == "用户已有内容"


def test_prepare_output_protects_same_name(tmp_path: Path) -> None:
    output = tmp_path / "同名 输出.mp4"
    output.write_bytes(b"existing")
    with pytest.raises(OutputExistsError, match="overwrite"):
        prepare_output(output)
    assert output.read_bytes() == b"existing"


def test_windows_subtitle_filter_path_escaping() -> None:
    escaped = escape_subtitles_path(Path(r"D:\媒体 测试\中文 字幕.srt"))
    assert escaped.startswith("filename='D\\:/")
    assert "媒体 测试/中文 字幕.srt" in escaped


def test_export_validation_returns_structured_missing_file(tmp_path: Path) -> None:
    result = validate_export(tmp_path / "不存在 输出.mp4")
    assert not result.ok
    assert not result.exists
    assert not result.probe_readable
    assert result.errors

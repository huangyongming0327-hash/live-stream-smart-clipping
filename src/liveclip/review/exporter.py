"""FFmpeg export, timeline-derived SRT, and atomic review publication."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from liveclip.media import FFmpegPaths, probe_media, resolve_ffmpeg_paths
from liveclip.media.errors import OutputExistsError, ProcessExecutionError
from liveclip.media.outputs import (
    discard_temporary,
    publish_without_overwrite,
    temporary_sibling,
)
from liveclip.media.process_runner import ProcessResult, run_process
from liveclip.media.subtitles import escape_subtitles_path

from .schema import (
    ReviewConflictError,
    ReviewError,
    ReviewInputs,
    find_candidate,
    sha256_file,
    validate_clip_range,
)


@dataclass(frozen=True, slots=True)
class ExportResult:
    video_path: Path
    subtitle_path: Path
    review_path: Path
    subtitle_count: int
    duration_ms: int
    elapsed_seconds: float
    subtitles_burned_in: bool


ProcessFunction = Callable[..., ProcessResult]
ProbeFunction = Callable[..., Any]


def subtitle_font_size(video_height: int) -> int:
    """Return one of the three fixed target pixel sizes for the source height."""

    if (
        isinstance(video_height, bool)
        or not isinstance(video_height, int)
        or video_height <= 0
    ):
        raise ReviewError("视频高度必须是正整数。")
    if video_height <= 720:
        return 24
    if video_height <= 1_440:
        return 28
    return 32


def _ass_value(target_pixels: float, video_height: int) -> str:
    """Scale target pixels to libass's 288-row SRT script coordinate space."""

    value = target_pixels * 288 / video_height
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _subtitle_filter(subtitle_path: Path, video_height: int) -> str:
    font_size = subtitle_font_size(video_height)
    horizontal_margin = {24: 32, 28: 48, 32: 60}[font_size]
    vertical_margin = {24: 48, 28: 72, 32: 96}[font_size]
    outline = {24: 2, 28: 2.5, 32: 3}[font_size]
    style = (
        f"FontName=Microsoft YaHei,FontSize={_ass_value(font_size, video_height)},"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BackColour=&H00000000,BorderStyle=1,"
        f"Outline={_ass_value(outline, video_height)},Shadow=0,Alignment=2,"
        f"MarginL={_ass_value(horizontal_margin, video_height)},"
        f"MarginR={_ass_value(horizontal_margin, video_height)},"
        f"MarginV={_ass_value(vertical_margin, video_height)},WrapStyle=0"
    )
    return (
        f"subtitles={escape_subtitles_path(subtitle_path)}:charenc=UTF-8:"
        f"force_style='{style}',setpts=PTS-STARTPTS"
    )


def format_srt_milliseconds(value: int) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReviewError("SRT 时间必须是非负整数毫秒。")
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def render_timeline_srt(
    timeline: dict[str, Any],
    start_ms: int,
    end_ms: int,
) -> tuple[str, int]:
    """Crop overlapping timeline segments and shift the clip to zero."""

    blocks: list[str] = []
    previous_end = 0
    for segment in timeline["segments"]:
        if segment["end_ms"] <= start_ms or segment["start_ms"] >= end_ms:
            continue
        cue_start = max(segment["start_ms"], start_ms) - start_ms
        cue_end = min(segment["end_ms"], end_ms) - start_ms
        cue_start = max(cue_start, previous_end)
        if cue_end <= cue_start:
            continue
        previous_end = cue_end
        blocks.append(
            "\n".join(
                (
                    str(len(blocks) + 1),
                    f"{format_srt_milliseconds(cue_start)} --> "
                    f"{format_srt_milliseconds(cue_end)}",
                    segment["text"],
                )
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else ""), len(blocks)


def _resolve_tools(paths: FFmpegPaths | None) -> FFmpegPaths:
    if paths is not None:
        return paths
    try:
        return resolve_ffmpeg_paths()
    except Exception:
        raise ReviewError("项目本地 FFmpeg/ffprobe 不可用。") from None


def _ffmpeg_arguments(
    inputs: ReviewInputs,
    temporary_video: Path,
    *,
    start_ms: int,
    end_ms: int,
    subtitle_path: Path | None,
) -> tuple[str | Path, ...]:
    duration_ms = end_ms - start_ms
    arguments: list[str | Path] = [
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_ms / 1000:.3f}",
        "-i",
        inputs.video_path,
    ]
    if not inputs.has_audio:
        arguments.extend(
            (
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            )
        )
    arguments.extend(
        (
            "-t",
            f"{duration_ms / 1000:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0" if inputs.has_audio else "1:a:0",
            "-vf",
            (
                _subtitle_filter(subtitle_path, inputs.video_height)
                if subtitle_path is not None
                else "setpts=PTS-STARTPTS"
            ),
            "-af",
            "asetpts=PTS-STARTPTS",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            "-avoid_negative_ts",
            "make_zero",
        )
    )
    if not inputs.has_audio:
        arguments.append("-shortest")
    arguments.append(temporary_video)
    return tuple(arguments)


def _build_review_document(
    inputs: ReviewInputs,
    candidate: dict[str, Any],
    *,
    start_ms: int,
    end_ms: int,
    video_file_name: str,
    subtitle_file_name: str,
    subtitles_burned_in: bool,
    reviewed_at: datetime,
) -> dict[str, Any]:
    timestamp = reviewed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": "1.0",
        "source": {
            "analysis_file_name": inputs.analysis_path.name,
            "analysis_sha256": inputs.analysis_sha256,
            "timeline_file_name": inputs.timeline_path.name,
            "timeline_sha256": inputs.timeline_sha256,
            "video_file_name": inputs.video_path.name,
        },
        "review": {
            "candidate_id": candidate["id"],
            "approved": True,
            "original_start_ms": candidate["start_ms"],
            "original_end_ms": candidate["end_ms"],
            "final_start_ms": start_ms,
            "final_end_ms": end_ms,
            "reviewed_at": timestamp,
        },
        "export": {
            "video_file_name": video_file_name,
            "subtitle_file_name": subtitle_file_name,
            "completed": True,
            "subtitles_burned_in": subtitles_burned_in,
        },
    }


def _inputs_match_bound_hashes(inputs: ReviewInputs) -> bool:
    try:
        return (
            sha256_file(inputs.video_path) == inputs.video_sha256
            and sha256_file(inputs.timeline_path) == inputs.timeline_sha256
            and sha256_file(inputs.analysis_path) == inputs.analysis_sha256
        )
    except OSError:
        return False


def export_review_clip(
    inputs: ReviewInputs,
    *,
    candidate_id: Any,
    start_ms: Any,
    end_ms: Any,
    confirmed: Any,
    paths: FFmpegPaths | None = None,
    process_function: ProcessFunction = run_process,
    probe_function: ProbeFunction = probe_media,
    now_function: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    timeout_seconds: float = 3_600.0,
) -> ExportResult:
    """Export exactly one confirmed clip and publish its review only on success."""

    if confirmed is not True:
        raise ReviewError("必须先勾选“我已人工预览并确认导出这个片段”。")
    candidate = find_candidate(inputs, candidate_id)
    validate_clip_range(start_ms, end_ms, inputs.video_duration_ms)
    resolved_paths = _resolve_tools(paths)

    video_name = f"{inputs.video_path.stem}_{candidate['id']}.mp4"
    subtitle_name = f"{inputs.video_path.stem}_{candidate['id']}.srt"
    try:
        inputs.output_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise ReviewError("输出目录不可创建或不可写。") from None
    video_output = inputs.output_dir / video_name
    subtitle_output = inputs.output_dir / subtitle_name
    if video_output.exists() or subtitle_output.exists():
        raise ReviewConflictError("同名输出文件已存在；请更换输出位置或移走旧文件。")

    temporary_video = temporary_sibling(video_output)
    temporary_subtitle = temporary_sibling(subtitle_output)
    temporary_review = temporary_sibling(inputs.review_path)
    published: list[Path] = []
    process_result: ProcessResult | None = None
    try:
        if not _inputs_match_bound_hashes(inputs):
            raise ReviewError(
                "原视频在审核期间发生变化，或 timeline/analysis 已变化，已停止导出。"
            )

        srt_text, subtitle_count = render_timeline_srt(
            inputs.timeline,
            start_ms,
            end_ms,
        )
        temporary_subtitle.write_text(srt_text, encoding="utf-8", newline="\n")
        subtitles_burned_in = subtitle_count > 0

        try:
            process_result = process_function(
                resolved_paths.ffmpeg,
                _ffmpeg_arguments(
                    inputs,
                    temporary_video,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    subtitle_path=(temporary_subtitle if subtitles_burned_in else None),
                ),
                timeout_seconds=timeout_seconds,
            )
        except ProcessExecutionError:
            raise ReviewError("FFmpeg 导出失败，未发布任何完成结果。") from None
        except OSError:
            raise ReviewError("FFmpeg 无法启动，未发布任何完成结果。") from None
        if not temporary_video.is_file() or temporary_video.stat().st_size <= 0:
            raise ReviewError("FFmpeg 未生成有效的临时视频。")

        try:
            output_probe = probe_function(
                temporary_video,
                paths=resolved_paths,
                require_audio=True,
                timeout_seconds=30.0,
            )
        except Exception:
            raise ReviewError("ffprobe 导出校验失败，未发布任何完成结果。") from None
        target_duration_ms = end_ms - start_ms
        probed_duration_ms = int(round(output_probe.duration_seconds * 1000))
        if (
            not output_probe.video_streams
            or not output_probe.audio_streams
            or output_probe.video_streams[0].codec_name != "h264"
            or output_probe.audio_streams[0].codec_name != "aac"
            or abs(probed_duration_ms - target_duration_ms) > 1_000
        ):
            raise ReviewError("导出视频的流格式或时长校验失败。")
        if not _inputs_match_bound_hashes(inputs):
            raise ReviewError(
                "原视频在导出期间发生变化，或 timeline/analysis 已变化，未发布任何完成结果。"
            )
        review_document = _build_review_document(
            inputs,
            candidate,
            start_ms=start_ms,
            end_ms=end_ms,
            video_file_name=video_name,
            subtitle_file_name=subtitle_name,
            subtitles_burned_in=subtitles_burned_in,
            reviewed_at=now_function(),
        )
        temporary_review.write_text(
            json.dumps(review_document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        publish_without_overwrite(temporary_video, video_output)
        published.append(video_output)
        publish_without_overwrite(temporary_subtitle, subtitle_output)
        published.append(subtitle_output)
        os.replace(temporary_review, inputs.review_path)
        return ExportResult(
            video_path=video_output,
            subtitle_path=subtitle_output,
            review_path=inputs.review_path,
            subtitle_count=subtitle_count,
            duration_ms=target_duration_ms,
            elapsed_seconds=(process_result.elapsed_seconds if process_result else 0.0),
            subtitles_burned_in=subtitles_burned_in,
        )
    except ReviewError:
        for path in reversed(published):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    except (FileExistsError, OutputExistsError):
        for path in reversed(published):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise ReviewConflictError(
            "同名输出文件被其他程序创建；本次未覆盖任何文件。"
        ) from None
    except OSError:
        for path in reversed(published):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise ReviewError("输出目录或审核结果不可写；未发布完成结果。") from None
    finally:
        discard_temporary(temporary_video)
        discard_temporary(temporary_subtitle)
        discard_temporary(temporary_review)

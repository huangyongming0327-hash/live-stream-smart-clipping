"""Sequentially reuse the existing ASR, analysis, and review capabilities."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from liveclip.analysis.client import load_config
from liveclip.analysis.pipeline import run_analysis
from liveclip.analysis.schema import AnalysisError, load_timeline, validate_analysis
from liveclip.asr.adapters import ASRAdapterError, Engine, model_identity
from liveclip.asr.pipeline import run_transcription
from liveclip.media import FFmpegPaths, MediaProbe, probe_media, resolve_ffmpeg_paths
from liveclip.review.server import launch_review
from liveclip.review.schema import sha256_file

from .status import StageStatus, write_pipeline_status


Progress = Callable[[str], None]
TranscribeFunction = Callable[..., Any]
AnalyzeFunction = Callable[..., Any]
ReviewFunction = Callable[..., Any]
ProbeFunction = Callable[..., MediaProbe]
ModelIdentityFunction = Callable[[Engine, Path], str]


class PipelineRunError(RuntimeError):
    """A stage-aware failure safe to print without a traceback."""

    def __init__(
        self,
        stage: str,
        reason: str,
        next_step: str,
        *,
        resumable: bool,
    ) -> None:
        self.stage = stage
        self.reason = " ".join(str(reason).splitlines()).strip()
        self.next_step = " ".join(str(next_step).splitlines()).strip()
        self.resumable = resumable
        resume_text = "可以继续" if resumable else "请先按上一步处理"
        super().__init__(
            f"{stage}：失败\n"
            f"原因：{self.reason}\n"
            f"下一步：{self.next_step}\n"
            f"再次运行同一命令：{resume_text}。"
        )


@dataclass(frozen=True, slots=True)
class RunResult:
    workdir: Path
    output_dir: Path
    timeline_path: Path
    analysis_path: Path
    review_path: Path
    transcribe_action: str
    analyze_action: str
    review_completed: bool


def _failure(
    stage: str,
    exc: BaseException | str,
    next_step: str,
    *,
    resumable: bool,
) -> PipelineRunError:
    reason = str(exc) or type(exc).__name__
    return PipelineRunError(stage, reason, next_step, resumable=resumable)


def _ensure_writable(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, delete=True):
        pass


def _persist_status(
    workdir: Path,
    *,
    stage: str,
    video_file_name: str,
    video_sha256: str,
    stages: Mapping[str, StageStatus],
) -> None:
    try:
        write_pipeline_status(
            workdir,
            video_file_name=video_file_name,
            video_sha256=video_sha256,
            stages=stages,
        )
    except (OSError, ValueError) as exc:
        raise _failure(
            stage,
            f"pipeline_status.json 无法原子更新：{exc}",
            "检查工作目录写入权限后再次运行同一命令。",
            resumable=True,
        ) from None


def _read_timeline_for_video(
    path: Path,
    *,
    video_name: str,
    video_sha256: str,
    video_duration_ms: int,
) -> tuple[dict[str, Any], bytes] | None:
    if not path.exists():
        return None
    try:
        _, timeline, raw = load_timeline(path)
    except (AnalysisError, OSError, ValueError) as exc:
        raise _failure(
            "[1/3] 字幕识别",
            f"现有 timeline.json 已损坏或无效：{exc}",
            "请先把损坏的 timeline.json 移出工作目录，再重新运行；LiveClip 不会自动删除它。",
            resumable=False,
        ) from None
    source = timeline["source"]
    if (
        source["file_name"] != video_name
        or source["sha256"] != video_sha256
        or abs(source["duration_ms"] - video_duration_ms) > 1_000
    ):
        raise _failure(
            "[1/3] 字幕识别",
            "现有 timeline.json 不属于当前视频内容。",
            "请为变化后的视频指定新的 --workdir，或先移走旧工作目录中的产物。",
            resumable=False,
        )
    return timeline, raw


def _read_analysis_for_timeline(
    path: Path,
    *,
    timeline: dict[str, Any],
    timeline_raw: bytes,
) -> tuple[dict[str, Any], bytes] | None:
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
        analysis = json.loads(raw.decode("utf-8"))
        validate_analysis(analysis, timeline=timeline)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AnalysisError, ValueError) as exc:
        raise _failure(
            "[2/3] 爆点分析",
            f"现有 current_analysis.json 已损坏或无效：{exc}",
            "请先把损坏的 current_analysis.json 移出工作目录，再重新运行；LiveClip 不会自动删除它。",
            resumable=False,
        ) from None
    timeline_sha256 = hashlib.sha256(timeline_raw).hexdigest()
    if analysis["source"]["timeline_sha256"] != timeline_sha256:
        raise _failure(
            "[2/3] 爆点分析",
            "现有 current_analysis.json 不属于当前 timeline.json。",
            "请先移走不匹配的 current_analysis.json，再重新运行。",
            resumable=False,
        )
    return analysis, raw


def _completed_review_matches(
    path: Path,
    *,
    output_dir: Path,
    video_duration_ms: int,
    analysis: dict[str, Any],
    video_name: str,
    timeline_name: str,
    timeline_sha256: str,
    analysis_name: str,
    analysis_sha256: str,
) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        source = payload["source"]
        review = payload["review"]
        export = payload["export"]
        start_ms = review.get("final_start_ms")
        end_ms = review.get("final_end_ms")
        video_file_name = export.get("video_file_name")
        subtitle_file_name = export.get("subtitle_file_name")
        candidate_ids = {
            candidate["id"] for candidate in analysis.get("candidates", [])
        }
        return bool(
            payload.get("schema_version") == "1.0"
            and source.get("video_file_name") == video_name
            and source.get("timeline_file_name") == timeline_name
            and source.get("timeline_sha256") == timeline_sha256
            and source.get("analysis_file_name") == analysis_name
            and source.get("analysis_sha256") == analysis_sha256
            and review.get("approved") is True
            and review.get("candidate_id") in candidate_ids
            and review.get("original_start_ms")
            == next(
                candidate["start_ms"]
                for candidate in analysis["candidates"]
                if candidate["id"] == review.get("candidate_id")
            )
            and review.get("original_end_ms")
            == next(
                candidate["end_ms"]
                for candidate in analysis["candidates"]
                if candidate["id"] == review.get("candidate_id")
            )
            and isinstance(start_ms, int)
            and not isinstance(start_ms, bool)
            and isinstance(end_ms, int)
            and not isinstance(end_ms, bool)
            and 0 <= start_ms < end_ms <= video_duration_ms
            and 1_000 <= end_ms - start_ms <= 180_000
            and export.get("completed") is True
            and isinstance(export.get("subtitles_burned_in"), bool)
            and isinstance(video_file_name, str)
            and Path(video_file_name).name == video_file_name
            and isinstance(subtitle_file_name, str)
            and Path(subtitle_file_name).name == subtitle_file_name
            and (output_dir / video_file_name).is_file()
            and (output_dir / subtitle_file_name).is_file()
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        return False


def run_pipeline(
    video: str | Path,
    *,
    workdir: str | Path | None = None,
    asr_model: Engine = "paraformer",
    output_dir: str | Path | None = None,
    open_browser: bool = True,
    assets_root: str | Path | None = None,
    model_root: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    progress: Progress = print,
    ffmpeg_paths: FFmpegPaths | None = None,
    probe_function: ProbeFunction = probe_media,
    model_identity_function: ModelIdentityFunction = model_identity,
    transcribe_function: TranscribeFunction = run_transcription,
    analyze_function: AnalyzeFunction = run_analysis,
    review_function: ReviewFunction = launch_review,
) -> RunResult:
    """Run one video through the three existing stages without duplicating them."""

    source = Path(video).expanduser().resolve()
    if not source.is_file():
        raise _failure(
            "启动检查",
            "所选视频不存在或不是文件。",
            "重新选择一个现有的 MP4 文件。",
            resumable=False,
        )
    if source.suffix.lower() != ".mp4":
        raise _failure(
            "启动检查",
            "输入必须是一个 .mp4 文件。",
            "重新选择 MP4 文件。",
            resumable=False,
        )
    if asr_model not in {"paraformer", "sensevoice"}:
        raise _failure(
            "启动检查",
            "ASR 模型必须是 paraformer 或 sensevoice。",
            "使用 --asr-model paraformer 或 --asr-model sensevoice。",
            resumable=False,
        )

    try:
        load_config(environ)
    except Exception as exc:
        raise _failure(
            "启动检查",
            exc,
            "配置 LIVECLIP_LLM_ENDPOINT、LIVECLIP_LLM_API_KEY 和 LIVECLIP_LLM_MODEL 后重试。",
            resumable=True,
        ) from None

    root = (
        Path(assets_root).expanduser().resolve()
        if assets_root is not None
        else Path(__file__).resolve().parents[3]
    )
    models = (
        Path(model_root).expanduser().resolve()
        if model_root is not None
        else root / "模型" / "asr"
    )
    try:
        paths = ffmpeg_paths or resolve_ffmpeg_paths(root=root)
        if not paths.ffmpeg.is_file() or not paths.ffprobe.is_file():
            raise FileNotFoundError("项目本地 FFmpeg/ffprobe 不可用。")
        model_identity_function(asr_model, models)
        media = probe_function(
            source,
            paths=paths,
            require_audio=True,
            timeout_seconds=60.0,
        )
        if (
            not media.video_streams
            or not media.audio_streams
            or not math.isfinite(media.duration_seconds)
            or media.duration_seconds <= 0
        ):
            raise ValueError("MP4 必须包含可读取的音频、视频和有效时长。")
    except Exception as exc:
        raise _failure(
            "启动检查",
            exc,
            "确认项目本地 FFmpeg/ffprobe、所选 ASR 模型和 MP4 音视频均可用后重试。",
            resumable=True,
        ) from None

    destination = (
        Path(workdir).expanduser().resolve()
        if workdir is not None
        else source.with_name(f"{source.stem}_liveclip")
    )
    exports = (
        Path(output_dir).expanduser().resolve()
        if output_dir is not None
        else destination / "exports"
    )
    if destination == source or exports == source:
        raise _failure(
            "启动检查",
            "工作目录或导出目录不能是原视频文件。",
            "选择其他 --workdir 或 --output。",
            resumable=False,
        )
    try:
        _ensure_writable(destination)
        _ensure_writable(exports)
        video_sha256 = sha256_file(source)
    except OSError as exc:
        raise _failure(
            "启动检查",
            exc,
            "选择可写的工作目录和导出目录后重试。",
            resumable=True,
        ) from None

    video_duration_ms = int(round(media.duration_seconds * 1_000))
    timeline_path = destination / "timeline.json"
    analysis_path = destination / "current_analysis.json"
    review_path = destination / "review_current.json"
    timeline_data = _read_timeline_for_video(
        timeline_path,
        video_name=source.name,
        video_sha256=video_sha256,
        video_duration_ms=video_duration_ms,
    )
    analysis_data = None
    if timeline_data is not None:
        analysis_data = _read_analysis_for_timeline(
            analysis_path,
            timeline=timeline_data[0],
            timeline_raw=timeline_data[1],
        )

    stages: dict[str, StageStatus] = {
        "transcribe": "completed" if timeline_data is not None else "pending",
        "analyze": "completed" if analysis_data is not None else "pending",
        "review": "pending",
    }
    _persist_status(
        destination,
        stage="启动检查",
        video_file_name=source.name,
        video_sha256=video_sha256,
        stages=stages,
    )

    transcribe_action = "reused"
    if timeline_data is not None:
        progress("[1/3] 字幕识别：已复用")
    else:
        resume_asr = (destination / "task_state.json").is_file()
        progress(
            "[1/3] 字幕识别：已恢复，继续处理"
            if resume_asr
            else "[1/3] 字幕识别：开始"
        )
        try:
            transcribe_function(
                source,
                engine=asr_model,
                output_dir=destination,
                assets_root=root,
                model_root=models,
                paths=paths,
                progress=lambda _message: None,
            )
            transcribe_action = "resumed" if resume_asr else "completed"
            timeline_data = _read_timeline_for_video(
                timeline_path,
                video_name=source.name,
                video_sha256=video_sha256,
                video_duration_ms=video_duration_ms,
            )
            if timeline_data is None:
                raise RuntimeError("字幕识别没有发布 timeline.json。")
            progress("[1/3] 字幕识别：完成")
        except PipelineRunError:
            raise
        except Exception as exc:
            raise _failure(
                "[1/3] 字幕识别",
                exc,
                "修正直接原因后再次运行同一命令；已完成分块会继续复用。",
                resumable=True,
            ) from None
        stages["transcribe"] = "completed"
        _persist_status(
            destination,
            stage="[1/3] 字幕识别",
            video_file_name=source.name,
            video_sha256=video_sha256,
            stages=stages,
        )

        if analysis_path.exists():
            analysis_data = _read_analysis_for_timeline(
                analysis_path,
                timeline=timeline_data[0],
                timeline_raw=timeline_data[1],
            )

    assert timeline_data is not None
    analyze_action = "reused"
    if analysis_data is not None:
        progress("[2/3] 爆点分析：已复用")
    else:
        resume_analysis = (destination / ".analysis_work" / "analysis_state.json").is_file()
        progress(
            "[2/3] 爆点分析：已恢复，继续处理"
            if resume_analysis
            else "[2/3] 爆点分析：开始"
        )
        try:
            analyze_function(
                timeline_path,
                output_dir=destination,
                environ=environ,
                progress=lambda _message: None,
            )
            analyze_action = "resumed" if resume_analysis else "completed"
            analysis_data = _read_analysis_for_timeline(
                analysis_path,
                timeline=timeline_data[0],
                timeline_raw=timeline_data[1],
            )
            if analysis_data is None:
                raise RuntimeError("爆点分析没有发布 current_analysis.json。")
            progress("[2/3] 爆点分析：完成")
        except PipelineRunError:
            raise
        except Exception as exc:
            raise _failure(
                "[2/3] 爆点分析",
                exc,
                "修正直接原因后再次运行同一命令；已完成窗口会继续复用。",
                resumable=True,
            ) from None
        stages["analyze"] = "completed"
        _persist_status(
            destination,
            stage="[2/3] 爆点分析",
            video_file_name=source.name,
            video_sha256=video_sha256,
            stages=stages,
        )

    assert analysis_data is not None
    timeline_sha256 = hashlib.sha256(timeline_data[1]).hexdigest()
    analysis_sha256 = hashlib.sha256(analysis_data[1]).hexdigest()
    already_reviewed = _completed_review_matches(
        review_path,
        output_dir=exports,
        video_duration_ms=video_duration_ms,
        analysis=analysis_data[0],
        video_name=source.name,
        timeline_name=timeline_path.name,
        timeline_sha256=timeline_sha256,
        analysis_name=analysis_path.name,
        analysis_sha256=analysis_sha256,
    )
    stages["review"] = "completed" if already_reviewed else "pending"
    _persist_status(
        destination,
        stage="[3/3] 人工审核与导出",
        video_file_name=source.name,
        video_sha256=video_sha256,
        stages=stages,
    )
    progress(
        "[3/3] 人工审核与导出：已复用，打开此前审核结果"
        if already_reviewed
        else "[3/3] 人工审核与导出：开始"
    )
    try:
        review_function(
            source,
            timeline_path,
            analysis_path,
            output_dir=exports,
            open_browser=open_browser,
            paths=paths,
        )
    except Exception as exc:
        raise _failure(
            "[3/3] 人工审核与导出",
            exc,
            "再次运行同一命令会复用字幕和分析并重新打开审核页面。",
            resumable=True,
        ) from None

    review_completed = _completed_review_matches(
        review_path,
        output_dir=exports,
        video_duration_ms=video_duration_ms,
        analysis=analysis_data[0],
        video_name=source.name,
        timeline_name=timeline_path.name,
        timeline_sha256=timeline_sha256,
        analysis_name=analysis_path.name,
        analysis_sha256=analysis_sha256,
    )
    stages["review"] = "completed" if review_completed else "pending"
    _persist_status(
        destination,
        stage="[3/3] 人工审核与导出",
        video_file_name=source.name,
        video_sha256=video_sha256,
        stages=stages,
    )
    progress(
        "[3/3] 人工审核与导出：完成"
        if review_completed
        else "[3/3] 人工审核与导出：完成（未导出，状态保持 pending）"
    )
    return RunResult(
        workdir=destination,
        output_dir=exports,
        timeline_path=timeline_path,
        analysis_path=analysis_path,
        review_path=review_path,
        transcribe_action=transcribe_action,
        analyze_action=analyze_action,
        review_completed=review_completed,
    )

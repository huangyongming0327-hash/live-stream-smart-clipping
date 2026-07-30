"""Single-video, chunked, resumable local ASR orchestration."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from liveclip.media import (
    FFmpegPaths,
    MediaProbe,
    extract_asr_wav_chunk,
    probe_media,
    resolve_ffmpeg_paths,
)

from .adapters import ASRAdapter, AdapterSegment, Engine, create_adapter, model_identity
from .exporters import (
    FORMAL_OUTPUT_NAMES,
    atomic_write_json,
    cleanup_work_dir,
    publish_final_outputs,
)
from .timeline import build_timeline, canonical_segment


MAX_DURATION_MS = 3 * 60 * 60 * 1000
STATE_SCHEMA_VERSION = "1.0"


class ASRPipelineError(RuntimeError):
    """Base error for a recoverable production transcription failure."""


class StateFileError(ASRPipelineError):
    """Raised when task_state.json is corrupt or belongs to another task."""


@dataclass(frozen=True, slots=True)
class PipelineResult:
    output_dir: Path
    timeline_path: Path
    subtitles_path: Path
    transcript_path: Path
    state_path: Path
    resumed_from_chunk: int
    total_chunks: int
    already_completed: bool = False


Progress = Callable[[str], None]
AfterChunk = Callable[[int, dict[str, Any]], None]
ProbeFunction = Callable[..., MediaProbe]
ExtractFunction = Callable[..., Path]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ensure_writable(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=True):
            pass
    except OSError as exc:
        raise ASRPipelineError(f"Output directory is not writable: {directory}") from exc


def _peak_rss_bytes() -> int | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.restype = wintypes.HANDLE
        get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        get_memory_info.restype = wintypes.BOOL
        process = get_current_process()
        if get_memory_info(
            process, ctypes.byref(counters), counters.cb
        ):
            return int(counters.PeakWorkingSetSize)
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    return None


def _default_output(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_liveclip")


def _load_state(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateFileError(f"task_state.json is corrupt or unreadable: {path}") from exc
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise StateFileError("task_state.json has an unsupported schema.")
    if not isinstance(state.get("completed_chunks"), list):
        raise StateFileError("task_state.json completed_chunks must be a list.")
    return state


def _validate_resume_state(
    state: dict[str, Any],
    *,
    task_fingerprint: str,
    total_chunks: int,
) -> None:
    if state.get("task_fingerprint") != task_fingerprint:
        raise StateFileError(
            "Existing task_state.json does not match the source, model, engine, "
            "or chunk settings; choose a new output directory."
        )
    if state.get("total_chunks") != total_chunks:
        raise StateFileError("Existing task_state.json has an invalid chunk count.")
    completed = state["completed_chunks"]
    if [item.get("index") for item in completed if isinstance(item, dict)] != list(
        range(len(completed))
    ):
        raise StateFileError("Completed chunks must be contiguous from index zero.")
    if len(completed) > total_chunks:
        raise StateFileError("task_state.json contains too many completed chunks.")


def _formal_paths(output_dir: Path) -> dict[str, Path]:
    return {name: output_dir / name for name in FORMAL_OUTPUT_NAMES}


def _all_segments(state: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for chunk in state["completed_chunks"]:
        chunk_segments = chunk.get("segments")
        if not isinstance(chunk_segments, list):
            raise StateFileError("Completed chunk segments must be a list.")
        segments.extend(chunk_segments)
    return segments


def _result(
    output_dir: Path,
    *,
    resumed_from_chunk: int,
    total_chunks: int,
    already_completed: bool,
) -> PipelineResult:
    return PipelineResult(
        output_dir=output_dir,
        timeline_path=output_dir / "timeline.json",
        subtitles_path=output_dir / "subtitles.srt",
        transcript_path=output_dir / "transcript.txt",
        state_path=output_dir / "task_state.json",
        resumed_from_chunk=resumed_from_chunk,
        total_chunks=total_chunks,
        already_completed=already_completed,
    )


def run_transcription(
    input_path: str | Path,
    *,
    engine: Engine = "paraformer",
    output_dir: str | Path | None = None,
    chunk_seconds: float = 60.0,
    assets_root: str | Path | None = None,
    model_root: str | Path | None = None,
    adapter: ASRAdapter | None = None,
    paths: FFmpegPaths | None = None,
    progress: Progress = print,
    after_chunk: AfterChunk | None = None,
    probe_function: ProbeFunction = probe_media,
    extract_function: ExtractFunction = extract_asr_wav_chunk,
) -> PipelineResult:
    started = time.perf_counter()
    source = Path(input_path).resolve()
    if not source.is_file():
        raise ASRPipelineError(f"Input file does not exist: {source}")
    if source.suffix.lower() != ".mp4":
        raise ASRPipelineError("Input must be a single .mp4 file.")
    if (
        isinstance(chunk_seconds, bool)
        or not isinstance(chunk_seconds, (int, float))
        or not math.isfinite(float(chunk_seconds))
        or not 1 <= float(chunk_seconds) <= 600
    ):
        raise ASRPipelineError("chunk_seconds must be between 1 and 600.")
    chunk_duration_ms = int(math.floor(float(chunk_seconds) * 1000 + 0.5))
    destination = (
        Path(output_dir).resolve() if output_dir is not None else _default_output(source)
    )
    if destination == source:
        raise ASRPipelineError("Output directory cannot be the input video.")

    root = (
        Path(assets_root).resolve()
        if assets_root is not None
        else Path(__file__).resolve().parents[3]
    )
    models = (
        Path(model_root).resolve()
        if model_root is not None
        else root / "模型" / "asr"
    )
    if paths is None:
        paths = resolve_ffmpeg_paths(root=root)

    progress(f"阶段: 检查输入 | 输出目录: {destination}")
    try:
        media = probe_function(
            source, paths=paths, require_audio=True, timeout_seconds=60.0
        )
    except Exception as exc:
        raise ASRPipelineError(f"Unable to read MP4 audio: {exc}") from exc
    if media.video_stream_count < 1:
        raise ASRPipelineError("Input MP4 has no video stream.")
    if "mp4" not in media.container_format and "mov" not in media.container_format:
        raise ASRPipelineError("Input is not a readable MP4 container.")
    duration_ms = int(math.floor(media.duration_seconds * 1000 + 0.5))
    if duration_ms <= 0:
        raise ASRPipelineError("Input MP4 has no positive duration.")
    if duration_ms > MAX_DURATION_MS:
        raise ASRPipelineError("Input MP4 exceeds the 3-hour limit.")
    total_chunks = math.ceil(duration_ms / chunk_duration_ms)

    _ensure_writable(destination)
    work_dir = destination / ".work"
    _ensure_writable(work_dir)
    required_free = min(chunk_duration_ms, duration_ms) * 32 + 10 * 1024 * 1024
    if shutil.disk_usage(destination).free < required_free:
        raise ASRPipelineError(
            "Insufficient disk space for one temporary PCM audio chunk."
        )

    progress("阶段: 计算源文件指纹")
    source_sha256 = _sha256_file(source)
    model_signature = (
        adapter.identity if adapter is not None else model_identity(engine, models)
    )
    if adapter is not None and adapter.engine != engine:
        raise ASRPipelineError("Provided adapter does not match the selected engine.")
    source_stat = source.stat()
    fingerprint_data = {
        "source_sha256": source_sha256,
        "source_size": source_stat.st_size,
        "duration_ms": duration_ms,
        "engine": engine,
        "chunk_duration_ms": chunk_duration_ms,
        "model_identity": model_signature,
    }
    task_fingerprint = _fingerprint(fingerprint_data)
    state_path = destination / "task_state.json"
    if state_path.exists():
        state = _load_state(state_path)
        _validate_resume_state(
            state, task_fingerprint=task_fingerprint, total_chunks=total_chunks
        )
    else:
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "status": "pending",
            "task_fingerprint": task_fingerprint,
            "source": {
                "file_name": source.name,
                "size_bytes": source_stat.st_size,
                "duration_ms": duration_ms,
                "sha256": source_sha256,
            },
            "asr": {
                "engine": engine,
                "model_identity": model_signature,
                "chunk_duration_ms": chunk_duration_ms,
            },
            "total_chunks": total_chunks,
            "completed_chunks": [],
            "run_count": 0,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "completed_at": None,
            "error": None,
            "metrics": {},
        }
        atomic_write_json(state_path, state)

    resumed_from = len(state["completed_chunks"])
    formal = _formal_paths(destination)
    existing_formal = [path for path in formal.values() if path.exists()]
    if state.get("status") == "completed":
        if len(existing_formal) != len(formal):
            raise StateFileError("Completed state is missing one or more formal outputs.")
        progress("阶段: 已完成 | 正式输出已存在")
        cleanup_work_dir(work_dir)
        return _result(
            destination,
            resumed_from_chunk=resumed_from,
            total_chunks=total_chunks,
            already_completed=True,
        )
    if existing_formal:
        if len(state["completed_chunks"]) == total_chunks and len(existing_formal) == len(
            formal
        ):
            timeline = json.loads(formal["timeline.json"].read_text(encoding="utf-8"))
            expected = build_timeline(
                file_name=source.name,
                duration_ms=duration_ms,
                source_sha256=source_sha256,
                engine=engine,
                segments=_all_segments(state),
            )
            if timeline != expected:
                raise StateFileError("Existing formal timeline does not match task state.")
            state["status"] = "completed"
            state["completed_at"] = _utc_now()
            state["updated_at"] = _utc_now()
            state["error"] = None
            atomic_write_json(state_path, state)
            cleanup_work_dir(work_dir)
            return _result(
                destination,
                resumed_from_chunk=resumed_from,
                total_chunks=total_chunks,
                already_completed=True,
            )
        raise StateFileError(
            "Incomplete task has existing formal outputs; refusing to overwrite them."
        )

    state["status"] = "running"
    state["run_count"] = int(state.get("run_count", 0)) + 1
    state["updated_at"] = _utc_now()
    state["error"] = None
    atomic_write_json(state_path, state)
    if resumed_from:
        progress(f"阶段: 恢复任务 | 从分块 {resumed_from + 1}/{total_chunks} 继续")

    current_wav: Path | None = None
    try:
        progress(f"阶段: 加载本地模型 | 引擎: {engine}")
        active_adapter = adapter if adapter is not None else create_adapter(engine, models)
        for index in range(resumed_from, total_chunks):
            chunk_started = time.perf_counter()
            start_ms = index * chunk_duration_ms
            end_ms = min(duration_ms, start_ms + chunk_duration_ms)
            progress(
                f"阶段: 提取音频并识别 | 分块 {index + 1}/{total_chunks} | "
                f"已用 {time.perf_counter() - started:.1f}s"
            )
            current_wav = work_dir / f"chunk-{index:05d}.wav"
            current_wav.unlink(missing_ok=True)
            extract_function(
                source,
                current_wav,
                start_ms=start_ms,
                duration_ms=end_ms - start_ms,
                paths=paths,
                timeout_seconds=max(120.0, chunk_seconds * 4),
            )
            relative_segments = active_adapter.transcribe(current_wav)
            chunk_segments: list[dict[str, Any]] = []
            for segment in relative_segments:
                if not isinstance(segment, AdapterSegment):
                    raise ASRPipelineError("Adapter returned an invalid segment type.")
                global_start = start_ms + segment.start_ms
                global_end = min(end_ms, start_ms + segment.end_ms)
                canonical = canonical_segment(
                    start_ms=global_start,
                    end_ms=global_end,
                    text_raw=segment.text_raw,
                )
                if canonical is not None:
                    chunk_segments.append(canonical)
            provisional = [
                *_all_segments(state),
                *chunk_segments,
            ]
            build_timeline(
                file_name=source.name,
                duration_ms=duration_ms,
                source_sha256=source_sha256,
                engine=engine,
                segments=provisional,
            )
            current_wav.unlink(missing_ok=True)
            current_wav = None
            chunk_record = {
                "index": index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "segments": chunk_segments,
                "elapsed_seconds": round(time.perf_counter() - chunk_started, 6),
                "completed_at": _utc_now(),
            }
            state["completed_chunks"].append(chunk_record)
            state["updated_at"] = _utc_now()
            state["metrics"]["peak_rss_bytes"] = max(
                int(state["metrics"].get("peak_rss_bytes") or 0),
                int(_peak_rss_bytes() or 0),
            )
            atomic_write_json(state_path, state)
            if after_chunk is not None:
                after_chunk(index, state)

        progress("阶段: 校验并发布 timeline/SRT/TXT")
        if _sha256_file(source) != source_sha256:
            raise ASRPipelineError(
                "Source MP4 changed during processing; formal outputs were not published."
            )
        timeline = build_timeline(
            file_name=source.name,
            duration_ms=duration_ms,
            source_sha256=source_sha256,
            engine=engine,
            segments=_all_segments(state),
        )
        output_sizes = publish_final_outputs(destination, timeline)
        state["status"] = "completed"
        state["completed_at"] = _utc_now()
        state["updated_at"] = _utc_now()
        state["error"] = None
        state["metrics"].update(
            total_elapsed_seconds=round(time.perf_counter() - started, 6),
            recognition_chunk_seconds=round(
                sum(
                    float(chunk["elapsed_seconds"])
                    for chunk in state["completed_chunks"]
                ),
                6,
            ),
            output_sizes=output_sizes,
        )
        atomic_write_json(state_path, state)
        cleanup_work_dir(work_dir)
        progress(
            f"阶段: 成功 | 分块 {total_chunks}/{total_chunks} | "
            f"已用 {time.perf_counter() - started:.1f}s | 输出目录: {destination}"
        )
        return _result(
            destination,
            resumed_from_chunk=resumed_from,
            total_chunks=total_chunks,
            already_completed=False,
        )
    except KeyboardInterrupt:
        if current_wav is not None:
            current_wav.unlink(missing_ok=True)
        state["status"] = "interrupted"
        state["updated_at"] = _utc_now()
        state["error"] = {
            "type": "KeyboardInterrupt",
            "message": "Task interrupted after the last completed chunk.",
        }
        atomic_write_json(state_path, state)
        raise
    except Exception as exc:
        if current_wav is not None:
            current_wav.unlink(missing_ok=True)
        state["status"] = "failed"
        state["updated_at"] = _utc_now()
        state["error"] = {"type": type(exc).__name__, "message": str(exc)}
        try:
            atomic_write_json(state_path, state)
        except OSError:
            pass
        raise

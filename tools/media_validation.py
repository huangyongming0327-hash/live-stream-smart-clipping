"""Generate a synthetic media sample and record TASK-001 validation metrics."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from liveclip.media import (
    burn_subtitles,
    extract_asr_wav,
    probe_media,
    resolve_ffmpeg_paths,
    retime_srt,
    trim_video_precise,
    validate_export,
)
from liveclip.media.outputs import (
    discard_temporary,
    prepare_output,
    publish_without_overwrite,
    temporary_sibling,
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


def probe_record(probe: object) -> dict[str, object]:
    data = asdict(probe)  # type: ignore[arg-type]
    data["path"] = str(data["path"])
    return data


def timed(operation: object, *args: object, **kwargs: object) -> tuple[object, float]:
    started = time.perf_counter()
    result = operation(*args, **kwargs)  # type: ignore[operator]
    return result, time.perf_counter() - started


def main() -> int:
    root = PROJECT_ROOT
    runtime_temp = (root / "runtime" / "temp").resolve()
    runtime_logs = (root / "runtime" / "logs").resolve()
    if runtime_temp.drive.casefold() != root.drive.casefold():
        raise RuntimeError("Media validation temp directory must remain on the project drive.")

    paths = resolve_ffmpeg_paths(root=root)
    run_id = f"{datetime.now().astimezone():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    work = runtime_temp / "媒体 测试" / run_id
    work.mkdir(parents=True, exist_ok=False)
    runtime_logs.mkdir(parents=True, exist_ok=True)

    source = work / "输入 视频.mp4"
    source_srt = work / "原始 中文 字幕.srt"
    wav = work / "提取 音频.wav"
    trimmed = work / "精准 裁切.mp4"
    retimed_srt = work / "重计时 中文 字幕.srt"
    burned = work / "字幕 烧录.mp4"

    source_output = prepare_output(source)
    source_temporary = temporary_sibling(source_output)
    try:
        started = time.perf_counter()
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
                source_temporary,
            ),
            timeout_seconds=120,
        )
        sample_elapsed = time.perf_counter() - started
        publish_without_overwrite(source_temporary, source_output)
    except Exception:
        discard_temporary(source_temporary)
        raise

    srt_output = prepare_output(source_srt)
    srt_temporary = temporary_sibling(srt_output)
    try:
        srt_temporary.write_text(SRT_TEXT, encoding="utf-8", newline="\n")
        publish_without_overwrite(srt_temporary, srt_output)
    except Exception:
        discard_temporary(srt_temporary)
        raise

    source_probe, probe_elapsed = timed(
        probe_media, source, paths=paths, require_audio=True
    )
    wav_probe, wav_elapsed = timed(extract_asr_wav, source, wav, paths=paths)
    trim_probe, trim_elapsed = timed(
        trim_video_precise, source, trimmed, 2.3, 8.7, paths=paths
    )
    retimed, srt_elapsed = timed(retime_srt, source_srt, retimed_srt, 2.3, 8.7)
    burn_probe, burn_elapsed = timed(
        burn_subtitles, trimmed, retimed_srt, burned, paths=paths
    )
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
    if not trimmed_validation.ok or not burned_validation.ok:
        raise RuntimeError(
            "Post-export validation failed: "
            f"trimmed={trimmed_validation.errors}, burned={burned_validation.errors}"
        )

    summary = {
        "validation_time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "project_root": str(root),
        "work_directory": str(work),
        "source_is_synthetic": True,
        "source_srt_unchanged": source_srt.read_text(encoding="utf-8") == SRT_TEXT,
        "paths": {"ffmpeg": str(paths.ffmpeg), "ffprobe": str(paths.ffprobe)},
        "source_probe": probe_record(source_probe),
        "wav_probe": probe_record(wav_probe),
        "trim": {
            "requested_start_seconds": 2.3,
            "requested_end_seconds": 8.7,
            "target_duration_seconds": 6.4,
            "actual": probe_record(trim_probe),
            "absolute_duration_error_seconds": abs(trim_probe.duration_seconds - 6.4),
        },
        "srt": {
            "source": str(source_srt),
            "retimed": str(retimed_srt),
            "cue_count": len(retimed),
            "cues": [asdict(cue) for cue in retimed],
        },
        "burned_probe": probe_record(burn_probe),
        "export_validation": {
            "trimmed": asdict(trimmed_validation),
            "burned": asdict(burned_validation),
        },
        "elapsed_seconds": {
            "synthetic_sample": sample_elapsed,
            "probe": probe_elapsed,
            "wav_extract": wav_elapsed,
            "precise_trim": trim_elapsed,
            "srt_retime": srt_elapsed,
            "subtitle_burn": burn_elapsed,
        },
        "file_sizes_bytes": {
            path.name: path.stat().st_size
            for path in (source, source_srt, wav, trimmed, retimed_srt, burned)
        },
    }

    summary_path = runtime_logs / f"media-validation-{run_id}.json"
    summary_output = prepare_output(summary_path)
    summary_temporary = temporary_sibling(summary_output)
    try:
        summary_temporary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        publish_without_overwrite(summary_temporary, summary_output)
    except Exception:
        discard_temporary(summary_temporary)
        raise

    print(f"SUMMARY_PATH={summary_output}")
    print(f"WORK_DIRECTORY={work}")
    print(f"SOURCE_DURATION_SECONDS={source_probe.duration_seconds:.6f}")
    print(f"WAV_DURATION_SECONDS={wav_probe.duration_seconds:.6f}")
    print(f"TRIM_DURATION_SECONDS={trim_probe.duration_seconds:.6f}")
    print(f"BURN_DURATION_SECONDS={burn_probe.duration_seconds:.6f}")
    print(f"TRIM_VALID={trimmed_validation.ok}")
    print(f"BURN_VALID={burned_validation.ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

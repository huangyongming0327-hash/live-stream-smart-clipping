"""Build a completely offline local listening-review package."""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from experiments.asr.common import atomic_write_json, atomic_write_text

from .input_parser import ReviewWindow, parse_review_csv
from .review_schema import MODEL_NAMES, build_export, initial_window_review
from .wav_clipper import clip_window, inspect_source_wav, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "local-data" / "asr-human-review"
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "review.html"


def _write_template_csv(
    path: Path,
    windows: list[ReviewWindow],
) -> None:
    fields = [
        "window_id",
        "start",
        "end",
        "label",
        *MODEL_NAMES,
        "best_candidate",
        "SenseVoice_severity",
        "Paraformer_severity",
        "Faster-Whisper_severity",
        "SenseVoice_error_tags",
        "Paraformer_error_tags",
        "Faster-Whisper_error_tags",
        "reference_text",
        "audio_hard_to_hear",
        "notes",
        "reviewed",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for window in windows:
                review = initial_window_review(window)
                writer.writerow(
                    {
                        "window_id": window.window_id,
                        "start": window.start,
                        "end": window.end,
                        "label": window.label,
                        **window.candidate_texts,
                        "best_candidate": "",
                        "SenseVoice_severity": "",
                        "Paraformer_severity": "",
                        "Faster-Whisper_severity": "",
                        "SenseVoice_error_tags": "",
                        "Paraformer_error_tags": "",
                        "Faster-Whisper_error_tags": "",
                        "reference_text": review["reference_text"],
                        "audio_hard_to_hear": "false",
                        "notes": review["notes"],
                        "reviewed": "false",
                    }
                )
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _render_html(package_data: dict[str, Any]) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    marker = "__REVIEW_DATA_JSON__"
    if template.count(marker) != 1:
        raise ValueError("review HTML template must contain exactly one data marker")
    embedded = json.dumps(
        package_data,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    embedded = (
        embedded.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return template.replace(marker, embedded)


def build_review_package(
    csv_path: str | Path,
    wav_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    padding_seconds: float = 0.8,
    expected_count: int = 20,
) -> dict[str, Any]:
    comparison_csv = Path(csv_path)
    source_wav = Path(wav_path)
    destination = Path(output_dir)

    wav_info = inspect_source_wav(source_wav)
    source_wav_sha_before = wav_info.sha256
    source_csv_sha_before = sha256_file(comparison_csv)
    windows = parse_review_csv(
        comparison_csv,
        audio_duration=wav_info.duration_seconds,
        expected_count=expected_count,
    )

    clips_dir = destination / "clips"
    exports_dir = destination / "exports"
    clips_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    clip_entries: list[dict[str, object]] = []
    reused_count = 0
    for sequence, window in enumerate(windows, start=1):
        filename = f"window-{sequence:03d}.wav"
        clip_entry, reused = clip_window(
            source_wav,
            clips_dir / filename,
            window,
            wav_info,
            padding_seconds=padding_seconds,
        )
        clip_entries.append(clip_entry)
        reused_count += int(reused)

    if sha256_file(source_wav) != source_wav_sha_before:
        raise RuntimeError("Source WAV changed while the package was being built")
    if sha256_file(comparison_csv) != source_csv_sha_before:
        raise RuntimeError("Comparison CSV changed while the package was being built")

    manifest = {
        "schema_version": "1.0",
        "manifest_type": "asr_human_review_package",
        "source": {
            "comparison_csv": {
                "name": comparison_csv.name,
                "sha256": source_csv_sha_before,
            },
            "wav": {
                "name": source_wav.name,
                "sha256": source_wav_sha_before,
                "compression_type": wav_info.compression_type,
                "channels": wav_info.channels,
                "sample_width_bytes": wav_info.sample_width_bytes,
                "sample_rate": wav_info.sample_rate,
                "frame_count": wav_info.frame_count,
                "duration_seconds": wav_info.duration_seconds,
            },
        },
        "padding_seconds": padding_seconds,
        "window_count": len(windows),
        "clips": clip_entries,
    }
    manifest_path = destination / "review-manifest.json"
    atomic_write_json(manifest_path, manifest)
    manifest_sha = sha256_file(manifest_path)

    initial_export = build_export(
        windows,
        source_manifest_sha256=manifest_sha,
    )
    package_windows: list[dict[str, Any]] = []
    for window, clip, review in zip(
        windows,
        clip_entries,
        initial_export["windows"],
        strict=True,
    ):
        package_windows.append(
            {
                "window_id": window.window_id,
                "start": window.start,
                "end": window.end,
                "label": window.label,
                "disagreement": window.disagreement,
                "audio_file": clip["file"],
                "candidate_texts": window.candidate_texts,
                "review": review,
            }
        )
    package_data = {
        "schema_version": "1.0",
        "review_type": "asr_human_listening_review",
        "source_manifest_sha256": manifest_sha,
        "total_window_count": len(windows),
        "windows": package_windows,
    }

    atomic_write_json(destination / "review-data.json", package_data)
    _write_template_csv(destination / "review-template.csv", windows)
    atomic_write_text(destination / "review.html", _render_html(package_data))
    atomic_write_text(
        destination / "README_LOCAL.md",
        "\n".join(
            (
                "# 本地人工听音审核包",
                "",
                "1. 直接使用 Chrome 或 Edge 打开同目录的 `review.html`。",
                "2. 逐窗口播放音频、比较三套候选并填写审核表单。",
                "3. 页面使用浏览器 localStorage 自动保存，也可手动保存。",
                "4. 全部完成后导出 `asr-human-review-completed.json`。",
                "5. 音频、审核结果、备注及导出文件仅保存在本地，请勿上传。",
                "6. `exports/` 可用于整理浏览器下载后移动回来的导出副本。",
                "",
            )
        ),
    )
    return {
        "window_count": len(windows),
        "clip_count": len(clip_entries),
        "reused_clip_count": reused_count,
        "source_manifest_sha256": manifest_sha,
        "review_html": str((destination / "review.html").resolve()),
        "output_dir": str(destination.resolve()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an offline TASK-002 human listening review package."
    )
    parser.add_argument("--csv", required=True, help="Existing 20-window comparison CSV")
    parser.add_argument("--wav", required=True, help="PCM 16 kHz mono 16-bit source WAV")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Local ignored output directory",
    )
    parser.add_argument("--padding-seconds", type=float, default=0.8)
    args = parser.parse_args()
    result = build_review_package(
        args.csv,
        args.wav,
        args.output_dir,
        padding_seconds=args.padding_seconds,
        expected_count=20,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

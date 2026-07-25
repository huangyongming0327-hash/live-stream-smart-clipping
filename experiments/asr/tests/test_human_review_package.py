from __future__ import annotations

import copy
import csv
import hashlib
import json
import re
import struct
import wave
from pathlib import Path

import pytest

from experiments.asr.human_review.build_review_package import build_review_package
from experiments.asr.human_review.input_parser import CSV_HEADERS, ReviewWindow
from experiments.asr.human_review.review_schema import (
    MODEL_NAMES,
    build_export,
    validate_review_export,
)


def _windows(count: int = 3) -> list[ReviewWindow]:
    return [
        ReviewWindow(
            window_id=str(index + 1),
            start=index * 0.15,
            end=index * 0.15 + 0.1,
            label="合成窗口",
            disagreement=0.1,
            candidate_texts={
                "SenseVoice": f"甲{index}",
                "Paraformer": f"乙{index}",
                "Faster-Whisper": f"丙{index}",
            },
        )
        for index in range(count)
    ]


def _write_csv(path: Path, windows: list[ReviewWindow]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for item in windows:
            writer.writerow(
                {
                    "窗口": item.window_id,
                    "开始秒": f"{item.start:.3f}",
                    "结束秒": f"{item.end:.3f}",
                    "类型": item.label,
                    "分歧分": f"{item.disagreement:.4f}",
                    **item.candidate_texts,
                }
            )


def _write_wav(path: Path, seconds: float = 4.0) -> None:
    samples = b"".join(
        struct.pack("<h", (index % 2000) - 1000)
        for index in range(int(seconds * 16_000))
    )
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(samples)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mark_all_complete(payload: dict) -> None:
    for row in payload["windows"]:
        row["best_candidate"] = "SenseVoice"
        row["severity"] = {model: 0 for model in MODEL_NAMES}
        row["reviewed"] = True
    payload["completed_window_count"] = len(payload["windows"])
    payload["completed"] = True


def test_review_schema_accepts_draft_and_completed_states() -> None:
    windows = _windows()
    draft = build_export(windows, source_manifest_sha256="a" * 64)
    validate_review_export(draft, windows)

    completed = copy.deepcopy(draft)
    _mark_all_complete(completed)
    validate_review_export(completed, windows)


@pytest.mark.parametrize(
    "mutator,match",
    [
        (
            lambda payload: payload["windows"][0].update(
                best_candidate="unknown"
            ),
            "unknown best_candidate",
        ),
        (
            lambda payload: payload["windows"][0]["severity"].update(
                SenseVoice=4
            ),
            "severity",
        ),
        (
            lambda payload: payload["windows"][0].update(window_id="999"),
            "unknown window_id",
        ),
        (
            lambda payload: payload["windows"][1].update(window_id="1"),
            "duplicate window_id",
        ),
    ],
)
def test_review_schema_rejects_invalid_values(mutator, match: str) -> None:
    windows = _windows()
    payload = build_export(windows, source_manifest_sha256="a" * 64)
    mutator(payload)

    with pytest.raises(ValueError, match=match):
        validate_review_export(payload, windows)


def test_three_window_synthetic_integration_is_offline_and_deterministic(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "input.csv"
    wav_path = tmp_path / "input.wav"
    output = tmp_path / "package"
    windows = _windows()
    _write_csv(csv_path, windows)
    _write_wav(wav_path)
    source_hashes = (_sha(csv_path), _sha(wav_path))

    first = build_review_package(
        csv_path,
        wav_path,
        output,
        expected_count=3,
    )
    stable_files = [
        output / "review.html",
        output / "review-data.json",
        output / "review-template.csv",
        output / "review-manifest.json",
        *sorted((output / "clips").glob("*.wav")),
    ]
    first_hashes = {path.name: _sha(path) for path in stable_files}
    second = build_review_package(
        csv_path,
        wav_path,
        output,
        expected_count=3,
    )

    assert first["window_count"] == first["clip_count"] == 3
    assert second["reused_clip_count"] == 3
    assert {path.name: _sha(path) for path in stable_files} == first_hashes
    assert (_sha(csv_path), _sha(wav_path)) == source_hashes
    assert len(list((output / "clips").glob("window-*.wav"))) == 3
    for clip in (output / "clips").glob("*.wav"):
        with wave.open(str(clip), "rb") as handle:
            assert (
                handle.getnchannels(),
                handle.getsampwidth(),
                handle.getframerate(),
            ) == (1, 2, 16_000)

    html = (output / "review.html").read_text(encoding="utf-8")
    assert not re.search(r"https?://", html, re.IGNORECASE)
    assert str(csv_path.resolve()) not in html
    assert str(wav_path.resolve()) not in html
    for token in (
        "localStorage",
        "asr-human-review-completed.json",
        "asr-human-review-completed.csv",
        "completed_window_count",
        "source_manifest_sha256",
        "best_candidate",
        "severity",
        "error_tags",
        "reference_text",
        "audio_hard_to_hear",
        "notes",
        "reviewed",
    ):
        assert token in html

    data = json.loads((output / "review-data.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (output / "review-manifest.json").read_text(encoding="utf-8")
    )
    with (output / "review-template.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        template_rows = list(csv.DictReader(handle))
    assert len(data["windows"]) == len(template_rows) == manifest["window_count"] == 3
    assert [item["window_id"] for item in data["windows"]] == [
        row["window_id"] for row in template_rows
    ]
    assert all((output / item["audio_file"]).is_file() for item in data["windows"])


def test_generated_html_embeds_all_20_windows(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    wav_path = tmp_path / "input.wav"
    output = tmp_path / "package"
    windows = _windows(20)
    _write_csv(csv_path, windows)
    _write_wav(wav_path)

    build_review_package(csv_path, wav_path, output, expected_count=20)
    data = json.loads((output / "review-data.json").read_text(encoding="utf-8"))
    html = (output / "review.html").read_text(encoding="utf-8")
    embedded_match = re.search(
        r'<script id="reviewPackageData" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )

    assert len(data["windows"]) == 20
    assert embedded_match is not None
    assert len(json.loads(embedded_match.group(1))["windows"]) == 20
    assert all(f"clips/window-{index:03d}.wav" in html for index in range(1, 21))

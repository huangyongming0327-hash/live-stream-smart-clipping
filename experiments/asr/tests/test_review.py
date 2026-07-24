from __future__ import annotations

import wave
from pathlib import Path

from experiments.asr.review import build_windows


def test_review_windows_keep_all_required_categories(tmp_path: Path) -> None:
    wav_path = tmp_path / "sample.wav"
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(b"\x00\x01" * 16_000 * 240)

    result = {
        "segments": [
            {"start": 0.0, "end": 240.0, "text": "普通话测试", "events": [], "emotion": None}
        ]
    }
    windows = build_windows({"a": result, "b": result, "c": result}, wav_path, 240.0)
    labels = [item["label"] for item in windows]

    assert len(windows) == 20
    assert {"开头", "中间", "结尾"}.issubset(labels)
    assert any("短句" in label for label in labels)
    assert any("长句" in label for label in labels)
    assert any("英文" in label for label in labels)
    assert any("低音量" in label for label in labels)
    assert any("噪声" in label for label in labels)
    assert any("笑声/掌声" in label for label in labels)
    assert any(label.startswith("候选分歧高") for label in labels)

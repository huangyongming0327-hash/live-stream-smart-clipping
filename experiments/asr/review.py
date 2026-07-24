"""Generate a 20-window no-reference human review package."""

from __future__ import annotations

import argparse
import audioop
import csv
import json
import re
import wave
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .common import atomic_write_text


DISCLAIMER = "准确率排名待人工审核，当前只比较技术性能、输出完整性和候选分歧。"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _window_text(result: dict[str, Any], start: float, end: float) -> str:
    return " ".join(
        segment["text"] for segment in result["segments"]
        if float(segment["end"]) > start and float(segment["start"]) < end
    ).strip()


def _disagreement(texts: list[str]) -> float:
    if len(texts) < 2:
        return 0.0
    scores: list[float] = []
    for left in range(len(texts)):
        for right in range(left + 1, len(texts)):
            scores.append(1.0 - SequenceMatcher(None, texts[left], texts[right]).ratio())
    return sum(scores) / len(scores)


def _energy_bins(wav_path: Path, seconds: int = 20) -> list[tuple[float, float]]:
    values: list[tuple[float, float]] = []
    with wave.open(str(wav_path), "rb") as handle:
        rate = handle.getframerate()
        frames = rate * seconds
        start = 0.0
        while data := handle.readframes(frames):
            values.append((start, float(audioop.rms(data, handle.getsampwidth()))))
            start += len(data) / (handle.getsampwidth() * handle.getnchannels() * rate)
    return values


def build_windows(results: dict[str, dict[str, Any]], wav_path: Path, duration: float) -> list[dict[str, Any]]:
    candidates = list(results)
    windows: list[dict[str, Any]] = []

    def add(start: float, label: str, length: float = 20.0) -> bool:
        start = max(0.0, min(start, max(0.0, duration - length)))
        if any(abs(item["start"] - start) < 4.0 for item in windows):
            return False
        end = min(duration, start + length)
        texts = {name: _window_text(results[name], start, end) for name in candidates}
        windows.append(
            {
                "start": start,
                "end": end,
                "label": label,
                "disagreement": _disagreement(list(texts.values())),
                "texts": texts,
            }
        )
        return True

    def add_near(start: float, label: str, length: float = 20.0) -> bool:
        """Add a required category, moving slightly when another window is too close."""

        offsets = [0.0]
        for distance in range(5, 105, 5):
            offsets.extend((float(distance), float(-distance)))
        return any(add(start + offset, label, length) for offset in offsets)

    for fraction, label in (
        (0.0, "开头"), (0.25, "前段"), (0.50, "中间"),
        (0.75, "后段"), (1.0, "结尾")
    ):
        add_near(duration * fraction - (20.0 if fraction == 1.0 else 0.0), label)

    scored: list[tuple[float, float, list[str]]] = []
    for start in range(0, int(duration), 20):
        texts = [_window_text(result, start, min(duration, start + 20)) for result in results.values()]
        scored.append((_disagreement(texts), float(start), texts))
    for score, start, _ in sorted(scored, reverse=True):
        add_near(start, f"候选分歧高（{score:.3f}）")
        if sum(item["label"].startswith("候选分歧高") for item in windows) >= 5:
            break

    english = re.compile(r"\b[A-Za-z][A-Za-z0-9+.#-]{1,}\b")
    for _, start, texts in sorted(scored, key=lambda item: item[1]):
        if any(english.search(text) for text in texts):
            add_near(start, "英文词/中英混合")
        if sum("英文" in item["label"] for item in windows) >= 2:
            break
    while sum("英文" in item["label"] for item in windows) < 2:
        index = sum("英文" in item["label"] for item in windows)
        add_near(duration * (0.35 + index * 0.25), "英文词人工检查（模型未检测到）")

    event_starts: list[float] = []
    for result in results.values():
        for segment in result["segments"]:
            if segment.get("events") or segment.get("emotion"):
                event_starts.append(float(segment["start"]))
    if event_starts:
        for start in event_starts[:2]:
            add_near(start, "笑声/掌声/事件或情绪标签")
    while sum("笑声/掌声" in item["label"] for item in windows) < 2:
        index = sum("笑声/掌声" in item["label"] for item in windows)
        add_near(duration * (0.42 + index * 0.20), "笑声/掌声/事件人工检查（模型未标记）")

    energy = _energy_bins(wav_path)
    nonzero = [item for item in energy if item[1] > 5]
    if nonzero:
        add_near(min(nonzero, key=lambda item: item[1])[0], "低音量（RMS 代理）")
        add_near(max(nonzero, key=lambda item: item[1])[0], "高能量/噪声人工检查（RMS 代理）")

    by_length = sorted(
        scored, key=lambda item: sum(len(text) for text in item[2])
    )
    if by_length:
        add_near(by_length[0][1], "短句/稀疏语音")
        add_near(by_length[-1][1], "长句/密集语音")

    fill_index = 0
    while len(windows) < 20:
        add_near(duration * fill_index / 20.0, "均匀固定补充窗口")
        fill_index += 1
        if fill_index > 100:
            break
    return windows[:20]


def write_review(windows: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = list(windows[0]["texts"]) if windows else []
    rows: list[list[str]] = []
    md = ["# TASK-002 人工审核对比", "", f"> {DISCLAIMER}", ""]
    for index, item in enumerate(windows, start=1):
        md.extend(
            [
                f"## 窗口 {index:02d}｜{item['label']}", "",
                f"- 时间：{item['start']:.3f}—{item['end']:.3f} 秒",
                f"- 候选分歧分：{item['disagreement']:.4f}", "",
            ]
        )
        row = [str(index), f"{item['start']:.3f}", f"{item['end']:.3f}", item["label"], f"{item['disagreement']:.4f}"]
        for candidate in candidates:
            text = item["texts"][candidate]
            md.extend([f"### {candidate}", "", text or "（此窗口无文本）", ""])
            row.append(text)
        rows.append(row)
    atomic_write_text(output_dir / "人工审核对比.md", "\n".join(md).rstrip() + "\n")
    csv_path = output_dir / "人工审核对比.csv"
    temporary = csv_path.with_name(f".{csv_path.name}.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["窗口", "开始秒", "结束秒", "类型", "分歧分", *candidates])
        writer.writerows(rows)
    temporary.replace(csv_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--result", action="append", required=True, help="name=path")
    args = parser.parse_args()
    results: dict[str, dict[str, Any]] = {}
    for entry in args.result:
        name, separator, path = entry.partition("=")
        if not separator:
            raise ValueError("--result must use name=path")
        results[name] = _load(Path(path).resolve())
    windows = build_windows(results, Path(args.wav).resolve(), args.duration)
    if len(windows) != 20:
        raise RuntimeError(f"Expected 20 review windows, got {len(windows)}")
    write_review(windows, Path(args.output_dir).resolve())


if __name__ == "__main__":
    main()

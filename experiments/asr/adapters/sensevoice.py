"""Official sherpa-onnx SenseVoice INT8 CPU adapter."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from liveclip.asr.adapters import SenseVoiceAdapter

from ..common import build_unified_result, new_segment, sha256_file
from .base import execute_run


def _events(value: str | None) -> list[str]:
    if not value or value.lower() in {"speech", "none", "null"}:
        return []
    return [value]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-kind", choices=("cold", "warm", "offline"), required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--probe-audio", required=True)
    parser.add_argument("--silence", required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--tokens", required=True)
    parser.add_argument("--vad", required=True)
    args = parser.parse_args()

    model_path = Path(args.model).resolve()
    tokens_path = Path(args.tokens).resolve()
    vad_path = Path(args.vad).resolve()
    for required in (model_path, tokens_path, vad_path):
        if not required.is_file():
            raise FileNotFoundError(required)

    def load_model() -> tuple[dict[str, Any], str]:
        adapter = SenseVoiceAdapter(model_path.parent.parent)
        return {"adapter": adapter}, adapter.runtime_version

    def transcribe_factory(loaded: dict[str, Any]):
        adapter: SenseVoiceAdapter = loaded["adapter"]

        def transcribe(path: str | Path) -> tuple[Any, dict[str, Any]]:
            raw_segments, timed_segments = adapter.transcribe_with_raw(Path(path))
            unified_segments: list[dict[str, Any]] = []
            timed_iterator = iter(timed_segments)
            for raw_item in raw_segments:
                if not str(raw_item["text"] or "").strip():
                    continue
                timed = next(timed_iterator)
                text = timed.text_raw.strip()
                unified_segments.append(
                    new_segment(
                        start=timed.start_ms / 1000,
                        end=timed.end_ms / 1000,
                        text=text,
                        raw_text=text,
                        language=raw_item["language"],
                        emotion=raw_item["emotion"],
                        events=_events(raw_item["event"]),
                        words=[],
                    )
                )
            unified = build_unified_result(
                candidate="sensevoice-sherpa-onnx-int8",
                model_name="sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17",
                model_revision="2024-07-17-int8",
                runtime_version=getattr(sherpa_onnx, "__version__", "1.13.4"),
                compute_type="int8",
                input_sha256=sha256_file(path),
                segments=unified_segments,
                warnings=["Timestamp granularity is VAD speech-segment boundaries; word timestamps are unavailable."],
            )
            return {"segments": raw_segments}, unified

        return transcribe

    execute_run(
        output_dir=args.output_dir, run_kind=args.run_kind, audio_path=args.audio,
        probe_audio_path=args.probe_audio, silence_path=args.silence,
        audio_duration=args.duration, load_model=load_model,
        transcribe_factory=transcribe_factory,
        candidate="sensevoice-sherpa-onnx-int8",
        model_name="sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17",
        model_revision="2024-07-17-int8", compute_type="int8"
    )


if __name__ == "__main__":
    main()

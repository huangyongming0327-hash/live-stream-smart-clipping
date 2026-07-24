"""Official SYSTRAN faster-whisper small CPU int8 adapter."""

from __future__ import annotations

import argparse
import importlib.metadata
import math
import wave
from pathlib import Path
from typing import Any

from ..common import build_unified_result, new_segment, sha256_file
from .base import execute_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-kind", choices=("cold", "warm", "offline"), required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--probe-audio", required=True)
    parser.add_argument("--silence", required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    model_path = Path(args.model).resolve()
    if not model_path.is_dir():
        raise FileNotFoundError(model_path)
    runtime_version = importlib.metadata.version("faster-whisper")

    def load_model() -> tuple[Any, str]:
        model = WhisperModel(
            str(model_path), device="cpu", compute_type="int8",
            cpu_threads=4, num_workers=1, local_files_only=True
        )
        return model, runtime_version

    def transcribe_factory(model: Any):
        def transcribe(path: str | Path) -> tuple[Any, dict[str, Any]]:
            with wave.open(str(path), "rb") as handle:
                duration = handle.getnframes() / handle.getframerate()
            generated, info = model.transcribe(
                str(Path(path).resolve()), language="zh", task="transcribe",
                beam_size=5, temperature=0.0, vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                word_timestamps=True, condition_on_previous_text=True
            )
            raw_segments: list[dict[str, Any]] = []
            unified_segments: list[dict[str, Any]] = []
            for segment in generated:
                start = max(0.0, float(segment.start))
                end = min(duration, float(segment.end))
                text = str(segment.text or "").strip()
                words: list[dict[str, Any]] = []
                raw_words: list[dict[str, Any]] = []
                for word in segment.words or []:
                    ws = getattr(word, "start", None)
                    we = getattr(word, "end", None)
                    probability = getattr(word, "probability", None)
                    raw_word = {
                        "start": ws, "end": we, "word": str(getattr(word, "word", "")),
                        "probability": probability
                    }
                    raw_words.append(raw_word)
                    if ws is None or we is None:
                        continue
                    ws, we = float(ws), float(we)
                    if not (math.isfinite(ws) and math.isfinite(we)):
                        continue
                    ws, we = max(start, ws), min(end, we)
                    if we <= ws:
                        continue
                    confidence = float(probability) if probability is not None else None
                    if confidence is not None and not 0 <= confidence <= 1:
                        confidence = None
                    words.append(
                        {"start": ws, "end": we, "text": raw_word["word"], "confidence": confidence}
                    )
                raw_segments.append(
                    {
                        "id": segment.id, "seek": segment.seek, "start": start, "end": end,
                        "text": text, "tokens": list(segment.tokens),
                        "avg_logprob": segment.avg_logprob,
                        "compression_ratio": segment.compression_ratio,
                        "no_speech_prob": segment.no_speech_prob,
                        "words": raw_words,
                    }
                )
                if text and end > start:
                    unified_segments.append(
                        new_segment(
                            start=start, end=end, text=text, raw_text=str(segment.text or ""),
                            language=info.language, words=words
                        )
                    )
            raw = {
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "duration_after_vad": info.duration_after_vad,
                "segments": raw_segments,
            }
            unified = build_unified_result(
                candidate="faster-whisper-small",
                model_name="Systran/faster-whisper-small",
                model_revision="536b0662742c02347bc0e980a01041f333bce120",
                runtime_version=runtime_version, compute_type="int8",
                input_sha256=sha256_file(path), segments=unified_segments
            )
            return raw, unified

        return transcribe

    execute_run(
        output_dir=args.output_dir, run_kind=args.run_kind, audio_path=args.audio,
        probe_audio_path=args.probe_audio, silence_path=args.silence,
        audio_duration=args.duration, load_model=load_model,
        transcribe_factory=transcribe_factory,
        candidate="faster-whisper-small", model_name="Systran/faster-whisper-small",
        model_revision="536b0662742c02347bc0e980a01041f333bce120",
        compute_type="int8"
    )


if __name__ == "__main__":
    main()

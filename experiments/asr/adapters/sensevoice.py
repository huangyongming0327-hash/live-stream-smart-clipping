"""Official sherpa-onnx SenseVoice INT8 CPU adapter."""

from __future__ import annotations

import argparse
import wave
from pathlib import Path
from typing import Any

from ..common import build_unified_result, new_segment, sha256_file
from .base import execute_run


def _read_pcm16(path: str | Path) -> tuple[int, Any]:
    import numpy as np

    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise ValueError("SenseVoice input must be mono PCM16 WAV")
        sample_rate = handle.getframerate()
        samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
    return sample_rate, samples.astype(np.float32) / 32768.0


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

    import sherpa_onnx

    model_path = Path(args.model).resolve()
    tokens_path = Path(args.tokens).resolve()
    vad_path = Path(args.vad).resolve()
    for required in (model_path, tokens_path, vad_path):
        if not required.is_file():
            raise FileNotFoundError(required)

    def load_model() -> tuple[dict[str, Any], str]:
        recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model_path), tokens=str(tokens_path), num_threads=4,
            use_itn=True, debug=False, provider="cpu"
        )
        vad_config = sherpa_onnx.VadModelConfig()
        vad_config.silero_vad.model = str(vad_path)
        vad_config.silero_vad.threshold = 0.2
        vad_config.silero_vad.min_silence_duration = 0.25
        vad_config.silero_vad.min_speech_duration = 0.25
        vad_config.silero_vad.max_speech_duration = 5.0
        vad_config.silero_vad.window_size = 512
        vad_config.sample_rate = 16000
        detector = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=60)
        return {"recognizer": recognizer, "vad_config": vad_config, "detector": detector}, getattr(sherpa_onnx, "__version__", "1.13.4")

    def transcribe_factory(loaded: dict[str, Any]):
        recognizer = loaded["recognizer"]
        vad_config = loaded["vad_config"]

        def transcribe(path: str | Path) -> tuple[Any, dict[str, Any]]:
            import numpy as np
            import sherpa_onnx

            sample_rate, samples = _read_pcm16(path)
            if sample_rate != 16000:
                raise ValueError("SenseVoice input sample rate must be 16000")
            detector = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=60)
            window = vad_config.silero_vad.window_size
            for offset in range(0, len(samples), window):
                chunk = samples[offset : offset + window]
                if len(chunk) < window:
                    chunk = np.pad(chunk, (0, window - len(chunk)))
                detector.accept_waveform(chunk)
            detector.flush()
            raw_segments: list[dict[str, Any]] = []
            unified_segments: list[dict[str, Any]] = []
            duration = len(samples) / sample_rate
            while not detector.empty():
                speech = detector.front
                speech_start = int(speech.start)
                speech_samples = np.asarray(speech.samples, dtype=np.float32).copy()
                detector.pop()
                start = speech_start / sample_rate
                end = min(duration, (speech_start + len(speech_samples)) / sample_rate)
                if end <= start:
                    continue
                stream = recognizer.create_stream()
                stream.accept_waveform(sample_rate, speech_samples)
                recognizer.decode_stream(stream)
                result = stream.result
                text = str(result.text or "").strip()
                raw_item = {
                    "start": start,
                    "end": end,
                    "text": text,
                    "tokens": list(getattr(result, "tokens", []) or []),
                    "timestamps": list(getattr(result, "timestamps", []) or []),
                    "language": getattr(result, "lang", None),
                    "emotion": getattr(result, "emotion", None),
                    "event": getattr(result, "event", None),
                }
                raw_segments.append(raw_item)
                if text:
                    unified_segments.append(
                        new_segment(
                            start=start, end=end, text=text, raw_text=text,
                            language=raw_item["language"], emotion=raw_item["emotion"],
                            events=_events(raw_item["event"]), words=[]
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

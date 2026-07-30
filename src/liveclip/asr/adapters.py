"""Lightweight local adapters for the two approved ASR engines."""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import socket
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal, Protocol


Engine = Literal["paraformer", "sensevoice"]
_MISSING = object()


class ASRAdapterError(RuntimeError):
    """Raised when a local model cannot produce a trustworthy timed result."""


@dataclass(frozen=True, slots=True)
class AdapterSegment:
    start_ms: int
    end_ms: int
    text_raw: str


class ASRAdapter(Protocol):
    engine: Engine
    identity: str

    def transcribe(self, wav_path: Path) -> list[AdapterSegment]:
        """Transcribe one short PCM16/16 kHz/mono WAV chunk."""


@contextlib.contextmanager
def offline_network_guard(enabled: bool = True) -> Iterator[None]:
    """Fail closed if a local model attempts any socket connection."""

    if not enabled:
        yield
        return
    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection

    def blocked_connect(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("LiveClip local ASR blocked a network connection")

    socket.socket.connect = blocked_connect  # type: ignore[method-assign]
    socket.create_connection = blocked_connect  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.create_connection = original_create_connection  # type: ignore[assignment]


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    return str(value)


def _number_ms(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ASRAdapterError(f"Paraformer returned invalid {field}.")
    number = float(value)
    if not math.isfinite(number):
        raise ASRAdapterError(f"Paraformer returned non-finite {field}.")
    return int(math.floor(number + 0.5))


def _validate_range(
    start_value: Any,
    end_value: Any,
    *,
    duration_ms: int,
    label: str,
) -> tuple[int, int]:
    if start_value is _MISSING or end_value is _MISSING:
        raise ASRAdapterError(f"Paraformer returned text without timing at {label}.")
    start_ms = _number_ms(start_value, field=f"{label}.start")
    end_ms = _number_ms(end_value, field=f"{label}.end")
    if start_ms < 0 or end_ms <= start_ms or end_ms > duration_ms + 1:
        raise ASRAdapterError(f"Paraformer returned out-of-range timing at {label}.")
    return start_ms, min(end_ms, duration_ms)


def _wav_duration_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as handle:
            if (
                handle.getnchannels() != 1
                or handle.getsampwidth() != 2
                or handle.getframerate() != 16000
            ):
                raise ASRAdapterError(
                    "ASR chunk must be PCM16, 16 kHz, mono WAV."
                )
            frames = handle.getnframes()
            return int(math.floor(frames * 1000 / handle.getframerate() + 0.5))
    except (OSError, wave.Error) as exc:
        raise ASRAdapterError(f"ASR chunk is not a readable WAV: {path}") from exc


def parse_paraformer_segments(
    result: list[dict[str, Any]],
    duration_ms: int,
) -> list[AdapterSegment]:
    """Convert audited FunASR timing fields without inventing timestamps."""

    segments: list[AdapterSegment] = []
    previous_start = -1
    previous_end = -1
    for raw_index, item in enumerate(result):
        sentence_info = item.get("sentence_info", _MISSING)
        if isinstance(sentence_info, list) and sentence_info:
            saw_text = False
            for sentence_index, sentence in enumerate(sentence_info):
                if not isinstance(sentence, dict):
                    continue
                text_raw = str(sentence.get("text") or "")
                if not text_raw.strip():
                    continue
                saw_text = True
                start_ms, end_ms = _validate_range(
                    sentence.get("start", _MISSING),
                    sentence.get("end", _MISSING),
                    duration_ms=duration_ms,
                    label=f"raw[{raw_index}].sentence_info[{sentence_index}]",
                )
                if start_ms < previous_start or end_ms < previous_end:
                    raise ASRAdapterError(
                        "Paraformer returned non-monotonic sentence timing."
                    )
                segments.append(AdapterSegment(start_ms, end_ms, text_raw))
                previous_start, previous_end = start_ms, end_ms
            if saw_text:
                continue

        text_raw = str(item.get("text") or "")
        if not text_raw.strip():
            continue
        timestamps = item.get("timestamp", _MISSING)
        if not isinstance(timestamps, list) or not timestamps:
            raise ASRAdapterError(
                f"Paraformer returned text without timing at raw[{raw_index}]."
            )
        parsed = [
            _validate_range(
                pair[0] if isinstance(pair, (list, tuple)) and len(pair) == 2 else _MISSING,
                pair[1] if isinstance(pair, (list, tuple)) and len(pair) == 2 else _MISSING,
                duration_ms=duration_ms,
                label=f"raw[{raw_index}].timestamp[{pair_index}]",
            )
            for pair_index, pair in enumerate(timestamps)
        ]
        for current, previous in zip(parsed[1:], parsed):
            if current[0] < previous[0] or current[1] < previous[1]:
                raise ASRAdapterError(
                    "Paraformer returned non-monotonic token timing."
                )
        start_ms, end_ms = parsed[0][0], parsed[-1][1]
        if start_ms < previous_start or end_ms < previous_end:
            raise ASRAdapterError("Paraformer returned non-monotonic result timing.")
        segments.append(AdapterSegment(start_ms, end_ms, text_raw))
        previous_start, previous_end = start_ms, end_ms
    return segments


def _identity(paths: list[Path]) -> str:
    evidence: list[dict[str, Any]] = []
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_file():
            raise ASRAdapterError(f"Required local model file is missing: {resolved}")
        stat = resolved.stat()
        evidence.append(
            {
                "name": resolved.name,
                "parent": resolved.parent.name,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    payload = json.dumps(
        evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def model_identity(engine: Engine, model_root: Path) -> str:
    root = model_root.resolve()
    if engine == "paraformer":
        return _identity(
            [
                root / "paraformer-zh" / "model.pt",
                root / "paraformer-zh" / "config.yaml",
                root / "fsmn-vad" / "model.pt",
                root / "fsmn-vad" / "config.yaml",
                root / "ct-punc" / "model.pt",
                root / "ct-punc" / "config.yaml",
            ]
        )
    if engine == "sensevoice":
        model = root / "sensevoice-small"
        return _identity(
            [
                model / "model.int8.onnx",
                model / "tokens.txt",
                model / "silero_vad.onnx",
            ]
        )
    raise ASRAdapterError(f"Unsupported ASR engine: {engine}")


class ParaformerAdapter:
    engine: Engine = "paraformer"

    def __init__(self, model_root: Path) -> None:
        self.identity = model_identity(self.engine, model_root)
        root = model_root.resolve()
        try:
            import funasr
            import torch
            from funasr import AutoModel
        except Exception as exc:
            raise ASRAdapterError(
                "Paraformer runtime is unavailable; run with the existing FunASR Python."
            ) from exc
        if torch.cuda.is_available() or getattr(torch.version, "cuda", None) is not None:
            raise ASRAdapterError("Only the audited CPU Paraformer runtime is allowed.")
        torch.set_num_threads(4)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass
        try:
            with offline_network_guard():
                self._model = AutoModel(
                    model=str(root / "paraformer-zh"),
                    vad_model=str(root / "fsmn-vad"),
                    punc_model=str(root / "ct-punc"),
                    device="cpu",
                    disable_update=True,
                    hub="ms",
                )
        except Exception as exc:
            raise ASRAdapterError(f"Paraformer model loading failed: {exc}") from exc
        self.runtime_version = getattr(funasr, "__version__", "unknown")

    def generate_raw(
        self,
        wav_path: Path,
        *,
        hotword: str | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "input": str(wav_path.resolve()),
            "cache": {},
            "batch_size_s": 60,
            "batch_size_threshold_s": 30,
            "merge_vad": True,
            "merge_length_s": 15,
            "sentence_timestamp": True,
        }
        if hotword is not None:
            kwargs["hotword"] = hotword
        try:
            with offline_network_guard():
                raw = self._model.generate(**kwargs)
        except Exception as exc:
            raise ASRAdapterError(f"Paraformer chunk recognition failed: {exc}") from exc
        safe = _jsonable(raw)
        if not isinstance(safe, list) or not all(
            isinstance(item, dict) for item in safe
        ):
            raise ASRAdapterError("Paraformer returned an unexpected result structure.")
        return safe

    def transcribe(self, wav_path: Path) -> list[AdapterSegment]:
        duration_ms = _wav_duration_ms(wav_path)
        safe = self.generate_raw(wav_path)
        return parse_paraformer_segments(safe, duration_ms)


class SenseVoiceAdapter:
    engine: Engine = "sensevoice"

    def __init__(self, model_root: Path) -> None:
        self.identity = model_identity(self.engine, model_root)
        model = model_root.resolve() / "sensevoice-small"
        try:
            import sherpa_onnx
        except Exception as exc:
            raise ASRAdapterError(
                "SenseVoice runtime is unavailable; run with the existing sherpa-onnx Python."
            ) from exc
        try:
            with offline_network_guard():
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                    model=str(model / "model.int8.onnx"),
                    tokens=str(model / "tokens.txt"),
                    num_threads=4,
                    use_itn=True,
                    debug=False,
                    provider="cpu",
                )
                config = sherpa_onnx.VadModelConfig()
                config.silero_vad.model = str(model / "silero_vad.onnx")
                config.silero_vad.threshold = 0.2
                config.silero_vad.min_silence_duration = 0.25
                config.silero_vad.min_speech_duration = 0.25
                config.silero_vad.max_speech_duration = 5.0
                config.silero_vad.window_size = 512
                config.sample_rate = 16000
                self._vad_config = config
        except Exception as exc:
            raise ASRAdapterError(f"SenseVoice model loading failed: {exc}") from exc
        self.runtime_version = getattr(sherpa_onnx, "__version__", "unknown")

    def transcribe_with_raw(
        self, wav_path: Path
    ) -> tuple[list[dict[str, Any]], list[AdapterSegment]]:
        try:
            import numpy as np
            import sherpa_onnx
        except Exception as exc:
            raise ASRAdapterError("SenseVoice runtime dependencies are unavailable.") from exc
        try:
            with wave.open(str(wav_path), "rb") as handle:
                if (
                    handle.getnchannels() != 1
                    or handle.getsampwidth() != 2
                    or handle.getframerate() != 16000
                ):
                    raise ASRAdapterError(
                        "SenseVoice input must be PCM16, 16 kHz, mono WAV."
                    )
                samples = np.frombuffer(
                    handle.readframes(handle.getnframes()), dtype=np.int16
                ).astype(np.float32) / 32768.0
        except (OSError, wave.Error) as exc:
            raise ASRAdapterError(f"SenseVoice cannot read WAV chunk: {wav_path}") from exc

        detector = sherpa_onnx.VoiceActivityDetector(
            self._vad_config, buffer_size_in_seconds=60
        )
        window = self._vad_config.silero_vad.window_size
        for offset in range(0, len(samples), window):
            chunk = samples[offset : offset + window]
            if len(chunk) < window:
                chunk = np.pad(chunk, (0, window - len(chunk)))
            detector.accept_waveform(chunk)
        detector.flush()

        raw_result: list[dict[str, Any]] = []
        result: list[AdapterSegment] = []
        duration_ms = int(math.floor(len(samples) * 1000 / 16000 + 0.5))
        while not detector.empty():
            speech = detector.front
            speech_start = int(speech.start)
            speech_samples = np.asarray(speech.samples, dtype=np.float32).copy()
            detector.pop()
            start_ms = int(math.floor(speech_start * 1000 / 16000 + 0.5))
            end_ms = min(
                duration_ms,
                int(
                    math.floor(
                        (speech_start + len(speech_samples)) * 1000 / 16000 + 0.5
                    )
                ),
            )
            if end_ms <= start_ms:
                continue
            try:
                with offline_network_guard():
                    stream = self._recognizer.create_stream()
                    stream.accept_waveform(16000, speech_samples)
                    self._recognizer.decode_stream(stream)
                    recognition = stream.result
                text_raw = str(recognition.text or "")
            except Exception as exc:
                raise ASRAdapterError(
                    f"SenseVoice chunk recognition failed: {exc}"
                ) from exc
            raw_result.append(
                {
                    "start": start_ms / 1000,
                    "end": end_ms / 1000,
                    "text": text_raw,
                    "tokens": list(getattr(recognition, "tokens", []) or []),
                    "timestamps": list(getattr(recognition, "timestamps", []) or []),
                    "language": getattr(recognition, "lang", None),
                    "emotion": getattr(recognition, "emotion", None),
                    "event": getattr(recognition, "event", None),
                }
            )
            if text_raw.strip():
                result.append(AdapterSegment(start_ms, end_ms, text_raw))
        return raw_result, result

    def transcribe(self, wav_path: Path) -> list[AdapterSegment]:
        _, segments = self.transcribe_with_raw(wav_path)
        return segments


def create_adapter(engine: Engine, model_root: Path) -> ASRAdapter:
    if engine == "paraformer":
        return ParaformerAdapter(model_root)
    if engine == "sensevoice":
        return SenseVoiceAdapter(model_root)
    raise ASRAdapterError(f"Unsupported ASR engine: {engine}")

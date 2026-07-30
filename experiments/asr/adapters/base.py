"""Shared command-line lifecycle for candidate adapters."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

from liveclip.asr.adapters import offline_network_guard

from ..common import assess_silence, atomic_write_json, sha256_file, write_run_artifacts
from ..resource_monitor import ResourceMonitor


Transcribe = Callable[[str | Path], tuple[Any, dict[str, Any]]]


def environment_evidence() -> dict[str, Any]:
    names = (
        "PIP_CACHE_DIR", "HF_HOME", "HUGGINGFACE_HUB_CACHE", "MODELSCOPE_CACHE",
        "TORCH_HOME", "XDG_CACHE_HOME", "TEMP", "TMP", "OMP_NUM_THREADS",
        "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE", "MODELSCOPE_OFFLINE"
    )
    return {name: os.environ.get(name) for name in names}


def execute_run(
    *,
    output_dir: str | Path,
    run_kind: str,
    audio_path: str | Path,
    probe_audio_path: str | Path,
    silence_path: str | Path,
    audio_duration: float,
    load_model: Callable[[], tuple[Any, str]],
    transcribe_factory: Callable[[Any], Transcribe],
    candidate: str,
    model_name: str,
    model_revision: str,
    compute_type: str,
    extra_probe: Callable[[Any], dict[str, Any]] | None = None,
) -> None:
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    monitor = ResourceMonitor(destination / "resource-samples.jsonl", 0.5)
    monitor.start()
    started = time.perf_counter()
    load_seconds = 0.0
    phase_metrics: dict[str, Any] = {}
    raw_payload: Any = None
    unified: dict[str, Any] | None = None
    silence_assessment: dict[str, Any] | None = None
    runtime_version = "unknown"
    try:
        with offline_network_guard(run_kind == "offline"):
            load_started = time.perf_counter()
            model, runtime_version = load_model()
            load_seconds = time.perf_counter() - load_started
            transcribe = transcribe_factory(model)
            if run_kind == "cold":
                warmup_started = time.perf_counter()
                transcribe(probe_audio_path)
                phase_metrics["warmup_seconds"] = time.perf_counter() - warmup_started
                full_started = time.perf_counter()
                raw_payload, unified = transcribe(audio_path)
                full_seconds = time.perf_counter() - full_started
                phase_metrics.update(
                    full_transcription_seconds=full_seconds,
                    rtf=full_seconds / audio_duration,
                )
            elif run_kind == "warm":
                full_started = time.perf_counter()
                raw_payload, unified = transcribe(audio_path)
                full_seconds = time.perf_counter() - full_started
                silence_started = time.perf_counter()
                silence_raw, silence_unified = transcribe(silence_path)
                silence_seconds = time.perf_counter() - silence_started
                silence_assessment = assess_silence(silence_unified)
                atomic_write_json(destination / "silence-raw.json", silence_raw)
                atomic_write_json(destination / "silence-unified.json", silence_unified)
                phase_metrics.update(
                    full_transcription_seconds=full_seconds,
                    rtf=full_seconds / audio_duration,
                    silence_seconds=silence_seconds,
                    silence=silence_assessment,
                )
                if extra_probe is not None:
                    probe_started = time.perf_counter()
                    phase_metrics["extra_probe"] = extra_probe(model)
                    phase_metrics["extra_probe_seconds"] = time.perf_counter() - probe_started
            elif run_kind == "offline":
                probe_started = time.perf_counter()
                raw_payload, unified = transcribe(probe_audio_path)
                phase_metrics.update(
                    offline_probe_seconds=time.perf_counter() - probe_started,
                    network_guard="socket connections blocked",
                    local_model_load=True,
                )
            else:
                raise ValueError(f"Unsupported run kind: {run_kind}")
    finally:
        resources = monitor.stop()
    if unified is None:
        raise RuntimeError("Adapter completed without a unified result")
    metrics = {
        "candidate": candidate,
        "run_kind": run_kind,
        "model_name": model_name,
        "model_revision": model_revision,
        "runtime_version": runtime_version,
        "device": "cpu",
        "compute_type": compute_type,
        "load_seconds": load_seconds,
        "total_process_seconds": time.perf_counter() - started,
        "audio_duration_seconds": audio_duration if run_kind != "offline" else 30.0,
        "phases": phase_metrics,
        "resources": resources,
        "environment": environment_evidence(),
    }
    write_run_artifacts(
        destination,
        raw=raw_payload,
        unified=unified,
        metrics=metrics,
        audio_duration=audio_duration if run_kind != "offline" else 30.0,
    )

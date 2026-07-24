"""Sequential TASK-002 benchmark orchestrator with candidate failure isolation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from .common import atomic_write_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "asr-benchmark"
INPUT_ROOT = RUNTIME_ROOT / "input"
RESULT_ROOT = RUNTIME_ROOT / "results"
LOG_ROOT = PROJECT_ROOT / "runtime" / "logs" / "asr"


def _python(environment: str) -> Path:
    return PROJECT_ROOT / "runtime" / "asr-envs" / environment / "Scripts" / "python.exe"


def _candidate_command(candidate: str, run_kind: str) -> list[str]:
    common = [
        "--run-kind", run_kind,
        "--audio", str(INPUT_ROOT / "benchmark-16k-mono.wav"),
        "--probe-audio", str(INPUT_ROOT / "probe-30s.wav"),
        "--silence", str(INPUT_ROOT / "silence-20s.wav"),
        "--duration", "827.690688",
        "--output-dir", str(RESULT_ROOT / candidate / run_kind),
    ]
    if candidate == "sensevoice":
        model = PROJECT_ROOT / "模型" / "asr" / "sensevoice-small"
        return [
            str(_python("sherpa-onnx")), "-m", "experiments.asr.adapters.sensevoice",
            *common,
            "--model", str(model / "model.int8.onnx"),
            "--tokens", str(model / "tokens.txt"),
            "--vad", str(model / "silero_vad.onnx"),
        ]
    if candidate == "paraformer":
        root = PROJECT_ROOT / "模型" / "asr"
        return [
            str(_python("funasr")), "-m", "experiments.asr.adapters.paraformer",
            *common,
            "--model", str(root / "paraformer-zh"),
            "--vad-model", str(root / "fsmn-vad"),
            "--punc-model", str(root / "ct-punc"),
            "--hotwords", "直播 智能切片 人工智能 AI",
        ]
    if candidate == "faster-whisper":
        return [
            str(_python("faster-whisper")), "-m", "experiments.asr.adapters.faster_whisper",
            *common,
            "--model", str(PROJECT_ROOT / "模型" / "asr" / "faster-whisper-small"),
        ]
    raise ValueError(f"Unknown candidate: {candidate}")


def benchmark_environment() -> dict[str, str]:
    env = dict(os.environ)
    d_paths = {
        "PIP_CACHE_DIR": PROJECT_ROOT / "runtime" / "cache" / "asr" / "pip",
        "HF_HOME": PROJECT_ROOT / "runtime" / "cache" / "asr" / "hf",
        "HUGGINGFACE_HUB_CACHE": PROJECT_ROOT / "runtime" / "cache" / "asr" / "hf" / "hub",
        "MODELSCOPE_CACHE": PROJECT_ROOT / "runtime" / "cache" / "asr" / "modelscope",
        "TORCH_HOME": PROJECT_ROOT / "runtime" / "cache" / "asr" / "torch",
        "XDG_CACHE_HOME": PROJECT_ROOT / "runtime" / "cache" / "asr" / "xdg",
        "TEMP": PROJECT_ROOT / "runtime" / "temp" / "asr",
        "TMP": PROJECT_ROOT / "runtime" / "temp" / "asr",
    }
    for name, path in d_paths.items():
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path.resolve())
    env.update(
        OMP_NUM_THREADS="4",
        MKL_NUM_THREADS="4",
        OPENBLAS_NUM_THREADS="4",
        CUDA_VISIBLE_DEVICES="-1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        MODELSCOPE_OFFLINE="1",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        TOKENIZERS_PARALLELISM="false",
    )
    for secret_name in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AZURE_OPENAI_API_KEY",
        "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "MODELSCOPE_API_TOKEN"
    ):
        env.pop(secret_name, None)
    return env


def run_candidate(candidate: str, wait_seconds: int = 25) -> dict[str, Any]:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {"candidate": candidate, "runs": [], "success": True}
    for run_kind in ("cold", "warm", "offline"):
        if run_kind == "warm":
            time.sleep(wait_seconds)
        command = _candidate_command(candidate, run_kind)
        log_path = LOG_ROOT / f"{candidate}-{run_kind}.log"
        started = time.perf_counter()
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS
        with log_path.open("w", encoding="utf-8", newline="\n") as log:
            completed = subprocess.run(
                command, cwd=PROJECT_ROOT, env=benchmark_environment(),
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                shell=False, check=False, creationflags=creationflags
            )
        run_status = {
            "run_kind": run_kind,
            "returncode": completed.returncode,
            "elapsed_seconds": time.perf_counter() - started,
            "log": str(log_path.resolve()),
        }
        status["runs"].append(run_status)
        atomic_write_json(RESULT_ROOT / candidate / "status.json", status)
        if completed.returncode != 0:
            status["success"] = False
            status["failed_run"] = run_kind
            break
    atomic_write_json(RESULT_ROOT / candidate / "status.json", status)
    return status


def run_selected(
    candidates: Iterable[str],
    runner: Callable[[str], dict[str, Any]] = run_candidate,
) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            statuses.append(runner(candidate))
        except Exception as exc:
            statuses.append(
                {"candidate": candidate, "success": False, "orchestrator_error": str(exc)}
            )
    return statuses


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate", action="append",
        choices=("sensevoice", "paraformer", "faster-whisper"),
        help="Run one or more candidates; defaults to all in the fixed order."
    )
    parser.add_argument("--wait-seconds", type=int, default=25)
    args = parser.parse_args()
    if not 20 <= args.wait_seconds <= 30:
        raise ValueError("wait-seconds must be between 20 and 30")
    candidates = args.candidate or ["sensevoice", "paraformer", "faster-whisper"]
    statuses = run_selected(
        candidates, runner=lambda candidate: run_candidate(candidate, args.wait_seconds)
    )
    atomic_write_json(RESULT_ROOT / "benchmark-status.json", statuses)
    print(json.dumps(statuses, ensure_ascii=False, indent=2))
    if not all(item.get("success") for item in statuses):
        sys.exit(1)


if __name__ == "__main__":
    main()

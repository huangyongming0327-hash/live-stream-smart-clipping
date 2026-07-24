"""0.5-second process/system resource sampling for isolated ASR runs."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from .common import atomic_write_text


class ResourceMonitor:
    def __init__(self, output_path: str | Path, interval_seconds: float = 0.5) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.output_path = Path(output_path).resolve()
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = 0.0

    def start(self) -> None:
        import psutil

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        process = psutil.Process(os.getpid())
        if os.name == "nt":
            process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        process.cpu_percent(None)
        psutil.cpu_percent(None)
        self._started = time.perf_counter()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def _sample_loop(self) -> None:
        import psutil

        process = psutil.Process(os.getpid())
        while not self._stop.is_set():
            try:
                memory = psutil.virtual_memory()
                battery = psutil.sensors_battery()
                self.samples.append(
                    {
                        "elapsed_seconds": time.perf_counter() - self._started,
                        "process_cpu_percent": process.cpu_percent(None),
                        "system_cpu_percent": psutil.cpu_percent(None),
                        "process_rss_bytes": process.memory_info().rss,
                        "available_memory_bytes": memory.available,
                        "battery_percent": battery.percent if battery else None,
                        "power_plugged": battery.power_plugged if battery else None,
                    }
                )
            except (psutil.Error, OSError):
                pass
            self._stop.wait(self.interval_seconds)

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.interval_seconds * 4))
        atomic_write_text(
            self.output_path,
            "".join(
                json.dumps(sample, ensure_ascii=False, allow_nan=False) + "\n"
                for sample in self.samples
            ),
        )
        if not self.samples:
            return {
                "sample_interval_seconds": self.interval_seconds,
                "sample_count": 0,
                "elapsed_seconds": time.perf_counter() - self._started,
                "average_process_cpu_percent": None,
                "peak_process_cpu_percent": None,
                "average_system_cpu_percent": None,
                "peak_system_cpu_percent": None,
                "peak_rss_bytes": None,
                "minimum_available_memory_bytes": None,
                "power_state": None,
            }
        return {
            "sample_interval_seconds": self.interval_seconds,
            "sample_count": len(self.samples),
            "elapsed_seconds": time.perf_counter() - self._started,
            "average_process_cpu_percent": sum(s["process_cpu_percent"] for s in self.samples) / len(self.samples),
            "peak_process_cpu_percent": max(s["process_cpu_percent"] for s in self.samples),
            "average_system_cpu_percent": sum(s["system_cpu_percent"] for s in self.samples) / len(self.samples),
            "peak_system_cpu_percent": max(s["system_cpu_percent"] for s in self.samples),
            "peak_rss_bytes": max(s["process_rss_bytes"] for s in self.samples),
            "minimum_available_memory_bytes": min(s["available_memory_bytes"] for s in self.samples),
            "power_state": {
                "battery_percent": self.samples[-1]["battery_percent"],
                "power_plugged": self.samples[-1]["power_plugged"],
            },
        }

    def __enter__(self) -> "ResourceMonitor":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop()

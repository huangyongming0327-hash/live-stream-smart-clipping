"""Privacy-minimal, atomic pipeline status summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Mapping

from liveclip.asr.exporters import atomic_write_json


StageStatus = Literal["pending", "completed"]
STAGE_NAMES = ("transcribe", "analyze", "review")


def write_pipeline_status(
    workdir: str | Path,
    *,
    video_file_name: str,
    video_sha256: str,
    stages: Mapping[str, StageStatus],
) -> Path:
    """Atomically replace pipeline_status.json without paths or user content."""

    if set(stages) != set(STAGE_NAMES):
        raise ValueError("pipeline stages must be transcribe, analyze, and review")
    if any(value not in {"pending", "completed"} for value in stages.values()):
        raise ValueError("pipeline stage status must be pending or completed")
    if not video_file_name or Path(video_file_name).name != video_file_name:
        raise ValueError("video_file_name must be a file name")
    if len(video_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in video_sha256
    ):
        raise ValueError("video_sha256 must be lowercase SHA-256")

    destination = Path(workdir).expanduser().resolve() / "pipeline_status.json"
    payload = {
        "schema_version": "1.0",
        "source": {
            "video_file_name": video_file_name,
            "video_sha256": video_sha256,
        },
        "stages": {name: stages[name] for name in STAGE_NAMES},
        "artifacts": {
            "timeline_file_name": "timeline.json",
            "analysis_file_name": "current_analysis.json",
            "review_file_name": "review_current.json",
        },
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return atomic_write_json(destination, payload)

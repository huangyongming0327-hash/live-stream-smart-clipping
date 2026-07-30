"""UTF-8 timeline, SRT, TXT, and state writers."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

from liveclip.media.outputs import publish_without_overwrite

from .timeline import validate_timeline


FORMAL_OUTPUT_NAMES = ("timeline.json", "subtitles.srt", "transcript.txt")


def atomic_write_text(path: str | Path, text: str) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, target)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return target


def atomic_write_json(path: str | Path, value: Any) -> Path:
    return atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    )


def format_srt_timestamp(milliseconds: int) -> str:
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, int):
        raise ValueError("SRT timestamp must be an integer")
    if milliseconds < 0:
        raise ValueError("SRT timestamp must be non-negative")
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def render_srt(segments: list[dict[str, Any]]) -> str:
    blocks = [
        "\n".join(
            (
                str(index),
                f"{format_srt_timestamp(segment['start_ms'])} --> "
                f"{format_srt_timestamp(segment['end_ms'])}",
                segment["text"],
            )
        )
        for index, segment in enumerate(segments, 1)
    ]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _format_txt_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def render_transcript(segments: list[dict[str, Any]]) -> str:
    lines = [
        f"[{_format_txt_timestamp(segment['start_ms'])} - "
        f"{_format_txt_timestamp(segment['end_ms'])}] {segment['text']}"
        for segment in segments
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def publish_final_outputs(output_dir: Path, timeline: dict[str, Any]) -> dict[str, int]:
    validate_timeline(timeline)
    output_dir = output_dir.resolve()
    work_dir = output_dir / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    targets = {name: output_dir / name for name in FORMAL_OUTPUT_NAMES}
    existing = [str(path) for path in targets.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing completed output: " + ", ".join(existing)
        )

    published: list[Path] = []
    try:
        with TemporaryDirectory(prefix=".publish-", dir=work_dir) as temporary_name:
            staging = Path(temporary_name)
            staged = {
                "timeline.json": atomic_write_json(staging / "timeline.json", timeline),
                "subtitles.srt": atomic_write_text(
                    staging / "subtitles.srt", render_srt(timeline["segments"])
                ),
                "transcript.txt": atomic_write_text(
                    staging / "transcript.txt",
                    render_transcript(timeline["segments"]),
                ),
            }
            parsed = json.loads(staged["timeline.json"].read_text(encoding="utf-8"))
            validate_timeline(parsed)
            for name in ("subtitles.srt", "transcript.txt", "timeline.json"):
                publish_without_overwrite(staged[name], targets[name])
                published.append(targets[name])
    except Exception:
        for path in published:
            path.unlink(missing_ok=True)
        raise
    return {name: path.stat().st_size for name, path in targets.items()}


def cleanup_work_dir(work_dir: Path) -> None:
    if not work_dir.exists():
        return
    for path in work_dir.iterdir():
        is_chunk_wav = path.name.startswith("chunk-") and path.suffix == ".wav"
        is_chunk_partial = (
            path.name.startswith(".chunk-")
            and ".part" in path.name
            and path.suffix == ".wav"
        )
        if path.is_file() and (is_chunk_wav or is_chunk_partial):
            path.unlink(missing_ok=True)
    try:
        work_dir.rmdir()
    except OSError:
        pass

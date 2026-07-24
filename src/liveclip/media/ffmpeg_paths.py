"""Resolve project-local FFmpeg binaries without consulting PATH."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import MediaToolNotFoundError


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class FFmpegPaths:
    ffmpeg: Path
    ffprobe: Path


def _resolve_candidate(value: str | Path | None, default: Path, root: Path) -> Path:
    candidate = default if value is None else Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def resolve_ffmpeg_paths(
    ffmpeg_path: str | Path | None = None,
    ffprobe_path: str | Path | None = None,
    *,
    root: Path | None = None,
) -> FFmpegPaths:
    """Resolve explicit overrides or the fixed project-local binary locations."""

    root = (root or project_root()).resolve()
    bin_dir = root / "tools" / "ffmpeg" / "bin"
    paths = FFmpegPaths(
        ffmpeg=_resolve_candidate(ffmpeg_path, bin_dir / "ffmpeg.exe", root),
        ffprobe=_resolve_candidate(ffprobe_path, bin_dir / "ffprobe.exe", root),
    )
    missing = [str(path) for path in (paths.ffmpeg, paths.ffprobe) if not path.is_file()]
    if missing:
        joined = ", ".join(missing)
        raise MediaToolNotFoundError(
            f"Project-local FFmpeg executable is missing: {joined}. "
            "Run tools/Install-FFmpeg.ps1 or provide explicit paths."
        )
    return paths

"""Non-overwriting temporary output and atomic publication helpers."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from .errors import OutputExistsError


def prepare_output(output_path: str | Path) -> Path:
    output = Path(output_path).resolve()
    if output.exists():
        raise OutputExistsError(f"Refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def temporary_sibling(output: Path) -> Path:
    return output.with_name(f".{output.stem}.{uuid4().hex}.part{output.suffix}")


def publish_without_overwrite(temporary: Path, output: Path) -> None:
    """Atomically publish a sibling temporary file without replacing a target."""

    if output.exists():
        raise OutputExistsError(f"Refusing to overwrite existing output: {output}")
    try:
        if os.name == "nt":
            temporary.rename(output)
        else:
            os.link(temporary, output)
            temporary.unlink()
    except FileExistsError as exc:
        raise OutputExistsError(
            f"Refusing to overwrite output created concurrently: {output}"
        ) from exc


def discard_temporary(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        # Preserve the primary media error; stale partials are clearly named.
        pass

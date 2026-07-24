"""Reference parsing and deterministic Chinese/mixed-text normalization."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


_SRT_TIME = re.compile(
    r"^(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
    r"(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})(?:\s+.*)?$"
)
_MIXED_TOKEN = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*|[\u3400-\u4dbf\u4e00-\u9fff]")


@dataclass(frozen=True, slots=True)
class SrtCue:
    start: float
    end: float
    text: str


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def cer_units(text: str) -> list[str]:
    normalized = normalize_unicode(text)
    return [
        char for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith(("P", "S"))
    ]


def mixed_tokens(text: str) -> list[str]:
    return _MIXED_TOKEN.findall(normalize_unicode(text))


def _timestamp(parts: tuple[str, str, str, str]) -> float:
    hours, minutes, seconds, milliseconds = (int(value) for value in parts)
    if minutes >= 60 or seconds >= 60:
        raise ValueError("invalid SRT timestamp")
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def parse_srt(text: str) -> list[SrtCue]:
    normalized = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return []
    cues: list[SrtCue] = []
    for block in re.split(r"\n[ \t]*\n", normalized.strip()):
        lines = block.split("\n")
        if len(lines) < 3:
            raise ValueError("malformed SRT cue")
        try:
            int(lines[0].strip())
        except ValueError as exc:
            raise ValueError("invalid SRT cue index") from exc
        match = _SRT_TIME.fullmatch(lines[1].strip())
        if not match:
            raise ValueError("invalid SRT time range")
        start = _timestamp(match.groups()[:4])
        end = _timestamp(match.groups()[4:])
        if end <= start:
            raise ValueError("SRT cue must end after it starts")
        cues.append(SrtCue(start=start, end=end, text="\n".join(lines[2:])))
    return cues

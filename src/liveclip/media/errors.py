"""Structured media-layer exceptions."""

from __future__ import annotations

from dataclasses import dataclass


class MediaError(Exception):
    """Base class for recoverable media-service failures."""


class MediaFileNotFoundError(MediaError):
    """Raised when an input media or subtitle file is missing."""


class MediaToolNotFoundError(MediaError):
    """Raised when a configured FFmpeg executable is missing."""


class OutputExistsError(MediaError):
    """Raised when an operation would overwrite an existing output."""


class ProbeError(MediaError):
    """Raised when ffprobe data is unavailable or malformed."""


class NoAudioStreamError(ProbeError):
    """Raised when an operation requires an audio stream but none exists."""


class SubtitleError(MediaError):
    """Raised when an SRT document is malformed or cannot be processed."""


@dataclass(frozen=True, slots=True)
class DecodedProcessOutput:
    """Decoded child-process output plus auditable decoding metadata."""

    raw_byte_length: int
    text: str
    encoding_used: str
    replacement_occurred: bool


@dataclass(frozen=True, slots=True)
class ProcessFailure:
    """Machine-readable details for a failed child process."""

    command: tuple[str, ...]
    returncode: int | None
    stdout_details: DecodedProcessOutput
    stderr_details: DecodedProcessOutput
    timed_out: bool
    timeout_seconds: float | None

    @property
    def stdout(self) -> str:
        return self.stdout_details.text

    @property
    def stderr(self) -> str:
        return self.stderr_details.text


class ProcessExecutionError(MediaError):
    """Raised for a timeout, launch failure, or non-zero process exit."""

    def __init__(self, message: str, failure: ProcessFailure) -> None:
        super().__init__(message)
        self.failure = failure

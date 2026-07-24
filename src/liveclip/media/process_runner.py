"""Safe subprocess execution for FFmpeg-family tools."""

from __future__ import annotations

import os
import locale
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .errors import DecodedProcessOutput, ProcessExecutionError, ProcessFailure


@dataclass(frozen=True, slots=True)
class ProcessResult:
    command: tuple[str, ...]
    returncode: int
    stdout_details: DecodedProcessOutput
    stderr_details: DecodedProcessOutput
    elapsed_seconds: float

    @property
    def stdout(self) -> str:
        return self.stdout_details.text

    @property
    def stderr(self) -> str:
        return self.stderr_details.text


def _windows_ansi_encoding() -> str:
    """Return the current Windows ANSI code page without consulting the shell."""

    if os.name == "nt":
        try:
            import ctypes

            code_page = int(ctypes.windll.kernel32.GetACP())
            if code_page > 0:
                return f"cp{code_page}"
        except (AttributeError, OSError, TypeError, ValueError):
            pass
    encoding = locale.getencoding()
    return encoding if encoding else "cp936"


def decode_process_output(
    value: bytes | str | None,
    *,
    ansi_encoding: str | None = None,
) -> DecodedProcessOutput:
    """Decode captured bytes without losing the whole result on invalid data."""

    if value is None:
        return DecodedProcessOutput(0, "", "none", False)
    if isinstance(value, str):
        return DecodedProcessOutput(
            len(value.encode("utf-8", errors="replace")),
            value,
            "already-decoded",
            "\ufffd" in value,
        )

    raw_length = len(value)
    try:
        utf8_text = value.decode("utf-8", errors="strict")
        if value.startswith(b"\xef\xbb\xbf"):
            return DecodedProcessOutput(
                raw_length,
                value.decode("utf-8-sig", errors="strict"),
                "utf-8-sig",
                False,
            )
        return DecodedProcessOutput(raw_length, utf8_text, "utf-8", False)
    except UnicodeDecodeError:
        pass

    ansi = ansi_encoding or _windows_ansi_encoding()
    try:
        return DecodedProcessOutput(
            raw_length,
            value.decode(ansi, errors="strict"),
            ansi.lower(),
            False,
        )
    except (LookupError, UnicodeDecodeError):
        safe_encoding = ansi if _encoding_exists(ansi) else "utf-8"
        text = value.decode(safe_encoding, errors="replace")
        return DecodedProcessOutput(
            raw_length,
            text,
            f"{safe_encoding.lower()}-replace",
            True,
        )


def _encoding_exists(encoding: str) -> bool:
    try:
        "".encode(encoding)
    except LookupError:
        return False
    return True


def run_process(
    executable: str | Path,
    arguments: Sequence[str | Path],
    *,
    timeout_seconds: float = 60.0,
) -> ProcessResult:
    """Run an executable with an argument list; never invokes a shell."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    command = (str(executable), *(str(argument) for argument in arguments))
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
            timeout=timeout_seconds,
            creationflags=creation_flags,
        )
    except subprocess.TimeoutExpired as exc:
        failure = ProcessFailure(
            command=command,
            returncode=None,
            stdout_details=decode_process_output(exc.stdout),
            stderr_details=decode_process_output(exc.stderr),
            timed_out=True,
            timeout_seconds=timeout_seconds,
        )
        raise ProcessExecutionError(
            f"Process timed out after {timeout_seconds:.3f} seconds.", failure
        ) from exc
    except OSError as exc:
        failure = ProcessFailure(
            command=command,
            returncode=None,
            stdout_details=decode_process_output(None),
            stderr_details=decode_process_output(str(exc)),
            timed_out=False,
            timeout_seconds=timeout_seconds,
        )
        raise ProcessExecutionError("Process could not be started.", failure) from exc

    stdout_details = decode_process_output(completed.stdout)
    stderr_details = decode_process_output(completed.stderr)
    result = ProcessResult(
        command=command,
        returncode=completed.returncode,
        stdout_details=stdout_details,
        stderr_details=stderr_details,
        elapsed_seconds=time.perf_counter() - started,
    )
    if completed.returncode != 0:
        failure = ProcessFailure(
            command=command,
            returncode=completed.returncode,
            stdout_details=stdout_details,
            stderr_details=stderr_details,
            timed_out=False,
            timeout_seconds=timeout_seconds,
        )
        raise ProcessExecutionError(
            f"Process exited with code {completed.returncode}.", failure
        )
    return result

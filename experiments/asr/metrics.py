"""Accuracy metrics with an explicit human-reference requirement."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from .normalize import cer_units, mixed_tokens


class ReferenceRequiredError(ValueError):
    """Raised when an accuracy claim is attempted without a human reference."""


@dataclass(frozen=True, slots=True)
class ErrorRate:
    errors: int
    reference_units: int
    substitutions: int
    deletions: int
    insertions: int

    @property
    def rate(self) -> float | None:
        return self.errors / self.reference_units if self.reference_units else None

    def as_dict(self) -> dict[str, int | float | None]:
        value = asdict(self)
        value["rate"] = self.rate
        return value


def edit_counts(reference: Sequence[str], hypothesis: Sequence[str]) -> ErrorRate:
    rows: list[list[tuple[int, int, int, int]]] = [
        [(j, 0, 0, j) for j in range(len(hypothesis) + 1)]
    ]
    for i in range(1, len(reference) + 1):
        row: list[tuple[int, int, int, int]] = [(i, 0, i, 0)]
        previous = rows[i - 1]
        for j in range(1, len(hypothesis) + 1):
            if reference[i - 1] == hypothesis[j - 1]:
                row.append(previous[j - 1])
                continue
            substitution = previous[j - 1]
            deletion = previous[j]
            insertion = row[j - 1]
            candidates = (
                (substitution[0] + 1, substitution[1] + 1, substitution[2], substitution[3]),
                (deletion[0] + 1, deletion[1], deletion[2] + 1, deletion[3]),
                (insertion[0] + 1, insertion[1], insertion[2], insertion[3] + 1),
            )
            row.append(min(candidates, key=lambda item: (item[0], item[3], item[2], item[1])))
        rows.append(row)
    errors, substitutions, deletions, insertions = rows[-1][-1]
    return ErrorRate(errors, len(reference), substitutions, deletions, insertions)


def character_error_rate(reference: str, hypothesis: str) -> ErrorRate:
    return edit_counts(cer_units(reference), cer_units(hypothesis))


def mixed_word_error_rate(reference: str, hypothesis: str) -> ErrorRate:
    return edit_counts(mixed_tokens(reference), mixed_tokens(hypothesis))


def compute_accuracy(reference: str | None, hypothesis: str) -> dict[str, object]:
    if reference is None:
        raise ReferenceRequiredError("A human reference is required for CER/WER")
    return {
        "cer": character_error_rate(reference, hypothesis).as_dict(),
        "mixed_token_wer": mixed_word_error_rate(reference, hypothesis).as_dict(),
    }

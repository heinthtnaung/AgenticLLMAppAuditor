"""Data model for a source file the scan could not analyse.

Recorded in surfaces.json beside the surfaces, never in a file of its own:
"these are all the surfaces" and "except in these files" have to travel
together, or a later phase scores recall against a partial scan and reads it
as a complete one.
"""

from dataclasses import dataclass

from artifacts.repo_path import is_repo_relative_posix

# Why a file the scan would otherwise have read was left out of it.
UNPARSEABLE_SYNTAX = "unparseable_syntax"
UNDECODABLE_BYTES = "undecodable_bytes"
TOO_LARGE = "too_large"

SKIP_REASONS = (UNPARSEABLE_SYNTAX, UNDECODABLE_BYTES, TOO_LARGE)


def _check_reason(reason: str) -> None:
    """Reject a reason outside the recorded vocabulary, wherever it came from."""
    if reason not in SKIP_REASONS:
        raise ValueError(f"unknown skip reason {reason!r}; expected one of {SKIP_REASONS}")


class UnreadableSource(Exception):
    """Raised by a language backend when one file cannot be analysed.

    Carries the reason, so the repository walk records why without matching on
    the interpreter's message — whose wording changes between Python versions
    and can contain an absolute path.
    """

    def __init__(self, message: str, reason: str, line: int | None = None) -> None:
        _check_reason(reason)
        super().__init__(message)
        self.reason = reason
        # Normalised, not rejected: this end takes whatever a third-party parser
        # reports, and a quirk in one file must not abort the whole scan. The
        # record below is the artifact contract, so there a bad line is an error.
        self.line = line if line and line >= 1 else None


@dataclass(frozen=True)
class SkippedFile:
    """One file left out of the scan: which file, why, and where the parser gave up.

    `line` is descriptive only, like a surface's `detail`: the interpreter moves
    reported lines between versions, so nothing may join on it.
    """

    file: str
    reason: str
    line: int | None = None

    def __post_init__(self) -> None:
        """Reject a record a later phase could not act on."""
        _check_reason(self.reason)
        if not self.file:
            raise ValueError("skipped file must not be empty")
        if not is_repo_relative_posix(self.file):
            raise ValueError(f"skipped file must be a repo-relative posix path, got {self.file!r}")
        if self.line is not None and self.line < 1:
            raise ValueError(f"skipped file line must be 1 or greater, got {self.line}")


def sort_key(skipped: SkippedFile) -> tuple[str, str]:
    """Order skipped files so the same repository always produces the same output."""
    return (skipped.file, skipped.reason)

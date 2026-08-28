"""The one path rule both artifact records share: repo-relative, POSIX, no drive.

`Surface` and `SkippedFile` each reject a bad path through their own message, and
their tests cover that. This file tests the rule itself, because it is the shared
contract underneath both -- a Windows path or an absolute one in an artifact makes
the artifact describe the machine that produced it rather than the repository.
"""

import pytest

from artifacts.repo_path import is_repo_relative_posix

# Paths an artifact may carry: relative, forward slashes, no drive letter.
ACCEPTED_PATHS = [
    "main.py",
    "app/agents/support.py",
    "src/index.ts",
    "app/notes:draft.py",
]

# Paths that would tie the artifact to one machine or one operating system.
REJECTED_PATHS = [
    "/home/someone/app/main.py",
    "app\\agents\\support.py",
    "C:/Users/someone/app/main.py",
    "C:\\Users\\someone\\app\\main.py",
]


@pytest.mark.parametrize("file", ACCEPTED_PATHS)
def test_a_repo_relative_posix_path_is_accepted(file: str) -> None:
    """A path below the repository root, spelled with forward slashes, is what artifacts hold."""
    assert is_repo_relative_posix(file) is True


@pytest.mark.parametrize("file", REJECTED_PATHS)
def test_an_absolute_or_windows_path_is_rejected(file: str) -> None:
    """Absolute paths, backslashes and drive letters all describe one machine, not the repo."""
    assert is_repo_relative_posix(file) is False


def test_only_the_first_segment_is_searched_for_a_drive_letter() -> None:
    """A drive can only be the first segment, so a colon deeper in the path is just a name."""
    assert is_repo_relative_posix("app/notes:draft.py") is True
    assert is_repo_relative_posix("C:/app/main.py") is False


def test_a_colon_in_a_filename_is_not_a_drive_letter() -> None:
    """A colon in a file at the repository root is a filename, not a drive."""
    assert is_repo_relative_posix("notes:draft.py") is True


def test_an_empty_path_passes_the_rule_and_is_refused_elsewhere() -> None:
    """The rule answers one question only; the records reject an empty file before asking it."""
    assert is_repo_relative_posix("") is True

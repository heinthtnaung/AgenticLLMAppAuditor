"""Chooses the right language backend for each file and walks a whole repository."""

from dataclasses import dataclass
from pathlib import Path

from parsing import extractor_js
from parsing import extractor_python
from parsing.languages import PYTHON, language_of
from parsing.repo_loader import list_oversized_files, list_source_files
from artifacts.skipped_file import TOO_LARGE, SkippedFile, UnreadableSource, sort_key
from artifacts.surface import Surface


@dataclass(frozen=True)
class ScanResult:
    """What one walk produced: the surfaces found, and the files that could not be read.

    The two travel together deliberately. A caller holding only the surfaces
    could not tell a repository with no surfaces from one the scan failed on.
    """

    surfaces: list[Surface]
    skipped: list[SkippedFile]


def extract_file(path: Path, file_label: str) -> list[Surface]:
    """Run the detectors for whichever language this file is written in."""
    if language_of(file_label) == PYTHON:
        return extractor_python.extract_file(path, file_label)
    return extractor_js.extract_file(path, file_label)


def _oversized_skips(repo_path: str, root: Path) -> list[SkippedFile]:
    """Record the files left out for size, so they are reported the same way as parse failures."""
    return [
        SkippedFile(path.relative_to(root).as_posix(), TOO_LARGE)
        for path in list_oversized_files(repo_path)
    ]


def extract_repo(repo_path: str) -> ScanResult:
    """Run the detectors over the repository, recording any file that could not be read.

    One unparseable vendored file must not cost the whole scan, so a failure is
    recorded against that file and the walk continues. Only UnreadableSource is
    caught: a detector's own ValueError is a bug and must still be loud.
    """
    root = Path(repo_path)
    found: list[Surface] = []
    skipped = _oversized_skips(repo_path, root)
    for path in list_source_files(repo_path):
        label = path.relative_to(root).as_posix()
        try:
            found.extend(extract_file(path, label))
        except UnreadableSource as error:
            skipped.append(SkippedFile(label, error.reason, error.line))
    # Sorted here, not only in the serialiser, so the warnings printed and the
    # records written come out in the same order.
    return ScanResult(found, sorted(skipped, key=sort_key))

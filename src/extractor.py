"""Chooses the right language backend for each file and walks a whole repository."""

from pathlib import Path

import extractor_js
import extractor_python
from languages import PYTHON, language_of
from repo_loader import list_source_files
from surface import Surface


def extract_file(path: Path, file_label: str) -> list[Surface]:
    """Run the detectors for whichever language this file is written in."""
    if language_of(file_label) == PYTHON:
        return extractor_python.extract_file(path, file_label)
    return extractor_js.extract_file(path, file_label)


def extract_repo(repo_path: str) -> list[Surface]:
    """Run the detectors over every readable source file in the repository."""
    root = Path(repo_path)
    found = []
    for path in list_source_files(repo_path):
        found.extend(extract_file(path, path.relative_to(root).as_posix()))
    return found

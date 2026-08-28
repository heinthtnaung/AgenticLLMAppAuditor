"""Reads a Python requirements file: what the app says it depends on.

Kept separate from the SBOM generator because the two answer different
questions. The generator says what it could find; the manifest says what the
app claims. Where they disagree is itself evidence.
"""

import re
from pathlib import Path

from deps.package_names import PYPI, normalise_name

MANIFEST_NAME = "requirements.txt"

# name, then an optional constraint. Enough for a requirements file; a full
# PEP 508 parser is not needed and would be harder to read.
REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<constraint>.*)$")

# Lines that declare no package: comments, blanks, and pip's own options.
SKIP_PREFIXES = ("#", "-", "http://", "https://", "git+")


def parse_line(line: str) -> tuple[str, str] | None:
    """Return (normalised name, constraint) for one line, or None if it declares nothing."""
    text = line.split("#", 1)[0].strip()
    if not text or text.startswith(SKIP_PREFIXES):
        return None
    match = REQUIREMENT.match(text)
    if match is None:
        return None
    constraint = match.group("constraint").split(";", 1)[0].strip()
    return normalise_name(match.group("name"), PYPI), constraint


def read_requirements(app_dir: Path) -> dict[str, str]:
    """Map each declared package to its constraint text, empty when unconstrained."""
    manifest = app_dir / MANIFEST_NAME
    if not manifest.is_file():
        return {}
    declared = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        parsed = parse_line(line)
        if parsed is not None:
            declared[parsed[0]] = parsed[1]
    return declared


def manifests_present(app_dir: Path) -> list[str]:
    """Return the dependency manifests that actually exist, so the SBOM can say what it read."""
    return [MANIFEST_NAME] if (app_dir / MANIFEST_NAME).is_file() else []


"""Baseline A: match the rules in `rules.py` over raw source text.

Reads text, nothing else. It never parses, never resolves an import, and never
opens an artifact this project produced -- if it did, it would be measuring the
auditor rather than standing beside it.

Its `surfaces.json` is derived from its own findings, not from an inventory:
what a grep tool knows about a repository is exactly what it matched. Writing
`surface_count: 0` beside findings that name surfaces would make the two files
contradict each other.
"""

from pathlib import Path

from artifacts.finding import STATIC, Finding
from artifacts.skipped_file import TOO_LARGE, UNDECODABLE_BYTES, SkippedFile, sort_key
from artifacts.surface import Surface
from baselines.rules import RULES, Rule, surface_name
from parsing.languages import language_of
from parsing.repo_loader import list_oversized_files, list_source_files

CHECK_NAMES = tuple(rule.rule_id for rule in RULES)


def _read_lines(path: Path) -> list[str] | None:
    """Read one file as text, or None when it is not readable text.

    None rather than an empty list, so the caller can record the skip. A file
    silently dropped would leave a miss inside it attributed to the rules
    staying silent, when the truth is the rules never saw it -- an error in this
    system's own favour, which is the direction a baseline must not be wrong in.
    """
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return None


def _finding_for(rule: Rule, name: str, file: str, line: int) -> Finding:
    """Build one finding, carrying the surface tuple the match named."""
    return Finding(
        owasp_id=rule.owasp_id, rule_id=rule.rule_id, title=rule.title,
        detection=STATIC,
        surface_id=f"{file}:{line}:{rule.surface_kind}:{name}",
        surface_kind=rule.surface_kind, surface_name=name, file=file, line=line,
    )


def scan_file(path: Path, file_label: str) -> list[Finding]:
    """Run every rule over one file's text and report what matched."""
    lines = _read_lines(path) or []
    found = []
    for index, line in enumerate(lines):
        found.extend(_matches_on_line(line, lines[index + 1:], file_label, index + 1))
    return found


def _matches_on_line(line: str, following: list[str], file: str, number: int) -> list[Finding]:
    """Report every rule that matches one line, so the loop above stays flat."""
    found = []
    for rule in RULES:
        match = rule.pattern.search(line)
        if match:
            found.append(_finding_for(rule, surface_name(rule, match, following), file, number))
    return found


def scan_repo(repo_path: str) -> list[Finding]:
    """Match every rule over every source file, deduplicating on the finding id."""
    root = Path(repo_path).resolve()
    reported: dict[str, Finding] = {}
    for path in list_source_files(repo_path):
        for finding in scan_file(path, path.resolve().relative_to(root).as_posix()):
            reported.setdefault(finding.id, finding)
    return sorted(reported.values(), key=lambda finding: finding.id)


def unreadable_files(repo_path: str) -> list[SkippedFile]:
    """Say which files this baseline could not read, so a miss inside one is not laid at the rules.

    The auditor records the same thing, and for the same reason: a file dropped
    without a word turns "the rules never saw it" into "the rules stayed
    silent", which is an error in this system's own favour.
    """
    root = Path(repo_path).resolve()
    skipped = [
        SkippedFile(path.resolve().relative_to(root).as_posix(), TOO_LARGE)
        for path in list_oversized_files(repo_path)
    ]
    skipped += [
        SkippedFile(path.resolve().relative_to(root).as_posix(), UNDECODABLE_BYTES)
        for path in list_source_files(repo_path) if _read_lines(path) is None
    ]
    return sorted(skipped, key=sort_key)


def surfaces_from(findings: list[Finding]) -> list[Surface]:
    """Derive the surfaces list from what the findings named, never by inventorying."""
    seen: dict[str, Surface] = {}
    for finding in findings:
        language = language_of(finding.file)
        seen.setdefault(finding.surface_id, Surface(
            kind=finding.surface_kind, name=finding.surface_name, file=finding.file,
            line=finding.line, language=language,
            detail=f"matched by {finding.rule_id}",
        ))
    return sorted(seen.values(), key=lambda surface: (surface.file, surface.line, surface.name))

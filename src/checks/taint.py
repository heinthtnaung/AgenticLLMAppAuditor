"""Traces an untrusted value from where it enters to where a model consumes it.

Within one file, deliberately. Following a value across modules is an unbounded
problem, and a trace that leaves what the syntax tree can prove is reported as
inconclusive rather than dropped -- "we could not follow it" and "nothing
reaches the model" are different answers.
"""

import ast
from pathlib import Path

from artifacts.finding import INCONCLUSIVE, STATIC, SURFACE_SUBJECT, Finding, Probe
from artifacts.surface import AGENT_DEF, DATA_SOURCE, TOOL_CALL
from artifacts.skipped_file import UnreadableSource
from parsing.bindings import argument_names, call_bindings, called_name
from parsing.extractor_python import parse_file
from parsing.languages import PYTHON, language_of
from parsing.repo_loader import list_source_files

CHECK_NAME = "untrusted_input_reaches_model"

# LLM01 in the 2025 OWASP list: prompt injection, direct and indirect.
OWASP_ID = "LLM01"

TITLE = "Untrusted input reaches the model without validation"

# Reaching one of these means the model, or a tool the model drives, consumes
# a value the app never checked.
SINK_KINDS = (AGENT_DEF, TOOL_CALL)

# Why a trace stopped, from `finding`'s vocabulary so every check reads alike.
LEFT_THE_FILE = "trace_left_static_analysis"


def _surfaces_by_line(surfaces: list, file: str, kinds: tuple) -> dict:
    """Index one file's surfaces of the given kinds by the line they sit on."""
    return {s.line: s for s in surfaces if s.file == file and s.kind in kinds}


def _finding_for(source) -> Finding:
    """Build the finding, anchored on the source: that is where a grading key records it."""
    return Finding(
        OWASP_ID, CHECK_NAME, TITLE, STATIC,
        surface_id=source.id, surface_kind=source.kind, surface_name=source.name,
        file=source.file, line=source.line,
    )


def _unfollowed(sources: dict, tainted: dict) -> list[Probe]:
    """Record every source this file never bound to a name.

    Not a finding and not a clean bill: the value may reach a model somewhere
    the syntax tree cannot show, so the gap is stated rather than dropped.
    """
    followed = {surface.id for surface in tainted.values()}
    return [
        Probe(CHECK_NAME, SURFACE_SUBJECT, surface.id, INCONCLUSIVE,
              "the value was not bound to a name in this file", LEFT_THE_FILE)
        for surface in sources.values() if surface.id not in followed
    ]


def trace_file(tree: ast.AST, file: str, surfaces: list) -> tuple[list[Finding], list[Probe]]:
    """Report each untrusted value this file hands to a model or a model-driven tool."""
    sources = _surfaces_by_line(surfaces, file, (DATA_SOURCE,))
    sinks = _surfaces_by_line(surfaces, file, SINK_KINDS)
    bindings = call_bindings(tree)
    tainted = {n: sources[b.line] for n, b in bindings.items() if b.line in sources}
    reached = {n: sinks[b.line] for n, b in bindings.items() if b.line in sinks}

    # One untrusted value is one finding however many sinks it reaches: the
    # finding is anchored on the source, so reporting per sink would emit the
    # same id twice and the document would refuse it as a duplicate.
    reported: dict[str, Finding] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or called_name(node) not in reached:
            continue
        for name in sorted(argument_names(node) & set(tainted)):
            finding = _finding_for(tainted[name])
            reported.setdefault(finding.id, finding)
    return list(reported.values()), _unfollowed(sources, tainted)


def python_files(repo_path: str) -> list[Path]:
    """Return the repository's Python files, the only ones the trace can read."""
    root = Path(repo_path)
    return [p for p in list_source_files(repo_path)
            if language_of(p.relative_to(root).as_posix()) == PYTHON]


def run_over_repo(repo_path: str, surfaces: list[Surface]) -> tuple[list[Finding], list[Probe]]:
    """Trace untrusted values within each Python file.

    Python only: the trace reads an `ast` tree, and the JavaScript side would
    need the same analysis rebuilt on tree-sitter. Recorded rather than implied,
    so a JS app's clean result is not read as a traced one.
    """
    root = Path(repo_path)
    findings: list[Finding] = []
    probes: list[Probe] = []
    for path in python_files(repo_path):
        label = path.relative_to(root).as_posix()
        try:
            tree = parse_file(path)
        except UnreadableSource:
            # Already recorded in surfaces.json's skipped_files, and one
            # unreadable file must not cost the audit -- the guarantee Phase 1
            # makes and this check must not quietly take back.
            continue
        traced, unfollowed = trace_file(tree, label, surfaces)
        findings += traced
        probes += unfollowed
    return findings, probes



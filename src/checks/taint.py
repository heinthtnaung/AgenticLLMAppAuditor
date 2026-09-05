"""Traces an untrusted value from where it enters to where a model consumes it.

Within one file, deliberately. Following a value across modules is an unbounded
problem.

**What is and is not reported when the trace gives up**, because "we could not
follow it" and "nothing reaches the model" are different answers. Two cases are
said out loud, as an `INCONCLUSIVE` probe: a source this file never bound to a
name, and a value handed to a method on a model or tool that this check does
not recognise.

Two are still silent, each held by a strict xfail in
`tests/checks/test_taint_defect.py` so neither can be quietly forgotten: a
receiver that is not a local name (`a.b.invoke(x)`), and a value passed inside
a container (`agent.invoke({"input": x})`). Neither should be read as a clean
result.
"""

import ast
from pathlib import Path

from artifacts.finding import INCONCLUSIVE, STATIC, SURFACE_SUBJECT, Finding, Probe
from artifacts.surface import AGENT_DEF, DATA_SOURCE, TOOL_CALL, Surface
from artifacts.skipped_file import UnreadableSource
from parsing.bindings import (
    argument_names, method_name, receiver_name, scoped_call_bindings)
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

# A method on a surface-bound object either hands the value to the model,
# configures the object, or is one this check does not know. Filing the third
# as configuration is how a closed list turns into silence, so it becomes a
# probe: loud, and never a false finding. A bare `agent(x)` consumes.
# Splitting these apart was forced by a false positive -- see `docs/TODO.md`.
CONSUMING_METHODS = frozenset({
    "invoke", "ainvoke", "run", "arun", "call", "acall",
    "predict", "apredict", "predict_messages", "apredict_messages",
    "generate", "agenerate", "stream", "astream", "astream_events",
    "batch", "abatch",
})

# Methods that set an object up rather than run it. Known, so they are silent
# without a probe: there is nothing inconclusive about `llm.bind(key)`.
#
# A name *missing* from this list is safe -- it falls through to a probe. A name
# wrongly *present* is not: it is silent, and no test can tell it from a correct
# entry. That is the one direction this design still fails silently in, so every
# addition is a decision that the method never forwards its argument to the
# model. `bind` is the entry to watch: it binds kwargs that are forwarded at
# invocation time, so `llm.bind(api_key=key)` is not a consumption while
# `llm.bind(extra_body=untrusted)` arguably is.
CONFIGURING_METHODS = frozenset({
    "bind", "bind_tools", "with_config", "with_retry", "with_fallbacks",
    "with_structured_output", "with_types", "configurable_fields",
    "configurable_alternatives", "add_node", "add_edge", "add_conditional_edges",
    "set_entry_point", "set_finish_point", "compile",
})

# What `_verdict` answers. Named rather than compared as strings twice.
CONSUMES = "consumes"
CONFIGURES = "configures"
UNKNOWN_METHOD = "unknown_method"


def _surfaces_by_line(surfaces: list, file: str, kinds: tuple) -> dict:
    """Index one file's surfaces of the given kinds by the line they sit on."""
    return {s.line: s for s in surfaces if s.file == file and s.kind in kinds}


def _finding_for(source: Surface) -> Finding:
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


def _calls_in(body: list[ast.stmt]) -> list[ast.Call]:
    """Every call written inside one scope's own statements, and no other scope's."""
    return [node for statement in body
            for node in ast.walk(statement) if isinstance(node, ast.Call)]


def _verdict(method: str) -> str:
    """Say whether this call consumes its arguments, configures the object, or is unknown."""
    if not method or method in CONSUMING_METHODS:
        return CONSUMES
    return CONFIGURES if method in CONFIGURING_METHODS else UNKNOWN_METHOD


def _unknown_method_probe(source: Surface, method: str) -> Probe:
    """Say the trace could not tell whether one method consumes the value it was given."""
    return Probe(
        CHECK_NAME, SURFACE_SUBJECT, source.id, INCONCLUSIVE,
        f"the value reaches {method!r} on a model or tool, and this check does "
        "not know whether that method consumes it",
        LEFT_THE_FILE)


def _judgements_in_scope(body: list[ast.stmt], tainted: dict,
                         reached: dict) -> tuple[list[Finding], list[Probe]]:
    """Report each untrusted name handed to a sink, and each one this check cannot judge.

    Both maps and the code are one scope's, so a source in one function can
    never be matched to a sink in another that reuses the name.
    """
    found: list[Finding] = []
    unsure: list[Probe] = []
    for call in _calls_in(body):
        if receiver_name(call) not in reached:
            continue
        passed = sorted(argument_names(call) & set(tainted))
        method = method_name(call)
        verdict = _verdict(method)
        if verdict == CONSUMES:
            found += [_finding_for(tainted[name]) for name in passed]
        elif verdict == UNKNOWN_METHOD:
            unsure += [_unknown_method_probe(tainted[name], method) for name in passed]
    return found, unsure


def trace_file(tree: ast.AST, file: str, surfaces: list) -> tuple[list[Finding], list[Probe]]:
    """Report each untrusted value this file hands to a model or a model-driven tool."""
    sources = _surfaces_by_line(surfaces, file, (DATA_SOURCE,))
    sinks = _surfaces_by_line(surfaces, file, SINK_KINDS)

    # One untrusted value is one finding however many sinks it reaches: the
    # finding is anchored on the source, so reporting per sink would emit the
    # same id twice and the document would refuse it as a duplicate.
    reported: dict[str, Finding] = {}
    tainted_anywhere: dict[str, Surface] = {}
    unsure_probes: dict[str, Probe] = {}
    for scope in scoped_call_bindings(tree):
        tainted = {n: sources[b.line] for n, b in scope.bindings.items() if b.line in sources}
        reached = {n: sinks[b.line] for n, b in scope.bindings.items() if b.line in sinks}
        tainted_anywhere.update(tainted)
        found, unsure = _judgements_in_scope(scope.body, tainted, reached)
        for finding in found:
            reported.setdefault(finding.id, finding)
        for probe in unsure:
            # One probe per source, because two probes on one subject would
            # share a probe_id. A source reaching several unjudgeable methods
            # keeps the one met first: `_calls_in` takes the scope's
            # statements in source order and only then walks inside each, so
            # nesting decides only between calls sharing one statement. The
            # detail therefore names *an* example, not every method reached.
            unsure_probes.setdefault(probe.subject_id, probe)
    # A source reported as a finding is followed, so it needs no probe beside it.
    reported_sources = {finding.surface_id for finding in reported.values()}
    remaining = [probe for subject, probe in unsure_probes.items()
                 if subject not in reported_sources]
    return list(reported.values()), _unfollowed(sources, tainted_anywhere) + remaining


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

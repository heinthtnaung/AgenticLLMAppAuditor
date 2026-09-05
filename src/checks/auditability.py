"""Reports an agent constructed with no callback or handler argument.

**What this establishes, and what it does not.** It establishes one structural
fact about the construction site: no `callbacks=` (or `callback_manager=`)
argument was passed where the agent was built. It does **not** establish that
the agent's actions go unrecorded, and the title says so.

Two measured cases show why that distinction is not pedantry. In
`damn-vulnerable-llm-agent`, `callbacks=[st_cb]` is passed at *invocation*
(`main.py:82`), not at construction -- and the handler is a Streamlit *display*
widget, which a static check cannot tell from an audit sink. Move that kwarg
into the constructor, a refactor with identical runtime behaviour, and this
check goes silent. In `RAG-Examples-with-Langchain`, `main.py` imports `logging`
and calls `logger.info` roughly thirty times, yet passes no `callbacks=`
anywhere: this check reports all three of its agents. That is a false positive
in the plain sense, accepted deliberately, because the alternative -- a registry
of blessed handler class names -- is the LangSmith name-matching this project
already rejected.

So read a finding here as "nothing was attached where the agent was built", and
decide for yourself. `owasp_id` is `AUDITABILITY` because the risk class is
right; only the strength of the evidence must not be overstated.
"""

import ast
from pathlib import Path

from artifacts.finding import STATIC, Finding
from artifacts.skipped_file import UnreadableSource
from artifacts.surface import AGENT_DEF, Surface
from checks.taint import python_files
from detectors.detector_names import AGENT_FACTORIES
from parsing.ast_utils import call_name
from parsing.languages import PYTHON
from parsing.extractor_python import parse_file

CHECK_NAME = "agent_defined_without_callback_handler"

# Not a stock OWASP entry: this project's own risk class, already in
# `finding.py`'s OWASP_IDS.
OWASP_ID = "AUDITABILITY"

TITLE = "Agent constructed with no callback or handler argument"

# The subject set is `AGENT_FACTORIES` itself, not a copy of it. `AGENT_DEF`
# also covers bare model clients -- `ChatLiteLLM(...)`, from `MODEL_CLASSES` --
# and "auditability of agent actions" is not a claim worth making about a client
# constructor that takes none. Naming the detector's own set is what excludes
# them: a second frozenset here would be eighteen duplicated literals that drift
# the first time a factory is added to the detector and not to this file.

# The arguments that attach a handler. Only these two: a name missing here
# costs a false positive, which is loud, while a name wrongly present is
# silence -- the same asymmetry `taint.CONFIGURING_METHODS` documents.
HANDLER_ARGUMENTS = frozenset({"callbacks", "callback_manager"})


def _has_handler(call: ast.Call) -> bool:
    """Say whether this construction was given a callback or handler argument."""
    return any(keyword.arg in HANDLER_ARGUMENTS for keyword in call.keywords)


def _unhandled_calls(tree: ast.AST) -> dict[int, set[str]]:
    """Map each line to the dotted names of the calls on it given no handler argument.

    Every call, not only agent constructions: what counts as an agent is decided
    once, in `_is_auditable_agent`, and the join in `find_in_tree` applies it.
    Testing it here as well made the two filters equivalent mutants -- either
    could be deleted with no test failing -- so the redundancy was removed
    rather than documented.
    """
    found: dict[int, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _has_handler(node):
            found.setdefault(node.lineno, set()).add(call_name(node))
    return found


def _is_auditable_agent(surface: Surface) -> bool:
    """Say whether this surface is a Python agent whose construction this check can read.

    Python because the trace reads an `ast` tree. Without that clause the
    planner would count a TypeScript agent, plan the check, read no TypeScript,
    and publish AUDITABILITY as examined with nothing found -- a blind spot
    dressed as a clean result, which is what `coverage.checks_run` exists to
    prevent.
    """
    return (surface.kind == AGENT_DEF and surface.language == PYTHON
            and surface.name.split(".")[0] in AGENT_FACTORIES)


def _agent_surfaces(surfaces: list[Surface], file: str) -> list[Surface]:
    """The file's agent surfaces built by a factory that takes actions."""
    return [surface for surface in surfaces
            if surface.file == file and _is_auditable_agent(surface)]


def _finding_for(surface: Surface) -> Finding:
    """Build the finding, anchored on the agent's construction site."""
    return Finding(
        OWASP_ID, CHECK_NAME, TITLE, STATIC,
        surface_id=surface.id, surface_kind=surface.kind, surface_name=surface.name,
        file=surface.file, line=surface.line,
    )


def find_in_tree(tree: ast.AST, file: str, surfaces: list[Surface]) -> list[Finding]:
    """Report each agent in this file built without a handler argument.

    Joined on line *and* the full dotted name, so two constructions sharing a
    line cannot borrow each other's verdict.
    """
    unhandled = _unhandled_calls(tree)
    reported: dict[str, Finding] = {}
    for surface in _agent_surfaces(surfaces, file):
        if surface.name not in unhandled.get(surface.line, set()):
            continue
        finding = _finding_for(surface)
        reported.setdefault(finding.id, finding)
    return list(reported.values())


def has_agent_surface(surfaces: list[Surface]) -> bool:
    """Say whether this app builds a Python agent, so the planner can scope the check."""
    return any(_is_auditable_agent(surface) for surface in surfaces)


def run_over_repo(repo_path: str, surfaces: list[Surface]) -> list[Finding]:
    """Read each Python file and report the agents built without a handler."""
    root = Path(repo_path)
    findings: list[Finding] = []
    for path in python_files(repo_path):
        try:
            tree = parse_file(path)
        except UnreadableSource:
            # Already recorded in surfaces.json's skipped_files; one unreadable
            # file must not cost the audit.
            continue
        findings += find_in_tree(tree, path.relative_to(root).as_posix(), surfaces)
    return findings

"""Which surfaces the auditability check takes as subjects at all.

`test_auditability.py` owns what the check reports about a construction it has
accepted as a subject. This file owns the step before that: whether a surface
is a subject in the first place. The check names `AGENT_FACTORIES` -- the
detector's own set -- and additionally requires Python, and both halves of that
narrowing are asserted here against the real detector's output rather than
against hand-built surfaces.

Why it matters that the narrowing is asserted twice, once on the check and once
on `has_agent_surface`: the planner calls the gate to decide whether
AUDITABILITY appears in `coverage.checks_run`, and the check itself decides
what is reported. The two used to spell the predicate separately, so they could
disagree -- a plan claiming a risk class the check never examined. They share
one predicate now, and the pairs below are what fails if they stop sharing it.

The same narrowing seen end to end, through `build_findings` and the coverage
block -- including the TypeScript case -- is in `test_check_scope.py`.

What this tree cannot show: it is written here, so it holds no oversized file,
no non-UTF-8 source and no framework idiom nobody foresaw.
"""

from pathlib import Path

from artifacts.surface import AGENT_DEF
from checks.auditability import has_agent_surface, run_over_repo
from detectors.detector_names import AGENT_FACTORIES, MODEL_CLASSES
from parsing.extractor import extract_repo

APP_NAME = "auditability-subjects-app"
PYTHON_FILE = "app.py"

# An agent built by a factory, with nothing attached: the subject the check
# exists for, and the "yes" half of every pair below.
AGENT_APP = '''from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[])
'''

# A bare model client. The detector reports it as `AGENT_DEF` too, so this is
# the line drawn inside one surface kind rather than a surface of another kind
# standing in for it.
MODEL_CLIENT_APP = '''from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o-mini")
'''
MODEL_CLIENT_NAME = "ChatOpenAI"

# One name each set must keep, so two emptied sets cannot satisfy the
# disjointness assertion below by holding nothing.
ANCHOR_FACTORY = "AgentExecutor"
ANCHOR_MODEL_CLASS = "ChatOpenAI"


def surfaces_of(tmp_path: Path, source: str) -> tuple[Path, list]:
    """Write one Python file and return the repository and the surfaces detected in it."""
    repo = tmp_path / APP_NAME
    repo.mkdir(exist_ok=True)
    (repo / PYTHON_FILE).write_text(source, encoding="utf-8")
    return repo, extract_repo(str(repo)).surfaces


def test_no_agent_factory_is_also_a_model_class() -> None:
    """The invariant the whole narrowing rests on: no name may be in both name sets.

    The check names `AGENT_FACTORIES` itself as its subject set, and `AGENT_DEF`
    covers bare model clients as well as agents. The only thing keeping
    `ChatOpenAI(...)` out of the subjects is that it is in `MODEL_CLASSES` and
    not in `AGENT_FACTORIES`. A name in both would put a constructor that takes
    no actions back inside the subject set and report it as an unaudited agent.
    """
    assert AGENT_FACTORIES.isdisjoint(MODEL_CLASSES), (
        f"{sorted(AGENT_FACTORIES & MODEL_CLASSES)} is both an agent factory and a "
        "model class, so a bare model client would be reported as an unaudited agent")


def test_both_name_sets_hold_the_name_this_file_anchors_them_on() -> None:
    """Guard: disjointness is free between two empty sets, so neither may be empty."""
    assert ANCHOR_FACTORY in AGENT_FACTORIES
    assert ANCHOR_MODEL_CLASS in MODEL_CLASSES


def test_a_bare_model_client_is_not_reported(tmp_path) -> None:
    """`ChatOpenAI(...)` takes no actions, so its auditability is not a claim worth making.

    It is an `AGENT_DEF` surface, and `_unhandled_calls` records every call given
    no handler argument, so this construction is in `unhandled`. The only thing
    keeping it out of the findings is `_is_auditable_agent` naming
    `AGENT_FACTORIES`. Measured by deleting that clause: this test fails, along
    with the planner-gate test below and two in `test_check_scope.py`.
    """
    repo, surfaces = surfaces_of(tmp_path, MODEL_CLIENT_APP)
    assert run_over_repo(str(repo), surfaces) == []


def test_the_model_client_really_is_an_agent_surface(tmp_path) -> None:
    """Guard on the test above: without this, silence could mean no surface existed at all."""
    surfaces = surfaces_of(tmp_path, MODEL_CLIENT_APP)[1]
    assert [(s.kind, s.name) for s in surfaces] == [(AGENT_DEF, MODEL_CLIENT_NAME)]


def test_the_planner_gate_says_yes_to_an_app_that_builds_an_agent(tmp_path) -> None:
    """`has_agent_surface` is what puts the check in the plan, so it is asserted directly."""
    assert has_agent_surface(surfaces_of(tmp_path, AGENT_APP)[1])


def test_the_planner_gate_says_no_to_an_app_that_only_calls_a_model(tmp_path) -> None:
    """The same narrowing at the gate: a model client leaves AUDITABILITY unexamined."""
    assert not has_agent_surface(surfaces_of(tmp_path, MODEL_CLIENT_APP)[1])

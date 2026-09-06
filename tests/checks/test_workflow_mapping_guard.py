"""Dispatching a component-anchored check with no mapping is refused, not tolerated.

Two checks read `state["mapping_document"]`, and before `_mapping_for` they
failed in two different ways over the same bad input. `undeclared_dependency`
died as `AttributeError: 'NoneType' object has no attribute 'get'` -- cryptic,
but loud enough to notice. `known_advisory` **returned normally with no
findings**, so `coverage.checks_run` named a check that had examined nothing
and the artifact read "looked and found none" when the truth was "was handed
nothing to look at". This project holds the silent answer to be the worse one,
so the guard converts both into the same refusal.

Every test drives the public `workflow.audit`, not the private dispatch: the
claim is that a *dispatched* check refuses, and calling the helper directly
would not establish that the graph propagates it. Each refusal is paired with
the same audit given a mapping, so a test cannot pass over an audit that was
broken for some other reason.

Eligibility is decided in `run_checks._checks_that_examined_something` from the
same field, so nothing in the audit path can reach here with None -- the guard
is for the dispatch bug, and `tests/checks/test_run_checks.py` holds the
eligibility half.
"""

from pathlib import Path

import pytest

from advisory_fixtures import ADVISORY_PURL, advisory_record
from artifacts.mapping import THIRD_PARTY, USED_BUT_UNDECLARED
from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from checks import known_advisory, supply_chain, workflow
from parsing.languages import PYTHON

# One surface per check: the tool call reaches the component the advisory index
# below names, and the data source reaches a package no manifest declares.
TOOL_SURFACE = Surface(TOOL_CALL, "ShellTool", "app/agent.py", 12, PYTHON,
                       "tool", "langchain.tools")
DATA_SURFACE = Surface(DATA_SOURCE, "yaml.load", "app/utils.py", 75, PYTHON,
                       "yaml read", "yaml")
SURFACES = [TOOL_SURFACE, DATA_SURFACE]

UNDECLARED_COMPONENT = "pyyaml"

# The mapping the refusals are measured against: with it both checks run and one
# of them reports, so the ValueError below is the missing document and not a
# fixture that never had anything to find.
MAPPING = {
    "entries": [
        {"surface_id": TOOL_SURFACE.id, "purl": ADVISORY_PURL,
         "component_name": "langchain", "reason": THIRD_PARTY},
        {"surface_id": DATA_SURFACE.id, "purl": None,
         "component_name": UNDECLARED_COMPONENT, "reason": USED_BUT_UNDECLARED},
    ],
}

ADVISORIES = {ADVISORY_PURL: [advisory_record()]}

# What the two branches are expected to find over MAPPING: one undeclared
# package, and one advisory on the reached component.
UNDECLARED_FINDING_COUNT = 1
ADVISORY_FINDING_COUNT = 1

# The field named in the refusal, spelled as the state key it comes from rather
# than as a phrase from the sentence around it.
MAPPING_FIELD = "mapping"


def run_with(mapping: dict | None, check: str, tmp_path: Path) -> dict:
    """Audit one app with a plan holding a single component-anchored check."""
    return workflow.audit(str(tmp_path), SURFACES, mapping, [check], ADVISORIES)


def test_the_supply_chain_check_refuses_a_null_mapping(tmp_path) -> None:
    """It used to die as AttributeError from inside the check, naming no check at all."""
    with pytest.raises(ValueError) as raised:
        run_with(None, supply_chain.CHECK_NAME, tmp_path)
    assert supply_chain.CHECK_NAME in str(raised.value)


def test_the_advisory_check_refuses_a_null_mapping_it_used_to_answer_silently(
        tmp_path) -> None:
    """The recorded defect: this returned `[]` and the audit completed.

    `find_known_advisories` still returns no findings for a null mapping -- that
    is the check's own contract and `tests/checks/test_known_advisory.py` pins
    it. What changed is the dispatch: a check that cannot look is never named in
    `coverage.checks_run`, so reaching it with nothing to read is a bug that
    must stop the audit rather than publish a clean result it never established.
    The guard is not defensive decoration on this branch; it is the only thing
    standing between a null mapping and a wrong artifact.
    """
    with pytest.raises(ValueError) as raised:
        run_with(None, known_advisory.CHECK_NAME, tmp_path)
    assert known_advisory.CHECK_NAME in str(raised.value)


def test_the_refusal_names_the_document_that_was_missing(tmp_path) -> None:
    """A reader has to be told which input was absent, not only which check stopped."""
    with pytest.raises(ValueError) as raised:
        run_with(None, known_advisory.CHECK_NAME, tmp_path)
    assert MAPPING_FIELD in str(raised.value)


def test_the_supply_chain_check_still_runs_when_the_mapping_is_there(tmp_path) -> None:
    """The control for the refusal above: the same audit, and it reports."""
    state = run_with(MAPPING, supply_chain.CHECK_NAME, tmp_path)
    assert state["checks_run"] == [supply_chain.CHECK_NAME]
    assert len(state["findings"]) == UNDECLARED_FINDING_COUNT
    assert state["findings"][0].component_name == UNDECLARED_COMPONENT


def test_the_advisory_check_still_runs_when_the_mapping_is_there(tmp_path) -> None:
    """The control for the silent branch: with a mapping it finds the advisory it should."""
    state = run_with(MAPPING, known_advisory.CHECK_NAME, tmp_path)
    assert state["checks_run"] == [known_advisory.CHECK_NAME]
    assert len(state["findings"]) == ADVISORY_FINDING_COUNT
    assert state["findings"][0].purl == ADVISORY_PURL


def test_the_advisory_check_refuses_a_null_advisory_index(tmp_path) -> None:
    """The same silence one argument over, found while pinning the mapping guard.

    `find_known_advisories` answers `[]` for a null advisory index exactly as it
    does for a null mapping, so guarding only the mapping left half the wrong
    artifact reachable: `coverage.checks_run` naming a check that was handed
    nothing. `run_checks._checks_that_examined_something` gates on both fields,
    so arriving here without either is the same dispatch bug and refuses alike.
    """
    with pytest.raises(ValueError) as raised:
        workflow.audit(str(tmp_path), SURFACES, MAPPING, [known_advisory.CHECK_NAME], None)
    assert known_advisory.CHECK_NAME in str(raised.value)

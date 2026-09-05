"""`build_findings` consulting the planner at the edge, and the record it returns.

`checks/planner.py` is tested on its own in `test_planner_monotone.py` and its
three siblings: given a reply, it returns a permutation. This file is about the
wiring -- that `build_findings` really calls it, really returns a second
document beside the findings, and really names the model that chose. Each of
those is a way for a working planner to be inert or unrecorded.

What the order does to the run -- that it reaches `workflow.audit`, and that no
model can shorten `coverage.checks_run` -- is the other half, in
`test_planner_order_honoured.py`.

The app comes from `planner_app_fixtures`, which writes it into `tmp_path`, and
every `ask` here is a stand-in from `semantic_probe_fixtures`. Nothing reaches
a server.
"""

from artifacts.findings_document import MODEL_DISABLED, MODEL_UNAVAILABLE, MODEL_USED
from artifacts.planner_document import SCHEMA_VERSION as PLANNER_SCHEMA_VERSION
from checks.run_checks import GRAPH_CHECKS, _planner_model
from planner_app_fixtures import PLANNED_ORDER, REORDERED, REORDERING_REPLY, audit
from semantic_probe_fixtures import PROBE_MODEL, Answering, Refusing


# --- the app really plans every check ---------------------------------------

def test_this_app_plans_every_graph_check(tmp_path) -> None:
    """Guard: over a shorter plan the permutation tests below would prove much less."""
    _document, planner_document = audit(tmp_path)
    assert sorted(planner_document["order"]) == sorted(GRAPH_CHECKS)
    assert len(PLANNED_ORDER) == 6


def test_the_planned_order_is_the_one_written_down_in_the_fixture(tmp_path) -> None:
    """The baseline every reordering is measured against, so it is asserted, not assumed."""
    _document, planner_document = audit(tmp_path)
    assert planner_document["order"] == PLANNED_ORDER


# --- no model: the plan is the order ----------------------------------------

def test_a_run_with_no_model_records_a_disabled_planner(tmp_path) -> None:
    """No model was offered, so the record names none and says why."""
    _document, planner_document = audit(tmp_path)
    assert planner_document["status"] == MODEL_DISABLED
    assert planner_document["identifier"] is None


def test_a_run_with_no_model_leaves_the_planned_order_unchanged(tmp_path) -> None:
    """A default audit runs the checks in the order the auditor itself planned."""
    _document, planner_document = audit(tmp_path)
    assert planner_document["order"] == PLANNED_ORDER


def test_the_second_return_value_is_a_document_rather_than_the_raw_record(tmp_path) -> None:
    """`build_findings` returns what `outputs` can write, so the schema version is on it."""
    _document, planner_document = audit(tmp_path)
    assert planner_document["schema_version"] == PLANNER_SCHEMA_VERSION


# --- a model that reorders --------------------------------------------------

def test_a_model_that_reorders_returns_a_permutation_of_the_planned_checks(tmp_path) -> None:
    """Same set, different sequence: that is the whole of what the model is allowed."""
    _document, planner_document = audit(tmp_path, Answering(REORDERING_REPLY), PROBE_MODEL)
    assert sorted(planner_document["order"]) == sorted(PLANNED_ORDER)
    assert planner_document["order"] != PLANNED_ORDER


def test_the_recorded_order_is_the_one_the_model_asked_for(tmp_path) -> None:
    """Guard: a permutation is also what ignoring the reply entirely would produce."""
    _document, planner_document = audit(tmp_path, Answering(REORDERING_REPLY), PROBE_MODEL)
    assert planner_document["order"] == REORDERED


def test_a_model_that_chose_the_order_is_named_in_the_record(tmp_path) -> None:
    """A run that used a model without naming it cannot be repeated."""
    _document, planner_document = audit(tmp_path, Answering(REORDERING_REPLY), PROBE_MODEL)
    assert planner_document["status"] == MODEL_USED
    assert planner_document["identifier"] == PROBE_MODEL["identifier"]


def test_an_unreachable_model_keeps_the_planned_order_and_names_nothing(tmp_path) -> None:
    """A refused call degrades the order to the plan; the audit itself is untouched."""
    _document, planner_document = audit(
        tmp_path, Refusing(RuntimeError("connection refused")), PROBE_MODEL)
    assert planner_document["status"] == MODEL_UNAVAILABLE
    assert planner_document["identifier"] is None
    assert planner_document["order"] == PLANNED_ORDER


# --- `_planner_model`: both or neither --------------------------------------

def test_the_model_and_its_name_are_handed_over_together() -> None:
    """With both, the planner is given the call and the identifier to record it under."""
    ask = Answering(REORDERING_REPLY)
    assert _planner_model(ask, PROBE_MODEL) == (ask, PROBE_MODEL["identifier"])


def test_a_model_with_no_provenance_block_is_not_handed_to_the_planner() -> None:
    """`order_checks` raises on an `ask` it cannot name, so it is never given one."""
    assert _planner_model(Answering(REORDERING_REPLY), None) == (None, None)


def test_a_provenance_block_with_no_model_call_plans_nothing() -> None:
    """The other direction: a name with nothing behind it is not a model that ran."""
    assert _planner_model(None, PROBE_MODEL) == (None, None)


def test_an_unnamed_model_leaves_the_planner_disabled_rather_than_failing(tmp_path) -> None:
    """End to end: the pairing is what keeps `order_checks` from raising mid-audit."""
    ask = Answering(REORDERING_REPLY)
    _document, planner_document = audit(tmp_path, ask, probe_model=None)
    assert planner_document["status"] == MODEL_DISABLED
    assert planner_document["order"] == PLANNED_ORDER
    assert ask.prompts == [], "the planner was handed a model it could not name"

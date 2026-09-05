"""`planner.json`'s two schema-2 fields: what the model asked each check to examine.

A sibling of test_planner_document.py, which is at the ~200-line cap and owns
the status, the identifier and the order. This file owns what task 7.4 added:
`surface_selection` and `refused_narrowing`.

Two rules matter here and both are easy to lose to a tidy-up.

**`surface_selection`'s ids are sorted while `order` is not.** They sit next to
each other in the same document with opposite rules, because membership is the
fact in one and sequence is the fact in the other. Said out loud so neither gets
"fixed" into the other.

**`refused_narrowing` is the only evidence the guard ever fired.** Without it, a
model that asked to narrow every check and was refused every time writes a file
byte-identical to one produced by a model that asked for nothing -- and the
difference between those two runs is the difference between a planner that is
working and one that is being ignored.

Nothing reads this file (`docs/SCHEMAS.md`), which is why the rules it publishes
are asserted here or nowhere.
"""

import json

from artifacts.finding import SCHEMA_VERSION as FINDINGS_SCHEMA_VERSION
from artifacts.findings_document import MODEL_DISABLED, MODEL_USED
from artifacts.planner_document import build_planner_document, planner_to_json
from checks.plan_selection import NOT_NARROWABLE, UNKNOWN_SURFACE
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK

MODEL_ID = "qwen2.5-coder:7b-instruct@sha256:abc"
ORDER = [TAINT_CHECK, PERMISSION_CHECK]

# Deliberately unsorted, and deliberately not in this order in the file: the
# selection's ids are membership, so they are published sorted.
UNSORTED_IDS = ["utils.py:75:DATA_SOURCE:yaml.load", "agent.py:12:TOOL_CALL:ShellTool"]

REFUSALS = [
    {"check": SUPPLY_CHAIN_CHECK, "surface_ids": [], "reason": NOT_NARROWABLE},
    {"check": PERMISSION_CHECK, "surface_ids": ["nowhere.py:1:TOOL_CALL:Ghost"],
     "reason": UNKNOWN_SURFACE},
]


def record(selection: dict | None = None, refused: list | None = None,
           status: str = MODEL_USED, identifier: str | None = MODEL_ID) -> dict:
    """A planner record shaped by hand, so the document is tested apart from the planner."""
    return {"status": status, "identifier": identifier, "order": list(ORDER),
            "surface_selection": selection or {}, "refused_narrowing": refused or []}


def built(**parts) -> dict:
    """One planner document from a hand-shaped record."""
    return build_planner_document(record(**parts), FINDINGS_SCHEMA_VERSION)


# --- a run that narrowed nothing ---------------------------------------------

def test_a_planner_that_narrowed_nothing_publishes_both_fields_empty() -> None:
    """Present and empty, never absent: a reader reads one shape whatever happened."""
    document = built()
    assert (document["surface_selection"], document["refused_narrowing"]) == ({}, [])


def test_a_record_predating_the_two_fields_still_builds() -> None:
    """A record with neither key reads as "narrowed nothing" rather than raising.

    `run_baseline.py` and every test that shapes a record by hand went through
    this path unchanged, which is what kept task 7.4 out of the baselines.
    """
    old_record = {"status": MODEL_DISABLED, "identifier": None, "order": list(ORDER)}
    document = build_planner_document(old_record, FINDINGS_SCHEMA_VERSION)
    assert (document["surface_selection"], document["refused_narrowing"]) == ({}, [])


# --- the selection -----------------------------------------------------------

def test_the_selection_keeps_the_check_it_was_given() -> None:
    """Which check was narrowed is the fact; the file must not lose it to a tidy-up."""
    document = built(selection={TAINT_CHECK: UNSORTED_IDS})
    assert list(document["surface_selection"]) == [TAINT_CHECK]


def test_the_ids_in_a_selection_are_published_sorted() -> None:
    """Membership is the fact here, so the sequence carries no meaning and is made stable."""
    document = built(selection={TAINT_CHECK: UNSORTED_IDS})
    assert document["surface_selection"][TAINT_CHECK] == sorted(UNSORTED_IDS)


def test_the_ids_are_sorted_while_the_order_beside_them_is_not() -> None:
    """The two adjacent lists with opposite rules, asserted together so neither drifts."""
    document = built(selection={TAINT_CHECK: UNSORTED_IDS})
    assert document["surface_selection"][TAINT_CHECK] != UNSORTED_IDS
    assert document["order"] == ORDER != sorted(ORDER)


def test_two_narrowed_checks_are_published_in_a_stable_order() -> None:
    """The artifact is byte-stable, so a dict's insertion order must not reach the file."""
    document = built(selection={TAINT_CHECK: [], PERMISSION_CHECK: []})
    assert list(document["surface_selection"]) == sorted([TAINT_CHECK, PERMISSION_CHECK])


def test_the_selection_is_copied_rather_than_aliased() -> None:
    """A caller editing its dict afterwards must not rewrite the artifact."""
    selection = {TAINT_CHECK: list(UNSORTED_IDS)}
    document = built(selection=selection)
    selection[TAINT_CHECK].append("invented")
    assert len(document["surface_selection"][TAINT_CHECK]) == len(UNSORTED_IDS)


# --- the refusals ------------------------------------------------------------

def test_every_refusal_reaches_the_file() -> None:
    """The only evidence the guard fired, so not one of them may be dropped."""
    assert len(built(refused=REFUSALS)["refused_narrowing"]) == len(REFUSALS)


def test_the_refusals_are_sorted_by_check_and_then_reason() -> None:
    """Two refusals of one check are told apart by reason, so both keys are in the sort."""
    document = built(refused=REFUSALS)
    assert [entry["check"] for entry in document["refused_narrowing"]] == [
        PERMISSION_CHECK, SUPPLY_CHAIN_CHECK]


def test_a_refusal_keeps_its_reason_and_the_ids_it_names() -> None:
    """A reader debugging a model's reply needs the reason and the ids, not a count."""
    document = built(refused=REFUSALS)
    assert document["refused_narrowing"][0] == REFUSALS[1]


def test_a_run_that_asked_and_was_refused_differs_from_one_that_asked_for_nothing() -> None:
    """The whole case for the field: without it the two runs write identical files."""
    assert planner_to_json(built(refused=REFUSALS)) != planner_to_json(built())


# --- the on-disk form --------------------------------------------------------

def test_both_fields_survive_the_round_trip_to_json() -> None:
    """Written and read back, because that is the only form anyone will ever see."""
    document = built(selection={TAINT_CHECK: UNSORTED_IDS}, refused=REFUSALS)
    written = json.loads(planner_to_json(document))
    assert written["surface_selection"] == {TAINT_CHECK: sorted(UNSORTED_IDS)}
    assert written["refused_narrowing"] == document["refused_narrowing"]


def test_the_written_document_would_still_be_accepted_by_its_builder() -> None:
    """Rebuilt from the file: a document the builder would refuse must not be on disk."""
    document = built(selection={TAINT_CHECK: UNSORTED_IDS}, refused=REFUSALS)
    written = json.loads(planner_to_json(document))
    assert build_planner_document(written, FINDINGS_SCHEMA_VERSION) == document

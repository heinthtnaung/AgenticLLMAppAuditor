"""`order_checks` turning one model reply into a narrowing, or into nothing at all.

`test_plan_selection.py` attacks the guard directly with values a model could
not produce. This file goes through the reply, so the whole path is exercised:
`parse_selection` reads the key, `resolve` judges it, and `planner_run` records
both what stood and what was refused.

The table this file works through, one row per way a narrowing can go wrong:

    narrow to one       examines 3 of 5   (1 chosen + 2 never described)
    empty list          examines 5 of 5   refused: empty_selection
    unknown id          examines 5 of 5   refused: unknown_surface_id
    not narrowable      examines 5 of 5   refused: not_narrowable
    invented check      examines 5 of 5   refused: unknown_check
    silence or garbage  examines 5 of 5   nothing refused

**The last column is the property.** Five of the six rows end at full coverage,
which is what "a failure mode falls back" has to mean if it is to mean anything.

The describe cap is patched down to three throughout, because the point of each
row is the refusal rather than the cap. The cap at its real value is
`test_planner_describe_cap.py`, where a model names one of 41 surfaces and the
other 40 have to run anyway.
"""

import json

import pytest

from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from checks import plan_selection, planner
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

# Five surfaces; the fixture below shows the model three of them.
SURFACES = [Surface(TOOL_CALL, f"Tool{index}", "agent.py", index + 1, PYTHON, "tool",
                    "langchain.tools")
            for index in range(4)] + [
    Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")]
DESCRIBED_COUNT = 3
EVERY_SURFACE = 5

ELIGIBLE = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK]
MODEL_ID = "qwen2.5-coder:7b-instruct@sha256:abc"

CHOSEN_ID = SURFACES[0].id
GHOST_ID = "nowhere.py:1:TOOL_CALL:Ghost"


def answering(reply: str):
    """An `ask` that returns one fixed reply, standing in for the model."""
    def ask(prompt: str) -> str:
        return reply
    return ask


def narrowing_reply(check: str, surface_ids: list[str]) -> str:
    """The reply shape the prompt asks for, carrying one check's chosen surfaces."""
    return json.dumps({planner.SELECTION_KEY: {check: surface_ids}})


@pytest.fixture
def capped_at_three(monkeypatch) -> None:
    """Show the model three of the five surfaces, so two are always undescribed."""
    monkeypatch.setattr(planner, "MAX_SURFACES_DESCRIBED", DESCRIBED_COUNT)


def plan(reply: str) -> dict:
    """Plan the audit with one model reply and return the record it produced."""
    _order, record = planner.order_checks(SURFACES, ELIGIBLE, answering(reply), MODEL_ID)
    return record


def examined(record: dict, check: str) -> int:
    """How many surfaces one check will actually be handed under this record."""
    selection = record["surface_selection"]
    return len(plan_selection.surfaces_for(check, selection, SURFACES))


def reasons(record: dict) -> list[str]:
    """The reason of every narrowing the guard refused."""
    return [entry["reason"] for entry in record["refused_narrowing"]]


# --- row 1: a narrowing that stands -----------------------------------------

def test_a_check_narrowed_to_one_surface_examines_three_of_the_five(capped_at_three) -> None:
    """The feature itself: one chosen, plus the two the prompt never described."""
    record = plan(narrowing_reply(TAINT_CHECK, [CHOSEN_ID]))
    assert examined(record, TAINT_CHECK) == 3
    assert len(SURFACES) == EVERY_SURFACE


def test_a_narrowing_that_stands_is_refused_nothing(capped_at_three) -> None:
    """Guard: three of five is also what a refusal plus a bug would produce."""
    assert plan(narrowing_reply(TAINT_CHECK, [CHOSEN_ID]))["refused_narrowing"] == []


def test_the_narrowing_reaches_the_record_as_a_sorted_list_of_ids(capped_at_three) -> None:
    """`planner.json` publishes the selection, so it is a stable list rather than a set."""
    record = plan(narrowing_reply(TAINT_CHECK, [CHOSEN_ID]))
    selected = record["surface_selection"][TAINT_CHECK]
    assert selected == sorted(selected)
    assert CHOSEN_ID in selected


def test_narrowing_one_check_leaves_the_other_two_at_full_coverage(capped_at_three) -> None:
    """The selection is per check: nothing narrows a check the reply never mentioned."""
    record = plan(narrowing_reply(TAINT_CHECK, [CHOSEN_ID]))
    assert examined(record, PERMISSION_CHECK) == EVERY_SURFACE
    assert list(record["surface_selection"]) == [TAINT_CHECK]


# --- rows 2 to 5: every refusal falls back to full coverage ------------------

@pytest.mark.parametrize("surface_ids,reason", [
    ([], plan_selection.EMPTY_SELECTION),
    ([GHOST_ID], plan_selection.UNKNOWN_SURFACE),
])
def test_a_narrowing_the_guard_refuses_leaves_the_check_at_full_coverage(
        capped_at_three, surface_ids: list[str], reason: str) -> None:
    """Rows 2 and 3: the check still sees all five, and the record says why."""
    record = plan(narrowing_reply(TAINT_CHECK, surface_ids))
    assert examined(record, TAINT_CHECK) == EVERY_SURFACE
    assert reasons(record) == [reason]


def test_narrowing_a_component_anchored_check_is_refused(capped_at_three) -> None:
    """Row 4: `undeclared_dependency` reads the mapping, so its surfaces are not its subject."""
    record = plan(narrowing_reply(SUPPLY_CHAIN_CHECK, [CHOSEN_ID]))
    assert examined(record, SUPPLY_CHAIN_CHECK) == EVERY_SURFACE
    assert reasons(record) == [plan_selection.NOT_NARROWABLE]


def test_narrowing_a_check_the_auditor_does_not_have_is_refused(capped_at_three) -> None:
    """Row 5: an invented name must never reach `checks_narrowed`, which names checks that ran."""
    record = plan(narrowing_reply("check_the_vibes", [CHOSEN_ID]))
    assert record["surface_selection"] == {}
    assert reasons(record) == [plan_selection.UNKNOWN_CHECK]


# --- row 6: silence ----------------------------------------------------------

def test_a_reply_with_no_narrowing_key_narrows_and_refuses_nothing(capped_at_three) -> None:
    """Row 6: an ordering-only reply is an opinion about the order and nothing else."""
    record = plan(json.dumps({planner.ORDER_KEY: [TAINT_CHECK]}))
    assert (record["surface_selection"], record["refused_narrowing"]) == ({}, [])


def test_a_reply_that_is_not_json_at_all_narrows_and_refuses_nothing(capped_at_three) -> None:
    """Garbled is silence: no opinion is the safe answer, and full coverage is it."""
    record = plan("I would look at the shell tool first, I think.")
    assert (record["surface_selection"], record["refused_narrowing"]) == ({}, [])
    assert examined(record, TAINT_CHECK) == EVERY_SURFACE

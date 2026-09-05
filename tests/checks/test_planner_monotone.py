"""The model may reorder the checks; it may never remove one, nor narrow one by accident.

The invariant this whole module exists for: whatever the model replies, the
returned order is a permutation of the eligible checks. A dropped check would
land in `coverage.checks_run` as an absence, and `docs/SCHEMAS.md` defines that
absence as "could not look at all" -- the scorer reads it as
`no_check_for_risk_class`. So a model able to subtract would be deciding what
counts as a finding, which `docs/FLOW.md` and `docs/PHASE_3_PLAN.md` both
forbid, and it would do it in coverage vocabulary where a reader would not see
it.

**Task 7.4 added a second thing a reply must not do.** The planner may now
narrow a check to some of its surfaces, so the table below carries a second
question as well: no malformed reply may *narrow* anything. A garbled reply
that silenced a check on most of its surfaces would be the same recall loss
arriving one level down -- the check would still be in `checks_run`, so a
reader would see "looked and found nothing" rather than "looked at two of
eleven". `checks/plan_selection.py` is the containment and
`test_plan_selection.py` attacks it directly; here it is attacked only through
the replies a real model produces.

A promise in a docstring is not that guarantee, so the table below is the
guarantee: every malformed reply shape a local model actually produces --
prose, fences, truncation, invented names, duplicates, a subset, a superset,
the wrong type -- is pushed through `order_checks` and the result compared with
the eligible set. Adding a shape is adding one line to `MALFORMED_REPLIES`.

Two siblings carry the rest: `test_planner_reply_types.py` for a reply that is
not text at all, and `test_planner_merge.py` for `merge_monotonically` attacked
directly rather than through `order_checks`.

Nothing here reaches Ollama: `ask` is injected, and every one used below is
written in this file.
"""

import pytest

from artifacts.findings_document import MODEL_DISABLED, MODEL_UNAVAILABLE, MODEL_USED
from artifacts.surface import TOOL_CALL, Surface
from checks import plan_selection, planner
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

# The three checks handed to the planner throughout. Three, so a reply naming
# one is a strict subset and a reply naming two is a real reordering.
ELIGIBLE = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK]

# One more surface than the prompt describes, so the last of them is real and
# was still never shown to the model. That is what makes the two "unknown id"
# shapes below different questions rather than one written twice: an id in no
# surface at all is a hallucination, while an id past the cap is a surface the
# model could not have named because it was never told it existed.
SURFACES = [Surface(TOOL_CALL, f"Tool{index}", "agent.py", index + 1, PYTHON, "tool",
                    "langchain.tools")
            for index in range(planner.MAX_SURFACES_DESCRIBED + 1)]

DESCRIBED_SURFACE_ID = SURFACES[0].id
UNDESCRIBED_SURFACE_ID = SURFACES[-1].id

# An id belonging to no surface this app has, in the shape a model invents.
GHOST_SURFACE_ID = "nowhere.py:1:TOOL_CALL:Ghost"

# The identifier a caller passes so the record says which model chose.
MODEL_ID = "qwen2.5-coder:7b-instruct@sha256:abc"

# Every way a reply has been or could be malformed, by the name of the shape.
# The value is the whole reply string the model is pretended to have returned.
MALFORMED_REPLIES = {
    "empty": "",
    "whitespace": "   \n\t ",
    "prose_only": "I would run the permission check first, then the others.",
    "invented_name": '{"order": ["check_the_vibes"]}',
    "all_names_invented": '{"order": ["one", "two", "three"]}',
    "truncated_json": '{"order": ["' + TAINT_CHECK + '"',
    "order_not_a_list": '{"order": "not-a-list"}',
    "order_empty_list": '{"order": []}',
    "order_null": '{"order": null}',
    "order_key_missing": '{"checks": ["' + TAINT_CHECK + '"]}',
    "strict_subset": '{"order": ["' + TAINT_CHECK + '"]}',
    "superset": '{"order": ["%s", "%s", "%s", "invented"]}' % (
        TAINT_CHECK, PERMISSION_CHECK, SUPPLY_CHAIN_CHECK),
    "duplicates": '{"order": ["%s", "%s", "%s"]}' % (TAINT_CHECK, TAINT_CHECK, TAINT_CHECK),
    "fenced": '```json\n{"order": ["' + TAINT_CHECK + '"]}\n```',
    "prose_either_side": 'Sure! {"order": ["' + TAINT_CHECK + '"]} Hope that helps.',
    "non_strings_in_list": '{"order": [1, null, {"a": 1}, ["' + TAINT_CHECK + '"]]}',
    "json_null": "null",
    "json_array": '["' + TAINT_CHECK + '"]',
    "json_string": '"' + TAINT_CHECK + '"',
    "nested_object": '{"order": {"first": "' + TAINT_CHECK + '"}}',
    "braces_only": "{}",
    "closing_brace_first": '} {"order": ["' + TAINT_CHECK + '"]',
    # Six shapes about the narrowing key rather than the order key, added with
    # task 7.4. Each is a way a reply could subtract surfaces instead of checks.
    "selection_not_an_object": '{"surfaces": "not-an-object"}',
    "selection_entry_not_a_list": '{"surfaces": {"%s": "not-a-list"}}' % TAINT_CHECK,
    "selection_entry_of_nulls": '{"surfaces": {"%s": [null]}}' % TAINT_CHECK,
    "selection_of_an_invented_surface": '{"surfaces": {"%s": ["%s"]}}' % (
        TAINT_CHECK, GHOST_SURFACE_ID),
    "selection_past_the_describe_cap": '{"surfaces": {"%s": ["%s"]}}' % (
        TAINT_CHECK, UNDESCRIBED_SURFACE_ID),
    "selection_of_a_component_anchored_check": '{"surfaces": {"%s": ["%s"]}}' % (
        SUPPLY_CHAIN_CHECK, DESCRIBED_SURFACE_ID),
}


def answering(reply: str):
    """An `ask` that returns one fixed reply, standing in for the model."""
    def ask(prompt: str) -> str:
        return reply
    return ask


def refusing(error: Exception):
    """An `ask` that fails the way an absent or broken Ollama does.

    `RuntimeError` at every call site below, because that is the only failure
    the real `ask` produces: `model_client._post` converts every `OSError` --
    so `ConnectionRefusedError` and `TimeoutError` both -- into a `RuntimeError`
    before it reaches a caller. `order_checks` catches `RuntimeError` and
    nothing wider on purpose, so raising a raw socket error here would test a
    shape no model client can hand it.
    """
    def ask(prompt: str) -> str:
        raise error
    return ask


@pytest.mark.parametrize("shape", sorted(MALFORMED_REPLIES))
def test_a_malformed_reply_never_removes_a_check(shape: str) -> None:
    """Every shape in the table returns a permutation of the eligible checks, nothing less."""
    order, _ = planner.order_checks(
        SURFACES, ELIGIBLE, answering(MALFORMED_REPLIES[shape]), MODEL_ID)
    assert sorted(order) == sorted(ELIGIBLE)


@pytest.mark.parametrize("shape", sorted(MALFORMED_REPLIES))
def test_a_malformed_reply_never_repeats_a_check(shape: str) -> None:
    """A repeated name would run a check twice and report its findings twice."""
    order, _ = planner.order_checks(
        SURFACES, ELIGIBLE, answering(MALFORMED_REPLIES[shape]), MODEL_ID)
    assert len(order) == len(ELIGIBLE)


@pytest.mark.parametrize("shape", sorted(MALFORMED_REPLIES))
def test_a_malformed_reply_is_still_recorded_as_the_model_having_answered(shape: str) -> None:
    """It replied, so the status is `used`: unreadable is an opinion, not an outage."""
    _, record = planner.order_checks(
        SURFACES, ELIGIBLE, answering(MALFORMED_REPLIES[shape]), MODEL_ID)
    assert record["status"] == MODEL_USED


@pytest.mark.parametrize("shape", sorted(MALFORMED_REPLIES))
def test_a_malformed_reply_never_narrows_a_check(shape: str) -> None:
    """The invariant task 7.4 added, in the same exhaustive form as the one above it.

    An empty selection means every check examines every surface, which is what
    each of these shapes must degrade to. The six narrowing shapes reach it by
    being refused; the twenty-two order shapes by asking for no narrowing at
    all -- and both are the same answer to a reader.
    """
    _, record = planner.order_checks(
        SURFACES, ELIGIBLE, answering(MALFORMED_REPLIES[shape]), MODEL_ID)
    assert record["surface_selection"] == {}


@pytest.mark.parametrize("shape", sorted(MALFORMED_REPLIES))
def test_a_refused_narrowing_is_recorded_with_a_reason_a_reader_can_look_up(
        shape: str) -> None:
    """Rule 5: a refusal is evidence the guard fired, so its reason is from the closed set."""
    _, record = planner.order_checks(
        SURFACES, ELIGIBLE, answering(MALFORMED_REPLIES[shape]), MODEL_ID)
    for refusal in record["refused_narrowing"]:
        assert refusal["reason"] in plan_selection.REFUSAL_REASONS


def test_the_table_holds_every_shape_this_file_claims_to_cover() -> None:
    """Guard: a table silently emptied would make the four tests above pass over nothing.

    22 order shapes, and six about the narrowing key that task 7.4 added. The
    number is written out rather than derived for exactly the reason the guard
    exists -- derived from the table, it would agree with an empty one.
    """
    assert len(MALFORMED_REPLIES) == 28


def test_a_reply_naming_no_check_at_all_leaves_the_planned_order_alone() -> None:
    """Not just a permutation: with no usable preference the original order survives."""
    order, _ = planner.order_checks(
        SURFACES, ELIGIBLE, answering("no idea, sorry"), MODEL_ID)
    assert order == ELIGIBLE


def test_a_partial_reply_moves_what_it_named_and_appends_the_rest_in_order() -> None:
    """The subset case in full: named first, unnamed behind it in the order planned."""
    order, _ = planner.order_checks(
        SURFACES, ELIGIBLE, answering('{"order": ["' + TAINT_CHECK + '"]}'), MODEL_ID)
    assert order == [TAINT_CHECK, PERMISSION_CHECK, SUPPLY_CHAIN_CHECK]


def test_a_valid_reply_genuinely_reorders_the_checks() -> None:
    """The feature itself: two named out of three, and the omitted one is appended."""
    reply = '{"order": ["%s", "%s"]}' % (TAINT_CHECK, PERMISSION_CHECK)
    order, record = planner.order_checks(SURFACES, ELIGIBLE, answering(reply), MODEL_ID)
    assert order == [TAINT_CHECK, PERMISSION_CHECK, SUPPLY_CHAIN_CHECK]
    assert order != ELIGIBLE
    assert record == {"status": MODEL_USED, "identifier": MODEL_ID, "order": order,
                      "surface_selection": {}, "refused_narrowing": []}


def test_no_model_leaves_the_order_untouched_and_says_so() -> None:
    """`ask=None` is a model-disabled run, and its order is the one the caller planned."""
    order, record = planner.order_checks(SURFACES, ELIGIBLE)
    assert order == ELIGIBLE
    assert record == {"status": MODEL_DISABLED, "identifier": None, "order": ELIGIBLE,
                      "surface_selection": {}, "refused_narrowing": []}


def test_a_model_that_cannot_be_reached_leaves_the_order_untouched_and_says_so() -> None:
    """An absent Ollama costs the ordering opinion and nothing else -- no check is lost."""
    order, record = planner.order_checks(
        SURFACES, ELIGIBLE, refusing(RuntimeError("cannot reach the model server")), MODEL_ID)
    assert order == ELIGIBLE
    assert record == {"status": MODEL_UNAVAILABLE, "identifier": None, "order": ELIGIBLE,
                      "surface_selection": {}, "refused_narrowing": []}


def test_the_disabled_and_unavailable_orders_are_the_same_list() -> None:
    """Why `findings.json` is byte-identical either way: both degrade to the planned order."""
    disabled, _ = planner.order_checks(SURFACES, ELIGIBLE)
    unavailable, _ = planner.order_checks(
        SURFACES, ELIGIBLE, refusing(RuntimeError("model server timed out")), MODEL_ID)
    assert disabled == unavailable == ELIGIBLE


def test_the_record_is_a_copy_the_caller_cannot_edit_the_plan_through() -> None:
    """The order in the record is the planner's own list, not the caller's to mutate."""
    eligible = list(ELIGIBLE)
    _, record = planner.order_checks(SURFACES, eligible)
    record["order"].append("invented")
    assert eligible == ELIGIBLE

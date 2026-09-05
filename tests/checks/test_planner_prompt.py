"""What the planner asks the model, and what it records about the answer.

The sibling of test_planner_monotone.py, which owns the one invariant. This
file owns the two edges either side of it: the prompt built before the call,
and the record written after it.

One of these is not a style test. `order_checks` builds the prompt *outside*
its `try`, so a bug in this project's own prompt building raises rather than
being filed as the model being unavailable -- an auditor that reported its own
defect as "no model" would hide it from the person running it. The test below
plants the defect and asserts it propagates.

The same line runs through the `except` clause. `order_checks` catches
`RuntimeError` and nothing wider, because that is the single exception
`model_client` raises for every reach failure. A `TypeError` from a
wrongly-wired `ask` is this repository's bug, and filing it as `unavailable`
would write "Ollama could not be reached" into an artifact as a fact. Both
halves of that split are asserted at the end of this file.
"""

import pytest

from artifacts.findings_document import MODEL_DISABLED, MODEL_UNAVAILABLE, MODEL_USED
from artifacts.surface import TOOL_CALL, Surface
from checks import plan_selection, planner
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

ELIGIBLE = [PERMISSION_CHECK, TAINT_CHECK]

SURFACE = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")

# Three more surfaces than the prompt describes, so the cap is exceeded by a
# number a reader can check against the "and N more" line.
OVER_THE_CAP = planner.MAX_SURFACES_DESCRIBED + 3

MODEL_ID = "qwen2.5-coder:7b-instruct@sha256:abc"


def many_surfaces(count: int) -> list[Surface]:
    """A list of distinct surfaces, one per line of a fictional file."""
    return [Surface(TOOL_CALL, f"Tool{index}", "agent.py", index + 1, PYTHON, "tool")
            for index in range(count)]


def test_a_surface_is_described_by_kind_name_and_position() -> None:
    """The model is told where each surface is, so its order is about this app."""
    assert planner.describe_surfaces([SURFACE]) == "- TOOL_CALL ShellTool at agent.py:12"


def test_no_surfaces_still_describes_something() -> None:
    """An empty section would leave the prompt reading as if a line went missing."""
    assert planner.describe_surfaces([]) == "- none"


def test_the_description_stops_at_the_cap() -> None:
    """A repo with hundreds of surfaces must not push the real question out of context."""
    lines = planner.describe_surfaces(many_surfaces(OVER_THE_CAP)).splitlines()
    assert len(lines) == planner.MAX_SURFACES_DESCRIBED + 1


def test_the_capped_description_says_how_many_it_left_out() -> None:
    """Truncating silently would let the model order an audit it was misinformed about."""
    lines = planner.describe_surfaces(many_surfaces(OVER_THE_CAP)).splitlines()
    assert lines[-1] == "- ... and 3 more"


def test_a_list_at_the_cap_exactly_says_nothing_about_more() -> None:
    """Off-by-one guard: at the cap there is no remainder to mention."""
    lines = planner.describe_surfaces(many_surfaces(planner.MAX_SURFACES_DESCRIBED)).splitlines()
    assert len(lines) == planner.MAX_SURFACES_DESCRIBED
    assert "more" not in lines[-1]


def test_the_prompt_names_every_check_the_model_may_choose_between() -> None:
    """A name missing here is a check the model cannot ask for, silently."""
    prompt = planner.build_prompt([SURFACE], ELIGIBLE)
    assert all(f"- {name}" in prompt for name in ELIGIBLE)


def test_the_prompt_shows_the_key_the_reply_is_read_from() -> None:
    """The parser looks for one key, so the prompt must ask for that key."""
    assert f'"{planner.ORDER_KEY}"' in planner.build_prompt([SURFACE], ELIGIBLE)


def test_the_prompt_shows_the_key_a_narrowing_is_read_from() -> None:
    """`parse_selection` looks for one key, so the prompt has to ask for that key."""
    assert f'"{planner.SELECTION_KEY}"' in planner.build_prompt([SURFACE], ELIGIBLE)


def offered_for_narrowing(prompt: str) -> list[str]:
    """The check names the prompt says may be narrowed, read back out of the sentence."""
    return prompt.split("can be narrowed: ")[1].split(".")[0].split(", ")


def test_the_prompt_names_only_the_checks_that_may_be_narrowed() -> None:
    """A check offered here but refused by the guard would waste the model's one answer."""
    offered = offered_for_narrowing(planner.build_prompt([SURFACE], ELIGIBLE))
    assert sorted(offered) == sorted(plan_selection.NARROWABLE_CHECKS)


def test_the_prompt_never_offers_a_component_anchored_check_for_narrowing() -> None:
    """Rule 4, asserted where the model would first hear about it.

    `undeclared_dependency` is eligible here, so it is named in the check list
    at the top of the prompt -- and still absent from the sentence that says
    what may be narrowed, which is the whole distinction.
    """
    prompt = planner.build_prompt([SURFACE], [SUPPLY_CHAIN_CHECK])
    assert f"- {SUPPLY_CHAIN_CHECK}" in prompt
    assert SUPPLY_CHAIN_CHECK not in offered_for_narrowing(prompt)


def test_the_prompt_carries_the_surfaces_it_was_given() -> None:
    """The description reaches the prompt rather than being built and dropped."""
    assert planner.describe_surfaces([SURFACE]) in planner.build_prompt([SURFACE], ELIGIBLE)


def refuse_to_be_asked(prompt: str) -> str:
    """An `ask` that fails the test if the prompt building bug ever reaches it."""
    raise AssertionError("the model was asked with a prompt that could not be built")


def test_a_bug_building_the_prompt_is_raised_not_filed_as_an_absent_model() -> None:
    """A surface missing its attributes is this project's defect, and it must surface as one.

    Were the prompt built inside the `try`, this would return the planned order
    with status `unavailable`: the audit would look like it ran without Ollama,
    and the defect would never be seen.
    """
    with pytest.raises(AttributeError):
        planner.order_checks([object()], ELIGIBLE, refuse_to_be_asked, MODEL_ID)


def test_the_planner_records_each_status_it_knows() -> None:
    """The three the record may carry, mirroring `model_run`'s vocabulary."""
    assert planner.planner_run(MODEL_USED, ELIGIBLE, MODEL_ID)["status"] == MODEL_USED
    for status in (MODEL_UNAVAILABLE, MODEL_DISABLED):
        assert planner.planner_run(status, ELIGIBLE)["status"] == status


def test_the_planner_refuses_a_used_record_that_names_no_model() -> None:
    """Enforced where the record is made, not only where it is written out.

    `artifacts/planner_document.py` refused this all along; `planner_run` did
    not, so `order_checks` could build a record the document would then reject
    -- an audit that failed at the moment it tried to save its artifact.
    """
    with pytest.raises(ValueError, match="must name it"):
        planner.planner_run(MODEL_USED, ELIGIBLE)


@pytest.mark.parametrize("status", [MODEL_UNAVAILABLE, MODEL_DISABLED])
def test_the_planner_refuses_a_record_that_names_a_model_it_did_not_use(status: str) -> None:
    """The other direction: a named `disabled` is a claim about a model that never ran."""
    with pytest.raises(ValueError, match="must not name a model"):
        planner.planner_run(status, ELIGIBLE, MODEL_ID)


def test_an_ask_given_with_no_identifier_is_refused_before_the_model_is_called() -> None:
    """Refused at the call, not after the answer: an unnamed run cannot be reproduced.

    `refuse_to_be_asked` proves the refusal happens first -- the model is never
    reached, so no time is spent on a run whose record the document would reject.
    """
    with pytest.raises(ValueError, match="needs the model's identifier"):
        planner.order_checks([SURFACE], ELIGIBLE, refuse_to_be_asked)


def test_the_planner_refuses_a_status_it_does_not_know() -> None:
    """An invented status would reach a reader as a claim about how the order was chosen."""
    with pytest.raises(ValueError, match="unknown planner status 'guessed'"):
        planner.planner_run("guessed", ELIGIBLE)


def test_the_record_keeps_the_identifier_of_the_model_that_chose() -> None:
    """Which model ordered the audit is part of reproducing it."""
    assert planner.planner_run(MODEL_USED, ELIGIBLE, MODEL_ID)["identifier"] == MODEL_ID


def failing_with(error: Exception):
    """An `ask` that raises one chosen exception, standing in for a broken call."""
    def ask(prompt: str) -> str:
        raise error
    return ask


def test_a_wiring_bug_in_the_ask_propagates_rather_than_being_filed_as_an_absent_model() -> None:
    """The mirror of the prompt-building test: this project's defect must surface as one.

    `order_checks` catches `RuntimeError` and nothing wider. A `TypeError` --
    an `ask` of the wrong arity, a `None` where a callable was meant -- is a bug
    in this repository, and recording it as `unavailable` would write "Ollama
    could not be reached" into an artifact as a fact. That is a false claim, not
    an internal detail, and it would be indistinguishable from a real outage.
    """
    with pytest.raises(TypeError):
        planner.order_checks(
            [SURFACE], ELIGIBLE, failing_with(TypeError("takes 2 args")), MODEL_ID)


def test_the_model_being_unreachable_is_recorded_as_unavailable() -> None:
    """The other half of the pair: `RuntimeError` is what `model_client` raises for a real outage.

    Every reach failure -- refused connection, timeout, bad HTTP, unparsable
    body -- arrives as a `RuntimeError`, so this is the only shape that may be
    caught, and it must still be caught.
    """
    order, record = planner.order_checks(
        [SURFACE], ELIGIBLE, failing_with(RuntimeError("cannot reach the model server")), MODEL_ID)
    assert order == ELIGIBLE
    assert record == {"status": MODEL_UNAVAILABLE, "identifier": None, "order": ELIGIBLE,
                      # An outage costs the ordering opinion and the narrowing
                      # opinion together: an empty selection is full coverage.
                      "surface_selection": {}, "refused_narrowing": []}


def test_an_unreachable_model_says_so_on_stderr(capsys) -> None:
    """The degradation is announced, not silent: a run that lost its planner tells the operator."""
    planner.order_checks(
        [SURFACE], ELIGIBLE, failing_with(RuntimeError("no ollama")), MODEL_ID)
    assert "planner: model unavailable" in capsys.readouterr().err

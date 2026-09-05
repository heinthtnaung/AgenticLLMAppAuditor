"""Rule 3 at the cap's real value: 41 surfaces, 40 described, and all 41 examined.

`describe_surfaces` shows the model at most `MAX_SURFACES_DESCRIBED` surfaces,
so the prompt stays a readable size. Under **ordering** semantics that cap cost
nothing -- the model was choosing between checks, not surfaces. Under
**selection** semantics it is the sharpest bug the design could have had: an
implementation that took the model's list literally would exclude every surface
past the cap without saying so, and the narrowing record would report a smaller
number and look entirely correct.

`plan_selection.resolve` therefore unions the model's choice with every surface
it was never shown. `test_plan_selection.py` proves that over a cap of three
handed in as an argument; this file proves it at the constant's real value,
which is the number the audit actually runs at.

The surfaces are stated by hand and the model is a function written below.
Nothing here reads a repository or reaches a server.
"""

import json

from artifacts.surface import TOOL_CALL, Surface
from checks import plan_selection, planner
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

ELIGIBLE = [PERMISSION_CHECK, TAINT_CHECK]
MODEL_ID = "qwen2.5-coder:7b-instruct@sha256:abc"

# One more surface than the prompt shows, so the last one is real, never
# described, and must still be examined by a check narrowed to the first.
OVER_THE_CAP = planner.MAX_SURFACES_DESCRIBED + 1


def many_surfaces(count: int) -> list[Surface]:
    """A list of distinct surfaces, one per line of a fictional file."""
    return [Surface(TOOL_CALL, f"Tool{index}", "agent.py", index + 1, PYTHON, "tool")
            for index in range(count)]


def narrowed_to(surface_ids: list[str]) -> tuple[list[Surface], list[Surface]]:
    """Plan an audit of 41 surfaces with the taint check narrowed to the given ids.

    Returns the whole surface list and the surfaces that check will be handed,
    which is the only pair the questions below are about.
    """
    surfaces = many_surfaces(OVER_THE_CAP)
    reply = json.dumps({planner.SELECTION_KEY: {TAINT_CHECK: surface_ids}})

    def ask(prompt: str) -> str:
        """Stand in for the model, answering the narrowing this test is about."""
        return reply

    _order, record = planner.order_checks(surfaces, ELIGIBLE, ask, MODEL_ID)
    return surfaces, plan_selection.surfaces_for(
        TAINT_CHECK, record["surface_selection"], surfaces)


def test_the_prompt_really_describes_fewer_surfaces_than_this_app_has() -> None:
    """Guard: at or under the cap there is nothing undescribed and the file proves nothing."""
    described = planner.describe_surfaces(many_surfaces(OVER_THE_CAP)).splitlines()
    assert len(described) == planner.MAX_SURFACES_DESCRIBED + 1
    assert described[-1] == "- ... and 1 more"


def test_a_surface_past_the_cap_runs_even_when_the_model_narrows_to_one() -> None:
    """The 41st surface is the one whose disappearance no reader could have spotted."""
    surfaces, examined = narrowed_to([many_surfaces(OVER_THE_CAP)[0].id])
    assert surfaces[-1] in examined


def test_that_narrowing_examines_two_of_the_forty_one() -> None:
    """The count beside it, so "surface 41 runs" cannot pass by nothing being narrowed."""
    surfaces, examined = narrowed_to([many_surfaces(OVER_THE_CAP)[0].id])
    assert len(surfaces) == 41
    assert len(examined) == 2


def test_the_surface_the_model_chose_is_examined_as_well() -> None:
    """Guard: adding back the undescribed surfaces must not replace the chosen one."""
    surfaces = many_surfaces(OVER_THE_CAP)
    _surfaces, examined = narrowed_to([surfaces[0].id])
    assert surfaces[0] in examined


def test_naming_the_surface_past_the_cap_is_refused_rather_than_honoured() -> None:
    """The mirror: the model cannot ask for what it was never shown, even when it is real."""
    surfaces = many_surfaces(OVER_THE_CAP)
    _surfaces, examined = narrowed_to([surfaces[-1].id])
    assert examined == surfaces

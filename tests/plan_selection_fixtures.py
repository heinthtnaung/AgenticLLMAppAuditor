"""The surfaces, the plan and the call the two `plan_selection` test files share.

`tests/checks/test_plan_selection.py` owns the three rules about surfaces and
`tests/checks/test_plan_selection_refusals.py` the two about checks. Both attack
the same guard over the same five surfaces, so the fixture is spelled once here
-- two copies of a fixture is how the two copies come to disagree about what
"three of five" means.

Nothing here reads a repository this project does not own and nothing reaches a
server: `resolve` is a pure function and every surface below is stated by hand.
A synthetic list is weaker than a real extraction, and deliberately so -- what
is under test is the arithmetic of the containment, not the detectors.
"""

from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from checks import plan_selection
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.known_advisory import CHECK_NAME as ADVISORY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

# Five surfaces, of which the prompt describes the first three. The split is the
# whole of rule 3: two surfaces the model was never told existed.
SURFACES = [Surface(TOOL_CALL, f"Tool{index}", "agent.py", index + 1, PYTHON, "tool",
                    "langchain.tools")
            for index in range(4)] + [
    Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")]
DESCRIBED = SURFACES[:3]
UNDESCRIBED_IDS = {surface.id for surface in SURFACES[3:]}

# The checks this app plans. `undeclared_dependency` is here so the guard can
# tell a check it refuses to narrow from one it has never heard of.
ELIGIBLE = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK, ADVISORY_CHECK,
            AUDITABILITY_CHECK]

CHOSEN_ID = DESCRIBED[0].id
GHOST_ID = "nowhere.py:1:TOOL_CALL:Ghost"


def resolve(selection: dict) -> tuple[dict, list]:
    """Run one asked-for selection through the guard, over the fixture above."""
    return plan_selection.resolve(selection, ELIGIBLE, DESCRIBED, SURFACES)


def refusal_reasons(refused: list[dict]) -> list[str]:
    """The reason of each refusal, in the order they were recorded."""
    return [entry["reason"] for entry in refused]

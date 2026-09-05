"""One app the planner has six checks to order, written into `tmp_path` by the caller.

Two test files audit it -- `tests/checks/test_planner_wiring.py` for the record
`build_findings` returns, `tests/checks/test_planner_order_honoured.py` for what
the order does to the run -- so the tree and the orders it produces are spelled
once here rather than in both.

Two properties of this app are load-bearing and neither may be dropped.
**Every graph check has a subject**, so the order under test is six names long:
a shorter plan makes a permutation test prove much less. And **there is no
prompt template**, so the semantic probe -- which takes the same `ask` -- adds
nothing, leaving the check order as the only difference between a model-on run
and a model-off one.

Nothing here reads a repository this project does not own, and nothing reaches
a server: the model stand-ins live in `semantic_probe_fixtures.py`.
"""

import json
from pathlib import Path

from artifacts.mapping import MAPPING_REASONS, USED_BUT_UNDECLARED
from artifacts.surface import AGENT_DEF, DATA_SOURCE, TOOL_CALL, Surface
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.known_advisory import CHECK_NAME as ADVISORY_CHECK
from checks.output_handling import CHECK_NAME as QUERY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.run_checks import build_findings
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from cli_helpers import STUB_ADVISORY_PIN
from parsing.languages import PYTHON

# One surface per gate in `_checks_that_examined_something`: the tool makes this
# an app that drives a model, the agent makes the auditability check plannable,
# and the data source gives the mapping an entry to join.
TOOL_SURFACE = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")
DATA_SURFACE = Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")
AGENT_SURFACE = Surface(AGENT_DEF, "AgentExecutor", "app.py", 1, PYTHON, "agent",
                        "langchain.agents")
SURFACES = [TOOL_SURFACE, DATA_SURFACE, AGENT_SURFACE]

# Python for the three checks that read source, with nothing in it to report:
# what is under test is the order the checks ran in, not what they found.
APP_FILE = "app.py"
APP_SOURCE = "greeting = 'hello'\n"

# Shaped like a real mapping.json, with the one undeclared package the
# supply-chain check reports.
MAPPING = {
    "entries": [{
        "surface_id": DATA_SURFACE.id,
        "reason": USED_BUT_UNDECLARED,
        "component_name": "pyyaml",
    }],
    "reason_counts": {reason: 0 for reason in MAPPING_REASONS} | {USED_BUT_UNDECLARED: 1},
}

# An empty index is still advisory data: the check looked and matched nothing,
# which is what makes it eligible.
ADVISORIES: dict = {}

# What `_checks_that_examined_something` plans for this app, in the order it
# names them. Written out rather than derived, so a change to that order is a
# change a reader has to make here too.
PLANNED_ORDER = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK,
                 ADVISORY_CHECK, QUERY_CHECK, AUDITABILITY_CHECK]

# The model's answer: two of the six named, the last of them first.
# `merge_monotonically` moves those two up and appends the rest in plan order.
REORDERING_REPLY = json.dumps({"order": [TAINT_CHECK, PERMISSION_CHECK]})
REORDERED = [TAINT_CHECK, PERMISSION_CHECK, SUPPLY_CHAIN_CHECK,
             ADVISORY_CHECK, QUERY_CHECK, AUDITABILITY_CHECK]

# A reply naming one check and no other: the shape a subtraction would arrive
# in, since the model is answering with a strict subset of the plan.
SUBSET_REPLY = json.dumps({"order": [AUDITABILITY_CHECK]})

# What the two static checks report on this app: one over-privileged tool and
# one package used but never declared.
EXPECTED_FINDINGS = 2


def audit(repo: Path, ask=None, probe_model: dict | None = None) -> tuple[dict, dict]:
    """Write the app into `repo` and audit it with whatever model the test offers.

    Returns both documents, which is what `build_findings` hands back: the
    findings, and the record of what ordered the checks that produced them.
    """
    repo.mkdir(parents=True, exist_ok=True)
    (repo / APP_FILE).write_text(APP_SOURCE, encoding="utf-8")
    return build_findings(str(repo), SURFACES, MAPPING, ADVISORIES,
                          STUB_ADVISORY_PIN, ask, probe_model)

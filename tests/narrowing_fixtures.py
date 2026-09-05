"""One app the planner can narrow a check on, and the audit calls two test files share.

`tests/checks/test_narrowed_run.py` asks what a narrowing costs and what it must
not change; `tests/checks/test_narrowing_join.py` asks whether the two artifacts
still agree about it. Both need the same app, so it is spelled once here.

Three properties of the app are load-bearing.

**Two privileged tools**, so narrowing the permission check to one of them is
exactly one finding fewer -- a difference a count can see.

**Two advisory-carrying components**, one reached by a surface and one not, so
`advisory_unreached_component_count` is `1` rather than `0`. A narrowed run must
leave it at `1`: that number is the other side of the ledger rule 4 exists to
keep balanced, and against `0` the assertion would hold whatever happened.

**No agent definition**, so `agent_defined_without_callback_handler` is
narrowable and still absent from `checks_run` -- which is the state a model can
name and the audit has to survive.

Everything is written into `tmp_path` and the model is a stand-in. A synthetic
tree is weaker than a real one: the surfaces are stated by hand rather than
extracted, so no oversized file, no unreadable encoding and no code shape nobody
foresaw is covered here.
"""

import json
from pathlib import Path

from advisory_fixtures import ADVISORY_PURL, advisory_record
from artifacts.mapping import MAPPING_REASONS, THIRD_PARTY, USED_BUT_UNDECLARED
from artifacts.surface import DATA_SOURCE, TOOL_CALL, Surface
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.run_checks import build_findings
from cli_helpers import STUB_ADVISORY_PIN
from parsing.languages import PYTHON
from planner_app_fixtures import APP_FILE, APP_SOURCE
from semantic_probe_fixtures import PROBE_MODEL, Answering

# Two privileged tools, so narrowing to one is one finding fewer, and one data
# source carrying the component the advisory check joins on.
SHELL = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")
REPL = Surface(TOOL_CALL, "PythonREPLTool", "agent.py", 20, PYTHON, "tool", "langchain.tools")
DATA = Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")
SURFACES = [SHELL, REPL, DATA]
EVERY_SURFACE = 3

# One reached component, joined to the data surface by its purl, and one
# undeclared package for the supply-chain check to report.
UNREACHED_PURL = "pkg:pypi/lonely@1.0.0"
MAPPING = {
    "entries": [
        {"surface_id": DATA.id, "reason": THIRD_PARTY,
         "component_name": "langchain", "purl": ADVISORY_PURL},
        {"surface_id": SHELL.id, "reason": USED_BUT_UNDECLARED,
         "component_name": "pyyaml"},
    ],
    "reason_counts": {reason: 0 for reason in MAPPING_REASONS}
    | {THIRD_PARTY: 1, USED_BUT_UNDECLARED: 1},
}

# Two advisory-carrying components: one a surface reaches, one nothing does.
# The second is the ledger's other side, and its count must survive a narrowing.
ADVISORIES = {ADVISORY_PURL: [advisory_record()],
              UNREACHED_PURL: [advisory_record("CVE-2024-0002")]}
UNREACHED_COMPONENTS = 1

# What the app reports with nothing narrowed: one finding per privileged tool,
# one undeclared package, one reachable advisory.
FULL_FINDINGS = 4
NARROWED_FINDINGS = 3

# A narrowable check with no subject on this app: nothing here defines an agent,
# so `_checks_that_examined_something` never plans it and it is never in
# `checks_run`.
UNPLANNED_CHECK = AUDITABILITY_CHECK


def narrowing_reply(check: str, surface_ids: list[str]) -> str:
    """The reply shape the planner prompt asks for, carrying one narrowing."""
    return json.dumps({"surfaces": {check: surface_ids}})


def audit(repo: Path, reply: str | None = None) -> tuple[dict, dict]:
    """Write the app into `repo` and audit it, optionally with a model that narrows."""
    repo.mkdir(parents=True, exist_ok=True)
    (repo / APP_FILE).write_text(APP_SOURCE, encoding="utf-8")
    ask = Answering(reply) if reply is not None else None
    return build_findings(str(repo), SURFACES, MAPPING, ADVISORIES, STUB_ADVISORY_PIN,
                          ask, PROBE_MODEL if reply is not None else None)


def narrowed_audit(repo: Path) -> tuple[dict, dict]:
    """Audit with the permission check narrowed to one of the two privileged tools."""
    return audit(repo, narrowing_reply(PERMISSION_CHECK, [SHELL.id]))

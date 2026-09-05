"""Which checks the planner names for an app, and which it leaves out entirely.

The two narrowest checks are scoped by what the app is, not by what it contains:
the query check is planned only where a model is driven at all, and the
auditability check only where an agent that takes actions is built. Both
gates matter because `coverage.checks_run` is read as a claim -- a check named
there and silent looked and cleared its subjects, so a check that could not
look must be *absent* rather than silent, or `src/evaluation/scorer.py` reads a
gap as a clean result.

Each gate is shown twice over the same defect: once on an app the check is
planned for, so the reader knows it bites, and once on an app it is not, where
absence is the assertion. The pair is the whole point -- an absence test alone
would pass over a check that never worked.

The auditability gate narrows twice over, so it is shown three ways: an agent is
built, only a model is called, and the only agent is TypeScript -- which the check
cannot read, because it parses `.py`. The same narrowing asserted on
`has_agent_surface` itself is in `test_auditability_subjects.py`.

Split out of `test_run_checks.py`, which owns how the document is assembled;
this file owns only which checks were planned.
"""

from pathlib import Path

from artifacts.surface import AGENT_DEF, DATA_SOURCE, TOOL_CALL, Surface
from checks import auditability, output_handling
from checks.run_checks import build_findings
from parsing.extractor import extract_repo
from parsing.languages import PYTHON, TYPESCRIPT

# A tool the model can call, which is what makes an app one that drives a model.
TOOL_SURFACE = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")


# --- the query check is scoped to apps that drive a model -------------------

# One query built by interpolation, with the surface the Python detector reports
# for it. The same file is audited twice, so the only thing that differs between
# the two runs is whether the app drives a model at all.
QUERY_FILE = "db.py"
QUERY_LINE = 2
QUERY_SOURCE = '''def read(cursor, user_id):
    cursor.execute(f"SELECT * FROM t WHERE id = '{user_id}'")
'''
QUERY_SURFACE = Surface(DATA_SOURCE, "cursor.execute", QUERY_FILE, QUERY_LINE,
                        PYTHON, "database query")


def audit_the_app_with_a_query(tmp_path: Path, surfaces: list) -> dict:
    """Audit one app holding a query built by interpolation, with the given surfaces."""
    (tmp_path / QUERY_FILE).write_text(QUERY_SOURCE, encoding="utf-8")
    document, _planner_document = build_findings(str(tmp_path), surfaces, None)
    return document


def test_the_query_check_runs_on_an_app_that_drives_a_model(tmp_path) -> None:
    """Python to read and a tool the model can call: the check had a subject and looked."""
    coverage = audit_the_app_with_a_query(
        tmp_path, [TOOL_SURFACE, QUERY_SURFACE])["coverage"]
    assert output_handling.CHECK_NAME in coverage["checks_run"]
    assert output_handling.OWASP_ID in coverage["risk_classes_checked"]


def test_the_interpolated_query_reaches_the_document(tmp_path) -> None:
    """The guard for the scope test below: on this tree the check does report something."""
    document = audit_the_app_with_a_query(tmp_path, [TOOL_SURFACE, QUERY_SURFACE])
    reported = [(f["rule_id"], f["file"], f["line"]) for f in document["findings"]]
    assert (output_handling.CHECK_NAME, QUERY_FILE, QUERY_LINE) in reported


def test_the_query_check_is_absent_from_an_app_that_drives_no_model(tmp_path) -> None:
    """Same file, same defect, no agent or tool: this rule is CWE-89 with an LLM filter.

    Dropping the filter would report a finding on every plain Python service
    with a database, which is what the published "0 findings on a repo with no
    LLM surface" result rests on. Absent, not silent: LLM02 was not examined.
    """
    coverage = audit_the_app_with_a_query(tmp_path, [QUERY_SURFACE])["coverage"]
    assert output_handling.CHECK_NAME not in coverage["checks_run"]
    assert output_handling.OWASP_ID not in coverage["risk_classes_checked"]


def test_an_app_that_drives_no_model_reports_no_query_finding(tmp_path) -> None:
    """The other half of the gate: a check that never ran can report nothing."""
    document = audit_the_app_with_a_query(tmp_path, [QUERY_SURFACE])
    assert document["findings"] == []


# --- the auditability check is scoped to apps that build an agent -----------

AGENT_FILE = "build.py"
AGENT_LINE = 2
AGENT_SOURCE = '''def build(tools):
    return AgentExecutor.from_agent_and_tools(agent=None, tools=tools)
'''
BUILT_AGENT_SURFACE = Surface(AGENT_DEF, "AgentExecutor.from_agent_and_tools",
                              AGENT_FILE, AGENT_LINE, PYTHON, "agent")

# The same app shape with an `AGENT_DEF` surface built by a name outside
# `AGENT_FACTORIES`. The extractor really does report `ChatOpenAI` as
# `AGENT_DEF`, asserted in `test_auditability_subjects.py`, so this is the line
# drawn inside one kind rather than a surface of another kind standing in.
MODEL_FILE = "chat.py"
MODEL_SOURCE = 'model = ChatOpenAI(model="gpt-4o-mini")\n'
MODEL_CLIENT_SURFACE = Surface(AGENT_DEF, "ChatOpenAI", MODEL_FILE, 1, PYTHON,
                               "model client")


def audit_the_app_that_builds_an_agent(tmp_path: Path) -> dict:
    """Audit one app whose agent is constructed with no callback argument."""
    (tmp_path / AGENT_FILE).write_text(AGENT_SOURCE, encoding="utf-8")
    document, _planner_document = build_findings(str(tmp_path), [BUILT_AGENT_SURFACE], None)
    return document


def audit_the_app_that_only_calls_a_model(tmp_path: Path) -> dict:
    """Audit one app that instantiates a model client and builds no agent."""
    (tmp_path / MODEL_FILE).write_text(MODEL_SOURCE, encoding="utf-8")
    document, _planner_document = build_findings(str(tmp_path), [MODEL_CLIENT_SURFACE], None)
    return document


def test_the_auditability_check_runs_on_an_app_that_builds_an_agent(tmp_path) -> None:
    """Python to read and an agent that takes actions: the check had a subject and looked."""
    coverage = audit_the_app_that_builds_an_agent(tmp_path)["coverage"]
    assert auditability.CHECK_NAME in coverage["checks_run"]
    assert auditability.OWASP_ID in coverage["risk_classes_checked"]


def test_the_unhandled_agent_reaches_the_document(tmp_path) -> None:
    """The guard for the scope test below: on this tree the check does report something."""
    document = audit_the_app_that_builds_an_agent(tmp_path)
    reported = [(f["rule_id"], f["file"], f["line"]) for f in document["findings"]]
    assert reported == [(auditability.CHECK_NAME, AGENT_FILE, AGENT_LINE)]


def test_the_auditability_check_is_absent_from_an_app_that_builds_no_agent(tmp_path) -> None:
    """A bare model client is an LLM surface that takes no actions, so nothing was examined.

    `ChatOpenAI(...)` is an `AGENT_DEF` surface, so a check scoped to that kind
    alone would run here and report a clean bill on an app whose auditability
    was never in question. Absent, not silent: AUDITABILITY was not examined.
    """
    coverage = audit_the_app_that_only_calls_a_model(tmp_path)["coverage"]
    assert auditability.CHECK_NAME not in coverage["checks_run"]
    assert auditability.OWASP_ID not in coverage["risk_classes_checked"]


def test_an_app_that_builds_no_agent_reports_no_auditability_finding(tmp_path) -> None:
    """A bare model client reaches the document as no finding at all.

    Not a corollary of the gate above: `_unhandled_calls` records every call
    given no handler argument, so if `_is_auditable_agent` stopped naming
    `AGENT_FACTORIES` this app would report `ChatOpenAI` as an unaudited agent.
    The gate test above asserts the coverage block; this asserts the findings.
    """
    assert audit_the_app_that_only_calls_a_model(tmp_path)["findings"] == []


# --- and the auditability check reads Python, so a TypeScript agent is not --
# `detector_names_js.AGENT_FACTORIES` shares `AgentExecutor` with the Python set,
# so this app really does hand the gate an `AGENT_DEF` surface built by a name it
# knows. The inert Python file must exist: without it the check would be absent
# for want of any Python, and the test would prove nothing.
TYPESCRIPT_FILE = "graph.ts"
TYPESCRIPT_AGENT_LINE = 3
TYPESCRIPT_SOURCE = '''import { AgentExecutor } from "langchain/agents";

const agent = new AgentExecutor({ agent: null, tools: [] });
'''
INERT_PYTHON_FILE = "settings.py"
INERT_PYTHON_SOURCE = "TIMEOUT_SECONDS = 30\n"
TYPESCRIPT_AGENT_NAME = "AgentExecutor"


def surfaces_of_the_app_whose_only_agent_is_typescript(tmp_path: Path) -> list:
    """Write the inert Python file and the TypeScript agent, and detect their surfaces."""
    (tmp_path / INERT_PYTHON_FILE).write_text(INERT_PYTHON_SOURCE, encoding="utf-8")
    (tmp_path / TYPESCRIPT_FILE).write_text(TYPESCRIPT_SOURCE, encoding="utf-8")
    return extract_repo(str(tmp_path)).surfaces


def test_the_typescript_agent_really_is_a_detected_agent_surface(tmp_path) -> None:
    """Guard: an extractor reporting nothing for the `.ts` file would make the test below pass."""
    surfaces = surfaces_of_the_app_whose_only_agent_is_typescript(tmp_path)
    assert [(s.kind, s.name, s.line, s.language) for s in surfaces] == [
        (AGENT_DEF, TYPESCRIPT_AGENT_NAME, TYPESCRIPT_AGENT_LINE, TYPESCRIPT)]


def test_the_auditability_check_is_absent_from_an_app_whose_only_agent_is_typescript(
        tmp_path) -> None:
    """A TypeScript agent is a subject the check cannot read, so nothing was examined.

    `run_over_repo` walks Python files and parses them with `ast`, so this app
    has an agent surface and no construction site the check can read. The gate
    used to count it anyway: plan the check, read no TypeScript, and publish
    AUDITABILITY as examined with an empty finding list. Absent, not silent.
    """
    surfaces = surfaces_of_the_app_whose_only_agent_is_typescript(tmp_path)
    document, _planner_document = build_findings(str(tmp_path), surfaces, None)
    coverage = document["coverage"]
    assert auditability.CHECK_NAME not in coverage["checks_run"], (
        "a TypeScript agent satisfied the auditability gate, but the check reads "
        "Python only: the risk class is published as examined and the empty "
        "finding list reads as a clean result -- a blind spot, not a clean app")
    assert auditability.OWASP_ID not in coverage["risk_classes_checked"], (
        "AUDITABILITY is claimed as examined on an app whose only agent is in a "
        "language the check never parses, which the scorer reads as covered and clean")

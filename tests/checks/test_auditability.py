"""AUDITABILITY: which agent constructions are reported for having no handler attached.

The check establishes one structural fact -- no `callbacks=` or
`callback_manager=` was passed where the agent was built -- and every test here
is written against that fact rather than against "the agent's actions go
unrecorded", which the module's own docstring disclaims.

The boundary worth more than the happy path is the join, which is on the file,
the line *and* the full dotted name: two constructions can share a line, and
joining on the call root would let a handled one borrow an unhandled one's
verdict.

Which surfaces are subjects at all -- a Python agent, not a bare model client --
is a separate question, and lives in `test_auditability_subjects.py`; the same
narrowing seen through the coverage block is in `test_check_scope.py`.

Surfaces come from the real Python detector, so what a finding is anchored to
is what an audit would actually have had -- with one exception, the unparseable
file, which the detector records as a skip rather than a surface.

What this tree cannot show: it is written here, so it holds no oversized file,
no non-UTF-8 source and no framework idiom nobody foresaw.
"""

from pathlib import Path

from checks.auditability import CHECK_NAME, OWASP_ID, TITLE, run_over_repo
from parsing.extractor import extract_repo

APP_NAME = "auditability-app"
PYTHON_FILE = "app.py"
BROKEN_FILE = "bad.py"

# The line every single-construction source below builds its agent on.
AGENT_LINE = 3

# An agent built with nothing attached: the subject the check exists for.
UNHANDLED_AGENT = '''from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[])
'''

# The same construction with a handler passed, which is what silences it.
HANDLED_AGENT = '''from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[], callbacks=[handler])
'''

# The other spelling. Both names are in `HANDLER_ARGUMENTS`, and a name missing
# from it costs a false positive rather than silence.
MANAGED_AGENT = '''from langchain.agents import AgentExecutor

agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[], callback_manager=manager)
'''

# Two constructions on one line, sharing the call root `AgentExecutor`: one
# handled, one not. Joining on the root would report both.
TWO_AGENTS_ONE_LINE = '''from langchain.agents import AgentExecutor

pair = (AgentExecutor.from_agent_and_tools(agent=None), AgentExecutor(agent=None, callbacks=[cb]))
'''

# The dotted name of every unhandled construction above, and of the handled one
# sharing a line with it. Both have the call root `AgentExecutor`.
FACTORY_CALL_NAME = "AgentExecutor.from_agent_and_tools"
HANDLED_CALL_NAME = "AgentExecutor"

# An app that logs throughout and attaches nothing at the construction site.
# Line 6 is the agent.
LOGGING_APP = '''import logging
from langchain.agents import AgentExecutor

logger = logging.getLogger(__name__)
logger.info("building the agent")
agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[])
logger.info("the agent is built")
'''
LOGGING_APP_AGENT_LINE = 6

# Python the extractor already records in `surfaces.json`'s `skipped_files`.
BROKEN_SOURCE = "def oops(:\n"

def write_app(tmp_path: Path, source: str) -> Path:
    """Write one Python file into the repository and return its path."""
    repo = tmp_path / APP_NAME
    repo.mkdir(exist_ok=True)
    (repo / PYTHON_FILE).write_text(source, encoding="utf-8")
    return repo


def surfaces_of(tmp_path: Path, source: str) -> list:
    """Write one Python file and return the surfaces the detector reports for it."""
    return extract_repo(str(write_app(tmp_path, source))).surfaces


def audit_source(tmp_path: Path, source: str) -> list:
    """Write one Python file, extract its surfaces, and run the check over the tree."""
    repo = write_app(tmp_path, source)
    return run_over_repo(str(repo), extract_repo(str(repo)).surfaces)


def test_an_agent_built_with_no_handler_is_reported(tmp_path) -> None:
    """The one construction with nothing attached, anchored on its own line."""
    findings = audit_source(tmp_path, UNHANDLED_AGENT)
    assert [(f.file, f.line) for f in findings] == [(PYTHON_FILE, AGENT_LINE)]


def test_the_finding_names_its_check_its_risk_class_and_its_surface(tmp_path) -> None:
    """A located finding is only useful if it says what it is and what it is about."""
    finding = audit_source(tmp_path, UNHANDLED_AGENT)[0]
    assert (finding.rule_id, finding.owasp_id, finding.title) == (CHECK_NAME, OWASP_ID, TITLE)
    assert finding.surface_name == FACTORY_CALL_NAME


def test_an_agent_given_callbacks_is_not_reported(tmp_path) -> None:
    """`callbacks=` at the construction site is exactly what the check looks for."""
    assert audit_source(tmp_path, HANDLED_AGENT) == []


def test_an_agent_given_a_callback_manager_is_not_reported(tmp_path) -> None:
    """The second spelling silences it too, or the check reports on a keyword's name."""
    assert audit_source(tmp_path, MANAGED_AGENT) == []


def test_two_constructions_on_one_line_are_told_apart_by_their_full_name(tmp_path) -> None:
    """Same line, same call root, one handler between them: only the bare one is reported."""
    findings = audit_source(tmp_path, TWO_AGENTS_ONE_LINE)
    assert [(f.surface_name, f.line) for f in findings] == [(FACTORY_CALL_NAME, AGENT_LINE)]


def test_both_constructions_on_that_line_really_are_surfaces(tmp_path) -> None:
    """Guard on the join test: the handled one must exist for a wrong join to report it."""
    surfaces = surfaces_of(tmp_path, TWO_AGENTS_ONE_LINE)
    assert sorted(s.name for s in surfaces) == sorted([HANDLED_CALL_NAME, FACTORY_CALL_NAME])
    assert {s.line for s in surfaces} == {AGENT_LINE}


def test_an_app_that_logs_everywhere_is_still_reported(tmp_path) -> None:
    """The known false positive, pinned deliberately: this asserts the behaviour, not the ideal.

    The app imports `logging` and logs on both sides of the construction, so its
    agent's actions may well be recorded -- and the check reports it anyway,
    because nothing was attached where the agent was built. This is the same
    case measured on `RAG-Examples-with-Langchain`, and it is accepted rather
    than fixed: the alternative is a registry of blessed handler class names,
    which is the LangSmith name-matching this project already rejected. Read a
    finding here as "nothing was attached at the construction site".
    """
    findings = audit_source(tmp_path, LOGGING_APP)
    assert [(f.file, f.line) for f in findings] == [(PYTHON_FILE, LOGGING_APP_AGENT_LINE)]


def test_a_file_that_cannot_be_parsed_does_not_stop_the_run(tmp_path) -> None:
    """One unreadable file is already a recorded skip; it must not cost the rest of the audit."""
    repo = tmp_path / APP_NAME
    repo.mkdir()
    (repo / BROKEN_FILE).write_text(BROKEN_SOURCE, encoding="utf-8")
    findings = audit_source(tmp_path, UNHANDLED_AGENT)
    assert [(f.file, f.line) for f in findings] == [(PYTHON_FILE, AGENT_LINE)]


def test_a_repository_with_no_python_reports_nothing(tmp_path) -> None:
    """Nothing to read is a clean result, not an error."""
    assert run_over_repo(str(tmp_path), []) == []

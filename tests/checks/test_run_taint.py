"""Which files the taint trace reads, and how its results reach findings.json.

The trace itself is tested in test_taint.py. What is tested here is the step
around it: it re-reads each file from disk, it is Python-only because it needs
an `ast` tree, and both halves of its answer -- the findings and the gaps it
could not follow -- have to survive assembly into the document.

Being Python-only is what `coverage.checks_run` has to carry: the check is
named when a Python file gave it something to read, and left out when the app
is JavaScript, where naming it would claim a clean result it never reached.
"""

from pathlib import Path

from artifacts.finding import INCONCLUSIVE
from artifacts.surface import AGENT_DEF, DATA_SOURCE, Surface
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.run_checks import build_findings
from checks.taint import run_over_repo
from checks.taint import CHECK_NAME, LEFT_THE_FILE
from parsing.languages import JAVASCRIPT, PYTHON

PYTHON_FILE = "app.py"
JS_FILE = "app.js"

# One source, one sink and the call between them: the same shape in both
# languages, so the only difference the test can be measuring is the language.
TRACED_SOURCE = '''if prompt := st.chat_input("ask"):
    executor = AgentExecutor.from_agent_and_tools(tools=tools)
    response = executor(prompt)
'''

# A source whose value is never bound to a name, which the trace cannot follow.
UNBOUND_SOURCE = 'st.chat_input("ask")\n'

# Python holding nothing the trace can follow: a file it read and cleared.
CLEAN_SOURCE = "greeting = 'hello'\n"

# Python the extractor already recorded as unparseable in surfaces.json.
BROKEN_SOURCE = "def oops(:\n"


def surfaces_in(file: str, language: str) -> list[Surface]:
    """The source and sink the extractor would have reported for TRACED_SOURCE."""
    return [
        Surface(DATA_SOURCE, "st.chat_input", file, 1, language, "user input"),
        Surface(AGENT_DEF, "AgentExecutor.from_agent_and_tools", file, 2, language, "agent"),
    ]


def repo_with(tmp_path: Path, file: str, source: str) -> str:
    """Write one file into an empty repository and return its path."""
    (tmp_path / file).write_text(source, encoding="utf-8")
    return str(tmp_path)


def test_a_python_file_is_traced(tmp_path) -> None:
    """The Python path is the one that works, so the rest of this file means something."""
    repo = repo_with(tmp_path, PYTHON_FILE, TRACED_SOURCE)
    findings, _ = run_over_repo(repo, surfaces_in(PYTHON_FILE, PYTHON))
    assert [(f.rule_id, f.file, f.line) for f in findings] == [(CHECK_NAME, PYTHON_FILE, 1)]


def test_a_javascript_file_is_not_traced(tmp_path) -> None:
    """The trace reads an `ast` tree, so a JS app's clean result is not a traced one."""
    repo = repo_with(tmp_path, JS_FILE, TRACED_SOURCE)
    assert run_over_repo(repo, surfaces_in(JS_FILE, JAVASCRIPT)) == ([], [])


def test_the_traced_finding_reaches_the_document(tmp_path) -> None:
    """A finding that does not survive assembly was never found as far as Phase 4 is concerned.

    Two rule ids, not one: the agent on line 2 is built with no `callbacks=`,
    so the auditability check reports it as well. Asserting the taint id alone
    would be asserting less than this tree actually produces.
    """
    repo = repo_with(tmp_path, PYTHON_FILE, TRACED_SOURCE)
    document, _planner_document = build_findings(repo, surfaces_in(PYTHON_FILE, PYTHON), None)
    assert [f["rule_id"] for f in document["findings"]] == [CHECK_NAME, AUDITABILITY_CHECK]


def test_the_unfollowed_trace_reaches_the_document(tmp_path) -> None:
    """The gap is carried too, or a short findings list reads as a clean bill."""
    repo = repo_with(tmp_path, PYTHON_FILE, UNBOUND_SOURCE)
    surfaces = [surfaces_in(PYTHON_FILE, PYTHON)[0]]
    document, _planner_document = build_findings(repo, surfaces, None)
    assert document["finding_count"] == 0
    assert document["probe_count"] == 1


def test_the_probe_in_the_document_says_why_it_concluded_nothing(tmp_path) -> None:
    """`inconclusive` plus a reason from the vocabulary: we could not look, not nothing there."""
    repo = repo_with(tmp_path, PYTHON_FILE, UNBOUND_SOURCE)
    document, _planner_document = build_findings(
        repo, [surfaces_in(PYTHON_FILE, PYTHON)[0]], None)
    probe = document["probes"][0]
    assert (probe["outcome"], probe["reason"]) == (INCONCLUSIVE, LEFT_THE_FILE)
    assert probe["probe_name"] == CHECK_NAME


def test_a_repository_with_no_source_files_traces_nothing(tmp_path) -> None:
    """Nothing to read is a clean result, not an error."""
    assert run_over_repo(str(tmp_path), []) == ([], [])


def test_the_check_is_named_in_coverage_when_it_had_a_file_to_read(tmp_path) -> None:
    """A Python file with nothing to trace is a file it cleared, and coverage says so."""
    repo = repo_with(tmp_path, PYTHON_FILE, CLEAN_SOURCE)
    document, _planner_document = build_findings(repo, [], None)
    assert (document["finding_count"], document["probe_count"]) == (0, 0)
    assert CHECK_NAME in document["coverage"]["checks_run"]


def test_a_javascript_app_leaves_the_check_out_of_coverage(tmp_path) -> None:
    """Nothing here was traced, so its silence must not read as a clean result."""
    repo = repo_with(tmp_path, JS_FILE, TRACED_SOURCE)
    surfaces = surfaces_in(JS_FILE, JAVASCRIPT)
    document, _planner_document = build_findings(repo, surfaces, None)
    checks_run = document["coverage"]["checks_run"]
    assert CHECK_NAME not in checks_run
    assert PERMISSION_CHECK in checks_run


def test_a_file_the_extractor_could_not_parse_does_not_stop_the_run(tmp_path) -> None:
    """An unparseable file is already recorded as a skip; the trace must step over it.

    The extractor reports it in `surfaces.json`'s `skipped_files` and carries on,
    so a whole audit cannot be lost to one bad file downstream of that.
    """
    (tmp_path / PYTHON_FILE).write_text(TRACED_SOURCE, encoding="utf-8")
    repo = repo_with(tmp_path, "bad.py", BROKEN_SOURCE)
    findings, _ = run_over_repo(repo, surfaces_in(PYTHON_FILE, PYTHON))
    assert [f.file for f in findings] == [PYTHON_FILE]

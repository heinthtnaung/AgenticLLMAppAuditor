"""What the LLM01 trace really produces on the vulnerable corpus app.

One value is followed all the way: `prompt := st.chat_input(...)` on line 60,
handed to the `AgentExecutor` bound on line 71. Nine more data sources are not,
because the file never binds their value to a name -- and those are recorded as
inconclusive probes rather than dropped, so the two findings this app yields
cannot be read as the whole story.
"""

from artifacts.finding import INCONCLUSIVE, STATIC
from artifacts.surface import DATA_SOURCE
from checks.taint import CHECK_NAME as TAINT_CHECK
from checks.taint import LEFT_THE_FILE, OWASP_ID
from dependency_fixtures import LANGGRAPHJS_STARTER, SUPPORT_AGENT, corpus_sbom, js_sbom
from findings_fixtures import corpus_findings

# The one trace that completes: the walrus-bound prompt reaching the executor.
TRACED_SURFACE_ID = "main.py:60:DATA_SOURCE:st.chat_input"

# Every data source whose value the app never binds to a name, read off the
# files by hand: (file, line, name).
UNFOLLOWED_SOURCES = (
    ("transaction_db.py", 14, "cursor.execute"),
    ("transaction_db.py", 22, "cursor.execute"),
    ("transaction_db.py", 44, "cursor.executemany"),
    ("transaction_db.py", 56, "cursor.executemany"),
    ("transaction_db.py", 62, "cursor.execute"),
    ("transaction_db.py", 63, "cursor.fetchall"),
    ("transaction_db.py", 76, "cursor.execute"),
    ("utils.py", 51, "open"),
    ("utils.py", 74, "open"),
)

UNFOLLOWED_SURFACE_IDS = {
    f"{file}:{line}:{DATA_SOURCE}:{name}" for file, line, name in UNFOLLOWED_SOURCES
}


def support_agent_document() -> dict:
    """Build the vulnerable Python app's whole findings document."""
    return corpus_findings(SUPPORT_AGENT, corpus_sbom())


def traced_findings() -> list[dict]:
    """Return only the findings the LLM01 trace produced."""
    return [f for f in support_agent_document()["findings"] if f["rule_id"] == TAINT_CHECK]


def test_the_trace_produces_exactly_one_finding() -> None:
    """One value is followed from entry to the model; the rest stop short."""
    assert len(traced_findings()) == 1


def test_the_finding_is_anchored_on_the_chat_input_source() -> None:
    """Line 60, where the untrusted value enters -- not line 71, where it is consumed."""
    finding = traced_findings()[0]
    assert finding["surface_id"] == TRACED_SURFACE_ID
    assert (finding["file"], finding["line"]) == ("main.py", 60)
    assert (finding["surface_kind"], finding["surface_name"]) == (DATA_SOURCE, "st.chat_input")


def test_the_finding_is_llm01_and_static() -> None:
    """Prompt injection, in the 2025 list, reached by reading the code and nothing else."""
    finding = traced_findings()[0]
    assert finding["owasp_id"] == OWASP_ID == "LLM01"
    assert finding["detection"] == STATIC and finding["probe_id"] is None


def test_the_traced_source_leaves_no_probe() -> None:
    """It was followed to a conclusion, so it is a finding rather than a gap."""
    subjects = {probe["subject_id"] for probe in support_agent_document()["probes"]}
    assert TRACED_SURFACE_ID not in subjects


def test_every_source_the_trace_could_not_follow_is_recorded() -> None:
    """Nine sources are never bound to a name, and each one is named in the document."""
    probes = support_agent_document()["probes"]
    assert {probe["subject_id"] for probe in probes} == UNFOLLOWED_SURFACE_IDS
    assert len(probes) == len(UNFOLLOWED_SOURCES)


def test_each_unfollowed_source_says_it_concluded_nothing() -> None:
    """`inconclusive` with a reason: we could not look, not we looked and found nothing."""
    for probe in support_agent_document()["probes"]:
        assert (probe["outcome"], probe["reason"]) == (INCONCLUSIVE, LEFT_THE_FILE)
        assert probe["probe_name"] == TAINT_CHECK


def test_the_graded_sql_source_is_among_the_gaps_rather_than_missed_silently() -> None:
    """VULN1-04's `cursor.execute` is not found, and the document says why it was not."""
    subjects = {probe["subject_id"] for probe in support_agent_document()["probes"]}
    assert f"transaction_db.py:62:{DATA_SOURCE}:cursor.execute" in subjects


def test_the_javascript_fixture_is_not_traced_at_all() -> None:
    """The trace reads an `ast` tree, so this app's silence is untraced, not traced clean."""
    document = corpus_findings(LANGGRAPHJS_STARTER, js_sbom())
    assert document["probes"] == []
    assert [f for f in document["findings"] if f["rule_id"] == TAINT_CHECK] == []

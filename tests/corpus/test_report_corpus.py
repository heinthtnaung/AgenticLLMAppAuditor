"""The report rendered from the two fixtures rendered here, findings and gaps alike.

Every other report test builds its own document. These two are the real thing:
the surfaces the extractor found and the findings the checks produced, rendered
as a person would read them. The clean fixture is the case that matters --
zero findings is exactly the report that gets misread as a pass.
"""

import json

from artifacts.surface import surfaces_to_json
from conftest import app_path
from dependency_fixtures import LANGGRAPHJS_STARTER, SUPPORT_AGENT, corpus_sbom, js_sbom
from findings_fixtures import corpus_findings
from parsing.extractor import extract_repo
from report import NOTHING_FOUND, render
from report_fixtures import findings_section, not_examined_section

# Verified by hand against the fixture at its pinned commit: seven database
# calls and two file reads the trace could not follow out of their file.
SUPPORT_AGENT_UNFOLLOWED = 9

# The mapping's `unresolved` reason on the same fixture: eight of its nineteen
# surfaces name no package the resolver could identify. Not `unmapped_count`,
# which is thirteen because it also counts stdlib and first-party answers.
SUPPORT_AGENT_UNTRACEABLE = 8

# The sentence the report prints for those surfaces, matched without its count
# so the clean fixture's assertion cannot pass on a different number.
UNTRACEABLE_LINE = "could not be traced to a component"


def render_corpus_report(app: str, sbom: dict) -> str:
    """Render one corpus app's report from its real surfaces and its real findings."""
    document = corpus_findings(app, sbom)
    scan = extract_repo(str(app_path(app)))
    surfaces = json.loads(surfaces_to_json(scan.surfaces, scan.skipped))
    return render(app, document, surfaces)


def support_agent_report() -> str:
    """The vulnerable Python fixture's report."""
    return render_corpus_report(SUPPORT_AGENT, corpus_sbom())


def clean_fixture_report() -> str:
    """The JavaScript fixture whose grading key claims it is clean."""
    return render_corpus_report(LANGGRAPHJS_STARTER, js_sbom())


def test_the_clean_fixtures_report_warns_against_reading_it_as_a_pass() -> None:
    """Zero findings on a real app is the exact report that gets misread."""
    assert NOTHING_FOUND in findings_section(clean_fixture_report())


def test_the_clean_fixtures_report_names_the_risk_no_check_could_cover() -> None:
    """The taint trace reads Python, so it never looked at this app for LLM01."""
    assert "LLM01 (Prompt injection)" in not_examined_section(clean_fixture_report())


def test_the_vulnerable_fixtures_report_sends_a_reader_to_the_undeclared_package() -> None:
    """The graded LLM03: the package, the line it is reached through, and why it was mapped."""
    section = findings_section(support_agent_report())
    assert "### LLM03 — Package used but never declared as a direct dependency" in section
    assert "- **Where**: `utils.py:75`" in section
    assert "- **Component**: `pyyaml`" in section


def test_the_vulnerable_fixtures_report_sends_a_reader_to_the_untrusted_input() -> None:
    """The graded LLM01: the chat input the app hands to the model unchecked."""
    section = findings_section(support_agent_report())
    assert "### LLM01 — Untrusted input reaches the model without validation" in section
    assert "- **Where**: `main.py:60`" in section


def test_the_vulnerable_fixtures_report_lists_every_trace_it_could_not_follow() -> None:
    """Two findings beside nine unfollowed traces is the honest shape of this audit."""
    section = not_examined_section(support_agent_report())
    assert f"**{SUPPORT_AGENT_UNFOLLOWED} traces could not be followed.**" in section
    assert "- `transaction_db.py:14:DATA_SOURCE:cursor.execute` — the value was not bound " \
        "to a name in this file (`trace_left_static_analysis`)" in section
    assert section.count("(`trace_left_static_analysis`)") == SUPPORT_AGENT_UNFOLLOWED


def test_the_vulnerable_fixtures_report_names_the_risks_no_check_covered() -> None:
    """Three checks ran; two of the five risk classes still had nothing behind them."""
    section = not_examined_section(support_agent_report())
    assert "AUDITABILITY (Inadequate auditability of agent actions)" in section
    assert "LLM02 (Insecure output handling)" in section
    assert "LLM01 (Prompt injection)" not in section


def test_the_vulnerable_fixtures_report_states_how_many_surfaces_have_no_component() -> None:
    """Eight surfaces the supply-chain check could say nothing about, named rather than omitted."""
    section = not_examined_section(support_agent_report())
    assert f"**{SUPPORT_AGENT_UNTRACEABLE} surfaces {UNTRACEABLE_LINE}**" in section


def test_the_clean_fixtures_report_carries_no_untraceable_surface_line() -> None:
    """Every surface there resolved, so printing the gap line would invent a gap."""
    assert UNTRACEABLE_LINE not in clean_fixture_report()

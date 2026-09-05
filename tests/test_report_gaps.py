"""The report's "what was not examined" section: the safety-critical half.

A findings list read on its own is read as a bill of health. These tests hold
the four gaps a reader has no other way to learn about -- risk classes with no
check behind them, files nobody could parse, surfaces no component could be
found for, and advisory data that was never ingested -- and check that each
line is earned rather than printed regardless.
"""

import pytest

from artifacts.finding import INCONCLUSIVE, NOT_RUN, OWASP_IDS
from artifacts.findings_document import ADVISORY_NOT_INGESTED, ADVISORY_SNAPSHOT
from artifacts.skipped_file import UNDECODABLE_BYTES, UNPARSEABLE_SYNTAX, SkippedFile
from checks.taint import LEFT_THE_FILE
from findings_fixtures import OWASP_ID, build_document, confirmed_probe, probe_finding
from reporting.report import RISK_TITLES, render
from report_fixtures import (
    APP,
    UNREADABLE,
    document_with_coverage,
    not_examined_section,
    surfaces_document,
    unresolved_probe,
)


def gaps(findings_document: dict, skipped=()) -> str:
    """Render the report and return only its gap list."""
    return not_examined_section(render(APP, findings_document, surfaces_document(skipped)))


# --- Risk classes no check covered -----------------------------------------

def test_a_risk_class_with_no_check_behind_it_is_named_with_its_title() -> None:
    """Silence about an unchecked risk must not read as silence about an absent one."""
    section = gaps(document_with_coverage(risk_classes=[OWASP_ID]))
    assert "**No check covers these risks**" in section
    assert "LLM01 (Prompt injection)" in section


def test_a_risk_class_a_check_did_cover_is_left_out_of_that_line() -> None:
    """Naming a covered risk as uncovered would understate the audit and mislead too."""
    section = gaps(document_with_coverage(risk_classes=[OWASP_ID]))
    assert f"{OWASP_ID} ({RISK_TITLES[OWASP_ID]})" not in section


def test_every_risk_class_covered_drops_the_no_check_line() -> None:
    """The warning is earned, not boilerplate: a full run must not carry it."""
    assert "No check covers these risks" not in gaps(
        document_with_coverage(risk_classes=list(OWASP_IDS)))


# --- Files the scan could not read -----------------------------------------

def test_an_unreadable_file_is_named_with_the_reason_it_was_skipped() -> None:
    """A surface in a file nobody could parse is absent from the report, not from the app."""
    section = gaps(build_document([]), [UNREADABLE])
    assert "could not be read" in section
    assert f"- `{UNREADABLE.file}` — {UNPARSEABLE_SYNTAX}" in section


def test_every_unreadable_file_is_listed_and_not_only_counted() -> None:
    """One name and a count would hide the other file; a reader needs both names."""
    second = SkippedFile("app/notes.py", UNDECODABLE_BYTES)
    section = gaps(build_document([]), [UNREADABLE, second])
    assert "**2 files could not be read**" in section
    assert f"- `{UNREADABLE.file}` — {UNPARSEABLE_SYNTAX}" in section
    assert f"- `{second.file}` — {UNDECODABLE_BYTES}" in section


def test_a_scan_that_read_everything_says_so_rather_than_saying_nothing() -> None:
    """An empty skip list is a claim worth stating, not a section to omit."""
    assert "Every source file was read." in gaps(build_document([]))


# --- Traces that reached no conclusion -------------------------------------

@pytest.mark.parametrize("outcome", (INCONCLUSIVE, NOT_RUN))
def test_a_probe_that_concluded_nothing_is_reported_as_a_trace_not_followed(
        outcome: str) -> None:
    """"We could not follow it" and "nothing reaches the model" are different answers."""
    probe = unresolved_probe(outcome)
    section = gaps(build_document([], [probe]))
    assert "could not be followed" in section
    assert f"- `{probe.subject_id}` — {probe.detail} (`{LEFT_THE_FILE}`)" in section


def test_a_probe_that_confirmed_something_is_not_listed_as_a_gap() -> None:
    """A probe that reached a conclusion examined its subject, so it is no omission."""
    probe = confirmed_probe()
    section = gaps(build_document([probe_finding(probe)], [probe]))
    assert "could not be followed" not in section


# --- Surfaces with no component behind them --------------------------------

def test_surfaces_the_mapping_could_not_trace_are_counted_as_a_gap() -> None:
    """The supply-chain check had no component to examine for them, and silence would hide that."""
    section = gaps(document_with_coverage(unresolved=2))
    assert "**2 surfaces could not be traced to a component**" in section


def test_a_mapping_that_traced_everything_drops_the_untraceable_line() -> None:
    """Zero is a result the mapping reached, not a gap to warn about."""
    assert "could not be traced to a component" not in gaps(document_with_coverage(unresolved=0))


def test_no_mapping_at_all_drops_the_untraceable_line_too() -> None:
    """Null is no count to print; that run's gap is that no check covered LLM03 at all."""
    section = gaps(document_with_coverage(unresolved=None))
    assert "could not be traced to a component" not in section
    assert "**No check covers these risks**" in section
    assert "LLM03 (Supply chain)" in section


# --- Advisory data ---------------------------------------------------------

def test_absent_advisory_data_is_stated_so_a_named_package_is_not_read_as_vetted() -> None:
    """Advisory ingestion has not landed, and a supply-chain finding must not imply it has."""
    section = gaps(document_with_coverage(advisory=ADVISORY_NOT_INGESTED))
    assert "**No advisory data was read**" in section


def test_an_advisory_snapshot_drops_the_no_advisory_data_line() -> None:
    """The line reports the real state of the run; it is not printed unconditionally."""
    section = gaps(document_with_coverage(advisory=ADVISORY_SNAPSHOT))
    assert "No advisory data was read" not in section


def test_every_risk_in_the_vocabulary_has_a_title_to_render() -> None:
    """A new OWASP id without a title here would render as a bare code in the gap list."""
    assert set(RISK_TITLES) == set(OWASP_IDS)

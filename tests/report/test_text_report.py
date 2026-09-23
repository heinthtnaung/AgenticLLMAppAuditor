"""Guards on the page: what it leads with, what it shouts, and what it never leaves out."""

import pytest

from report.record import (
    CouncilAssessment,
    CouncilWithoutVector,
    RunProvenance,
    UnknownAdvisoryDatabase,
    build_report,
)
from report.text_report import as_text
from report_samples import (
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    TOTAL_LOSS,
    catalogue,
    component,
    finding,
    unidentified,
)

TERMINAL_WIDTH = 100
DJANGO = component()
PYYAML = component("pyyaml", "5.1")


def rendered(findings=(), components=(DJANGO,), provenance=PROVENANCE, unidentified=(), council=()):
    """Render one report from whatever a test is about."""
    found = catalogue(*components, unidentified=unidentified)
    return as_text(build_report(provenance, found, findings, {}, council))


def lines_under(heading: str, text: str) -> list[str]:
    """Give the indented lines of one section, so a test can read its order."""
    after = text.split(heading)[1].split("\n\n")[0]
    return [line for line in after.split("\n") if line.startswith("  ")]


def test_the_two_kinds_of_nothing_are_counted_apart():
    text = rendered(components=(DJANGO, PYYAML))
    assert "2 components carry no advisory" in text
    assert "0 advisories matched no component" in text


@pytest.mark.parametrize(
    "named", ["Organisation Risk Score", "Approval record", "Council ruling"]
)
def test_what_was_not_assessed_is_printed_rather_than_left_out(named):
    assert named in rendered()


def test_a_run_that_could_not_read_a_database_says_so_loudly():
    blind = RunProvenance("r", "s", "t", UnknownAdvisoryDatabase("no metadata.json"))
    assert "NO ADVISORY DATABASE DATE: no metadata.json" in rendered(provenance=blind)


def test_a_run_that_read_one_says_when_it_was_built():
    assert "advisory database built 2026-09-22T02:00:05Z" in rendered()


def test_the_page_fits_a_terminal_and_carries_no_trailing_whitespace():
    text = rendered((
        finding(DJANGO, vectors={"a": TOTAL_LOSS, "b": LOW_CONFIDENTIALITY}),
        finding(PYYAML, advisory_id="GHSA-5p4m-2wfm-xmqj", vectors={"a": TOTAL_LOSS}),
    ))
    assert max(len(line) for line in text.split("\n")) <= TERMINAL_WIDTH
    assert all(line == line.rstrip() for line in text.split("\n"))


def test_the_same_record_renders_the_same_page():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    assert as_text(report) == as_text(report)


def test_artifacts_nothing_could_join_to_are_counted_and_named():
    text = rendered(unidentified=(unidentified(), unidentified("./other", "github-action")))
    assert "COULD NOT BE IDENTIFIED (2)" in text
    assert "./local-action" in text and "./other" in text


def test_a_run_where_everything_was_identified_says_nothing_about_it():
    assert "COULD NOT BE IDENTIFIED" not in rendered()


def test_a_run_with_no_council_shows_no_council_section_and_names_the_absence():
    text = rendered((finding(DJANGO),))
    assert "COUNCIL" not in text
    assert "no council assessed this run" in text


def test_a_council_that_settled_a_vector_says_so_with_the_vector():
    settled = CouncilAssessment("CVE-2019-14234", TOTAL_LOSS, single_assessor=False)
    text = rendered((finding(DJANGO),), council=(settled,))
    assert f"CVE-2019-14234  settled  ·  {TOTAL_LOSS}" in text
    assert "no council assessed this run" not in text


def test_a_council_that_ran_and_settled_nothing_is_not_read_as_no_council():
    # The bug this pins: the record said no council had run, which is a false
    # statement in an audit record and the likely outcome of any real run.
    open_still = CouncilWithoutVector("CVE-2019-14234", False, ("S",), ("AC",))
    text = rendered((finding(DJANGO),), council=(open_still,))
    assert "COUNCIL (1)" in text
    assert "no vector  ·  could not settle S, AC" in text
    assert "no council assessed this run" not in text


def test_the_three_council_states_read_differently():
    none_ran = rendered((finding(DJANGO),))
    settled = rendered((finding(DJANGO),), council=(CouncilAssessment("CVE-1", TOTAL_LOSS, False),))
    ran_open = rendered((finding(DJANGO),), council=(CouncilWithoutVector("CVE-1", False, ("S",)),))
    assert none_ran != settled != ran_open != none_ran

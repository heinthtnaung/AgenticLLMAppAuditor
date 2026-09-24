"""Guards on the page: what it leads with, what it shouts, and what it never leaves out."""

import pytest

from report.provenance import RunProvenance, UnknownAdvisoryDatabase
from council_runs import OPEN_TWO_WAYS, council_ran, council_states, passed_over_entirely
from full_runs import fully_assessed
from report.record import NO_COUNCIL_RUN, NOTHING_ABSENT, NOTHING_WAS_PUT_TO_IT, build_report
from report.text_report import as_text
from report_samples import (
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    REFUSED_DISSENT,
    TOTAL_LOSS,
    catalogue,
    component,
    finding,
    unidentified,
)

TERMINAL_WIDTH = 100
DJANGO = component()
PYYAML = component("pyyaml", "5.1")


def rendered(
    findings=(), components=(DJANGO,), provenance=PROVENANCE, unidentified=(), council=(),
    overridden=(),
):
    """Render one report from whatever a test is about."""
    found = catalogue(*components, unidentified=unidentified)
    return as_text(
        build_report(provenance, found, findings, {}, council, (), None, overridden)
    )


def lines_under(heading: str, text: str) -> list[str]:
    """Give the indented lines of one section, so a test can read its order."""
    after = text.split(heading)[1].split("\n\n")[0]
    return [line for line in after.split("\n") if line.startswith("  ")]


def test_a_dissent_only_a_refused_source_carries_is_not_counted_in_the_summary():
    # Accepted on purpose until it is decided whether a refused vector counts as a
    # dissent: CVE-2020-11023's ghsa disagrees and is not counted. Counting it turns
    # this red.
    text = rendered((finding(DJANGO, vectors=REFUSED_DISSENT),))
    assert "0 carry sources that disagree." in text


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
    text = rendered((finding(DJANGO),), council=(council_ran(),))
    assert f"CVE-2019-14234  settled  ·  {TOTAL_LOSS}" in text
    assert "no council assessed this run" not in text


def test_a_council_that_ran_and_settled_nothing_is_not_read_as_no_council():
    # The bug this pins: the record said no council had run, which is a false
    # statement in an audit record and the likely outcome of any real run.
    text = rendered((finding(DJANGO),), council=(council_ran(**OPEN_TWO_WAYS),))
    assert "COUNCIL (1)" in text
    assert "no vector  ·  could not settle AC, S" in text
    assert "no council assessed this run" not in text


def test_the_three_council_states_read_differently():
    none_ran = rendered((finding(DJANGO),))
    settled = rendered((finding(DJANGO),), council=(council_ran(),))
    ran_open = rendered((finding(DJANGO),), council=(council_ran(**OPEN_TWO_WAYS),))
    assert none_ran != settled != ran_open != none_ran


def test_an_override_that_matched_no_finding_is_counted_and_named():
    text = rendered((finding(DJANGO),), overridden=("CVE-2021-42799",))
    assert "1 answer override matched no finding: CVE-2021-42799" in text


def test_several_overrides_that_matched_nothing_are_all_named():
    text = rendered(overridden=("CVE-1", "CVE-2"))
    assert "2 answer overrides matched no finding: CVE-1, CVE-2" in text


def test_a_run_whose_overrides_all_matched_says_nothing_about_them():
    one = finding(DJANGO)
    text = rendered((one,), overridden=(one.advisory.advisory_id,))
    assert "matched no finding" not in text


def test_every_state_the_council_record_can_be_in_renders():
    states = council_states()
    raised = tuple(finding(DJANGO, advisory_id=one.advisory_id) for one in states)
    page = rendered(findings=raised, council=states)
    assert [one.advisory_id for one in states if one.advisory_id not in page] == []


def test_a_council_put_to_no_finding_says_so_and_not_that_none_ran():
    raised = (finding(DJANGO, advisory_id="CVE-PASSED"),)
    page = rendered(findings=raised, council=passed_over_entirely())
    assert NOTHING_WAS_PUT_TO_IT in page
    assert NO_COUNCIL_RUN not in page


def test_a_run_with_no_council_at_all_renders_and_names_the_absence():
    page = rendered(findings=(finding(DJANGO),))
    assert "COUNCIL" not in page
    assert "Council ruling" in page


def test_a_run_that_left_nothing_out_says_so_under_the_heading():
    # An empty heading is the silence the section exists to prevent.
    page = as_text(fully_assessed())
    assert lines_under("NOT ASSESSED", page) == [f"  {NOTHING_ABSENT}"]


def test_a_run_that_left_something_out_does_not_say_nothing_was():
    assert NOTHING_ABSENT not in rendered()

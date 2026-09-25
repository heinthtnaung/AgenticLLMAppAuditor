"""Guards on the summary line: its counts, and its pointer to the manifests nothing was read from.

The two pages carry one sentence, so a test of the wording is also a test that
both put it on their summary line and neither leaves it off.
"""

import html

import pytest

from full_runs import fully_assessed
from report.absences import Coverage
from report.html_report import as_html
from report.record import Report, build_report
from report.summary_words import counts, unread_pointer
from report.text_report import as_text
from report_samples import (
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    REFUSED_DISSENT,
    TOTAL_LOSS,
    catalogue,
    component,
    finding,
)

UNREAD = ("frontend/package.json", "package.json")


def reading_nothing_from(*paths: str) -> Report:
    """Build a record whose scan read no version from these manifests."""
    return fully_assessed(Coverage(answers_given=True, council_named=True, unread_manifests=paths))


def test_a_run_that_read_every_manifest_adds_nothing_to_the_summary():
    assert unread_pointer(reading_nothing_from()) == ""


def test_one_manifest_is_counted_in_the_singular_and_the_pointer_says_where_it_is_named():
    said = unread_pointer(reading_nothing_from("package.json"))
    assert said == (
        "Not in these counts: 1 manifest with no lock file Syft reads, named under not assessed."
    )


def test_several_manifests_are_counted_in_the_plural():
    assert "2 manifests with no lock file" in unread_pointer(reading_nothing_from(*UNREAD))


def test_the_terminal_puts_the_pointer_on_the_line_under_the_counts():
    # Beside the counts it would run past the edge of the terminal.
    lines = as_text(reading_nothing_from(*UNREAD)).split("\n")
    counts = next(number for number, line in enumerate(lines) if " across " in line)
    assert lines[counts + 1] == unread_pointer(reading_nothing_from(*UNREAD))


def test_the_page_puts_the_pointer_in_the_same_paragraph_as_the_counts():
    page = as_html(reading_nothing_from(*UNREAD))
    pointer = html.escape(unread_pointer(reading_nothing_from(*UNREAD)), quote=True)
    assert f"carry sources that disagree. {pointer}</p>" in page


def test_neither_page_points_anywhere_when_every_manifest_was_read():
    report = reading_nothing_from()
    assert "Not in these counts" not in as_text(report)
    assert "Not in these counts" not in as_html(report)


def with_sources(*vectors: dict[str, str]):
    """Build a record with one finding for each set of published vectors."""
    django = component()
    found = tuple(
        finding(django, advisory_id=f"CVE-{number}", vectors=one)
        for number, one in enumerate(vectors)
    )
    return build_report(PROVENANCE, catalogue(django), found, {})


def test_a_run_with_no_refused_source_says_nothing_about_refused_sources():
    # Left out at none, so a run like the README's reads exactly as it did.
    assert counts(with_sources({"a": TOTAL_LOSS})) == (
        "1 finding across 1 component. 0 carry sources that disagree."
    )


def test_the_findings_carrying_a_refused_source_are_counted_apart_from_the_disputes():
    said = counts(with_sources(REFUSED_DISSENT, REFUSED_DISSENT, {"a": TOTAL_LOSS}))
    assert said.endswith(
        "0 carry sources that disagree; 2 carry a source this calculator could not read."
    )


def test_both_pages_carry_the_one_counts_sentence():
    report = with_sources(REFUSED_DISSENT)
    assert counts(report) in " ".join(as_text(report).split("\n\n")[1].split("\n"))
    assert html.escape(counts(report), quote=True) in as_html(report)


@pytest.mark.parametrize("disputing, said", [(1, "1 carries"), (2, "2 carry")])
def test_the_verb_agrees_with_the_number_of_findings_whose_sources_disagree(disputing, said):
    disputed = [{"a": TOTAL_LOSS, "b": LOW_CONFIDENTIALITY}] * disputing
    assert f"{said} sources that disagree." in counts(with_sources(*disputed, {"a": TOTAL_LOSS}))


@pytest.mark.parametrize("refusing, said", [(1, "1 carries"), (2, "2 carry")])
def test_the_verb_agrees_with_the_number_of_findings_carrying_a_refused_source(refusing, said):
    refused = [REFUSED_DISSENT] * refusing
    said_last = f"; {said} a source this calculator could not read."
    assert counts(with_sources(*refused)).endswith(said_last)


@pytest.mark.parametrize("raised, said", [(1, "1 finding"), (2, "2 findings")])
def test_the_findings_are_counted_in_the_singular_only_when_there_is_one(raised, said):
    assert counts(with_sources(*[{"a": TOTAL_LOSS}] * raised)).startswith(f"{said} across ")


@pytest.mark.parametrize("installed, said", [(1, "1 component"), (2, "2 components")])
def test_the_components_are_counted_in_the_singular_only_when_there_is_one(installed, said):
    components = [component(f"package-{number}", "1.0") for number in range(installed)]
    report = build_report(PROVENANCE, catalogue(*components), (), {})
    assert counts(report) == f"0 findings across {said}. 0 carry sources that disagree."

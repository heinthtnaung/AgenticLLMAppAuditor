"""Guards on the pointer from the summary's counts to the manifests nothing was read from.

The two pages carry one sentence, so a test of the wording is also a test that
both put it on their summary line and neither leaves it off.
"""

import html

from full_runs import fully_assessed
from report.html_report import as_html
from report.record import Coverage, Report
from report.summary_words import unread_pointer
from report.text_report import as_text

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
    counts = next(number for number, line in enumerate(lines) if "findings across" in line)
    assert lines[counts + 1] == unread_pointer(reading_nothing_from(*UNREAD))


def test_the_page_puts_the_pointer_in_the_same_paragraph_as_the_counts():
    page = as_html(reading_nothing_from(*UNREAD))
    pointer = html.escape(unread_pointer(reading_nothing_from(*UNREAD)), quote=True)
    assert f"carry sources that disagree. {pointer}</p>" in page


def test_neither_page_points_anywhere_when_every_manifest_was_read():
    report = reading_nothing_from()
    assert "Not in these counts" not in as_text(report)
    assert "Not in these counts" not in as_html(report)

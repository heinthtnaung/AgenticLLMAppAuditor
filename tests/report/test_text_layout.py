"""Guards on the typography: columns measured off what is there, not guessed."""

from report.text_layout import NAME_WIDTH, id_width, identified, named, section
from report_samples import component, finding

SHORT = finding(component("a", "1"), advisory_id="CVE-1")
LONG = finding(component("b", "2"), advisory_id="GHSA-5p4m-2wfm-xmqj")


def test_the_id_column_is_as_wide_as_the_longest_id_present():
    # Guessed at, a nineteen-character GHSA id pushes one row out of line with
    # its neighbours and there is a constant to outgrow.
    assert id_width((SHORT, LONG)) == len("GHSA-5p4m-2wfm-xmqj")


def test_a_group_with_nothing_in_it_needs_no_column():
    assert id_width(()) == 0


def test_every_id_in_a_group_is_padded_to_the_same_width():
    width = id_width((SHORT, LONG))
    assert len(identified(SHORT, width)) == len(identified(LONG, width)) == width


def test_a_component_is_named_with_its_version_and_padded():
    assert named(SHORT) == "a 1".ljust(NAME_WIDTH)


def test_a_name_longer_than_the_column_is_not_cut_short():
    wide = finding(component("a-very-long-package-name-indeed", "10.11.12"))
    assert named(wide).strip() == "a-very-long-package-name-indeed 10.11.12"


def test_a_section_puts_its_title_above_its_entries():
    assert section("TITLE", ["  one", "  two"]) == "TITLE\n  one\n  two"


def test_a_section_with_no_entries_is_just_its_title():
    assert section("TITLE", []) == "TITLE"

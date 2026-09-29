"""Guards on the tabbed shell: each tab controls a panel, panels read without JS, deterministic.

With scripts off the `js` class is never set, so the stylesheet leaves every panel
shown; only the running script hides the inactive ones. The same record renders
byte-identical, so a report can be compared run to run.
"""

from report.html_report import as_html
from report_pages import TABS, full_report, parsed, report_with_models


def test_every_tab_controls_a_panel_by_aria_controls():
    page = parsed(as_html(full_report()))
    assert [name for name, _ in page.tabs] == list(TABS)
    assert all(controls == f"panel-{name}" for name, controls in page.tabs)


def test_every_panel_a_tab_names_is_on_the_page():
    page = parsed(as_html(full_report()))
    assert page.panels == [f"panel-{name}" for name in TABS]


def test_the_tabs_route_over_a_tablist():
    # Counted through the parser, not the raw text: the script's own
    # `[role="tab"]` selector would otherwise read as an extra tab.
    rendered = as_html(full_report())
    assert 'role="tablist"' in rendered
    assert len(parsed(rendered).tabs) == len(TABS)


def test_the_page_starts_without_the_js_class_the_script_adds():
    assert "js" not in parsed(as_html(full_report())).html_class.split()


def test_no_panel_is_hidden_so_every_one_is_readable_without_scripts():
    page = parsed(as_html(full_report()))
    assert len(page.panels) == len(TABS)
    assert all(css != "panel" for css in page.hidden)


def test_the_only_hidden_elements_are_the_filter_empty_notes():
    assert set(parsed(as_html(full_report())).hidden) <= {"empty"}


def test_every_panels_content_is_present_with_no_script_running():
    page = as_html(full_report())
    for said in ("Sources disagree", "Agreements and the rest", "Organisation risk",
                 "Council", "Secrets", "Inventory", "All findings"):
        assert said in page


def test_the_same_record_renders_byte_identical_html():
    assert as_html(full_report()) == as_html(full_report())


def test_no_clock_or_random_id_enters_the_page():
    # Two freshly built records over the same inputs give the same bytes: nothing
    # on the page is read from a clock or a random source.
    assert as_html(report_with_models()) == as_html(report_with_models())


def test_the_page_is_one_document_a_browser_will_take():
    page = as_html(full_report())
    assert page.startswith('<!DOCTYPE html>\n<html lang="en">')
    assert page.rstrip().endswith("</html>")
    assert '<meta name="viewport"' in page

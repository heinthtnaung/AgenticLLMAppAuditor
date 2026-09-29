"""Guards that the page fetches nothing: parsed not grepped, so a repository name is no alarm.

The offline guarantee is what lets a report open behind a corporate proxy from a
file. These hold it from both ends: the markup carries no address off the page but
an advisory link, and the one inline script names no network API and loads nothing.
"""

import re

from report.html_assets import script
from report.html_report import as_html
from report_pages import full_report, full_report_with_link, parsed

# Network APIs a page that fetches nothing may not name, as bare words (a bare
# `new XMLHttpRequest;` fetches without parentheses).
NETWORK = re.compile(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon)\b")
# The rest are only ever calls, so the parenthesis stays and a mention cannot trip it.
CALLS = re.compile(r"\b(import|eval|Function)\s*\(")


def test_the_page_carries_exactly_one_inline_script_with_no_src():
    page = parsed(as_html(full_report()))
    assert page.scripts == 1
    assert page.with_src == []


def test_the_page_links_no_stylesheet_and_the_style_fetches_nothing():
    page = parsed(as_html(full_report()))
    assert page.links == 0
    assert "url(" not in page.style and "@import" not in page.style
    assert page.styled_url == []


def test_no_element_reaches_off_the_page_through_an_svg_or_use():
    page = parsed(as_html(full_report_with_link()))
    assert page.xlink == 0
    assert page.uses == 0


def test_the_only_external_address_is_an_advisory_link_a_reader_may_follow():
    linked = parsed(as_html(full_report_with_link()))
    external = [one for one in linked.external if one[0] == "a" and one[1] == "href"]
    assert external, "the fixture has no advisory link, so this guard checked nothing"
    assert linked.offsite == [], f"the page reaches off itself: {linked.offsite}"


def test_the_advisory_link_leaves_the_page_and_is_marked_with_an_inline_icon():
    page = as_html(full_report_with_link())
    assert 'target="_blank" rel="noreferrer"' in page
    assert '<svg class="ext"' in page


def test_the_script_names_no_network_api():
    text = script()
    assert NETWORK.findall(text) == [], f"the script names {NETWORK.findall(text)}, which fetch"
    assert CALLS.findall(text) == [], f"the script calls {CALLS.findall(text)}"


def test_the_script_builds_no_element_and_sets_no_src():
    # A created element or an assigned src is how a relative or protocol-relative
    # URL slips past a URL scan; ban both outright.
    text = script()
    assert "createElement(" not in text
    assert re.search(r"\.src\s*=", text) is None


def test_the_script_holds_no_address_of_its_own():
    text = script()
    assert "http://" not in text and "https://" not in text


def test_the_script_adds_the_js_class_and_opens_details_for_print():
    # Without the js class the stylesheet cannot hide a panel; without the
    # beforeprint handler opening details, a printed page loses them.
    text = script()
    assert 'classList.add("js")' in text
    assert "one.open = true" in text


def test_every_filter_and_toggle_host_names_an_element_that_exists():
    # The script reads data-filter-for and data-toggle-all as element ids; one
    # that resolves to nothing throws on load and leaves every panel shown.
    page = parsed(as_html(full_report()))
    assert page.filter_hosts, "no filter bar rendered, so this guard checked nothing"
    assert page.toggle_hosts, "no toggle-all rendered, so this guard checked nothing"
    assert page.filter_hosts <= page.ids
    assert page.toggle_hosts <= page.ids

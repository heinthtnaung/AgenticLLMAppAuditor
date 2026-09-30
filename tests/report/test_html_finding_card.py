"""Guards on the parts a finding card is built from: the advisory link, the head, the source table.

Both the Disagreements and Agreements tabs assemble these atoms, so they are held
here once: the advisory link leaves the page with an inline icon and nothing else
reaches off it, and a refused source stays on the card marked not scored.
"""

from report.html_finding_card import advisory_name, card_head, source_table, unreadable_table
from report.record import build_report
from report_samples import (
    ADVISORY_URL,
    CONFIDENTIALITY_ONLY,
    ESCAPED_URL,
    PROVENANCE,
    VERSION_2_VECTOR,
    catalogue,
    component,
    finding,
)

DJANGO = component()


def report_of():
    """A minimal report, enough to resolve a finding's approval reasons."""
    return build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})


def test_an_advisory_with_a_page_is_named_by_a_link_that_leaves_the_page():
    linked = advisory_name(finding(DJANGO, url=ADVISORY_URL).advisory)
    opening = f'<a href="{ADVISORY_URL}" target="_blank" rel="noreferrer">CVE-2019-14234'
    assert linked.startswith(opening)
    assert '<svg class="ext"' in linked and linked.endswith("</a>")
    assert '<span class="adv"><a href=' in card_head(report_of(), finding(DJANGO, url=ADVISORY_URL))


def test_an_advisory_with_no_page_is_named_in_plain_text_and_links_nowhere():
    head = card_head(report_of(), finding(DJANGO))
    assert '<span class="adv">CVE-2019-14234</span>' in head
    assert "<a " not in head


def test_a_link_is_escaped_so_nothing_trivy_read_can_close_the_href():
    linked = advisory_name(finding(DJANGO, url=ESCAPED_URL).advisory)
    assert 'href="https://example.test/advisory?id=&quot;1&quot;&amp;x=&lt;b&gt;"' in linked


def test_the_head_names_the_component_a_finding_was_raised_against():
    assert "django 2.2.0" in card_head(report_of(), finding(DJANGO))


def test_every_source_is_a_row_of_its_own_under_generic_headers():
    two = finding(DJANGO, vectors={"ghsa": CONFIDENTIALITY_ONLY, "nvd": CONFIDENTIALITY_ONLY})
    table = source_table(two)
    assert table.count('<span class="source-name">') == 2
    assert "<th>Source</th>" in table
    assert "<th>ghsa" not in table and "<th>nvd" not in table


def test_a_refused_source_is_kept_marked_not_scored_with_its_reason():
    one = finding(DJANGO, vectors={"nvd": VERSION_2_VECTOR})
    table = unreadable_table(one)
    assert "not scored" in table
    assert '<span class="refusal">' in table
    assert VERSION_2_VECTOR in table

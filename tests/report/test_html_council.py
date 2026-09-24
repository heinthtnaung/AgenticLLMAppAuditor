"""Guards on the council on the page: every member's answer, and a run of one marked.

`docs/COUNCIL.md` keeps each member's answer and evidence per assessment. The
page is the rendering most readers open, so these hold it to that -- a member
that spoke and is not on the page is the user's own request unmet in the format
they read.

**Every record here comes out of a real chairman**, through `council_runs`, and
not out of a dataclass filled in by hand. A hand-built record can hold a shape
no chairman emits -- a `basis` on a **contested** ruling, which
`src/council/ruling.py` puts only on a settled one -- and a passing test over an
impossible record is worse than no test, because it reports coverage of a path
that never runs.
"""

from cli.council_run import NO_TEXT_TO_READ, SOURCES_AGREE
from council_runs import (
    AGREED, ALONE, DISSENTING, EVIDENCE, INVENTED, answering, council_ran, declining,
)
from report.council_record import CouncilNotAsked
from cvss.metrics import METRIC_ORDER
from report.html_council import council_section
from report.record import build_report
from report_samples import PROVENANCE, catalogue, component, finding

DJANGO = component()


def rendered(*outcomes) -> str:
    """Render the council section of a report carrying these outcomes."""
    raised = tuple(finding(DJANGO, advisory_id=one.advisory_id) for one in outcomes)
    return council_section(build_report(PROVENANCE, catalogue(DJANGO), raised, {}, outcomes))


def contested_page() -> str:
    """Render an advisory a real council left one metric contested on."""
    return rendered(council_ran(**DISSENTING))


def test_a_run_with_no_council_shows_no_section():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    assert council_section(report) == ""


def test_every_member_that_spoke_is_named_on_the_page():
    # The advisory, the outcome and the vector with no member's name beside them
    # leave a reader unable to say who said what.
    page = contested_page()
    assert "qwen2.5:7b (qwen2.5)" in page
    assert "gemma4:latest (gemma4)" in page


def test_a_verified_quotation_says_it_was_found_and_not_that_one_was_offered():
    # `quoted` and `found in the advisory` are different facts, and the evidence
    # rule turns entirely on the difference.
    assert '<span class="verified">quotation found in the advisory</span>' in contested_page()


def test_a_quotation_the_advisory_does_not_contain_is_marked_as_not_found():
    # Both members quote text nobody wrote, so the metric stays open. That is the
    # only way an unverified row reaches a disclosure: one quotation that does
    # verify settles the metric, and a settled metric is counted rather than opened.
    page = rendered(council_ran(**{
        "qwen2.5:7b": {"AV": answering("N", INVENTED)},
        "gemma4:latest": {"AV": answering("A", INVENTED)},
    }))
    assert '<span class="unverified">quotation not found in the advisory</span>' in page
    assert "verified" in page


def test_the_settled_metrics_are_counted_by_what_settled_them():
    # The basis is on `SettledMetric` and nowhere else, so the counting line is
    # where the chairman's own words belong. "The chairman overruled somebody"
    # is the fact a count alone cannot express.
    page = contested_page()
    assert "7 metrics settled" in page
    assert AGREED in page
    assert EVIDENCE in page


def test_the_basis_counts_add_up_to_the_metrics_they_count():
    page = contested_page()
    assert f'<span class="basis-count">6</span>{AGREED}' in page
    assert f'<span class="basis-count">1</span>{EVIDENCE}' in page


def test_a_contested_metric_shows_no_basis_because_the_chairman_has_none_to_give():
    # `ContestedMetric` carries no basis, no value and no confidence. A
    # disclosure that printed one would be showing a field the record cannot fill.
    page = contested_page()
    opened = page.split('<details class="metric">')[1]
    assert "chairman:" not in opened
    assert AGREED not in opened
    assert EVIDENCE not in opened


def test_one_settled_metric_is_counted_in_the_singular():
    silent = {metric: declining() for metric in METRIC_ORDER[1:]}
    page = rendered(council_ran(**{"qwen2.5:7b": silent, "gemma4:latest": silent}))
    assert "1 metric settled" in page


def test_a_single_assessor_run_says_so_and_a_council_is_not_marked_one():
    # `docs/COUNCIL.md`: the record marks the run single-assessor, so no reader
    # takes council-grade confidence from one model.
    assert "single assessor" in rendered(council_ran(models=ALONE))
    assert "single assessor" not in contested_page()


def test_a_council_that_settled_a_vector_hands_it_over_on_the_page():
    page = rendered(council_ran())
    assert "settled" in page
    assert "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" in page


def test_an_open_metric_is_its_own_disclosure_and_a_settled_one_is_only_counted():
    page = contested_page()
    assert '<details class="metric">' in page
    assert "<code>AV</code>" in page and "contested" in page and "2 members" in page
    assert "<code>PR</code>" not in page


def test_a_member_whose_reply_could_not_be_read_says_why():
    page = rendered(council_ran(**{
        "qwen2.5:7b": {"AV": declining()},
        "gemma4:latest": {"AV": answering("NONSENSE")},
    }))
    assert "failed:" in page
    assert "Attack Vector" in page


def test_a_council_that_settled_nothing_says_what_stopped_it():
    page = contested_page()
    assert "no vector" in page
    assert "could not settle AV" in page


def test_a_quotation_that_could_close_a_tag_is_escaped():
    hostile = "</blockquote><script>alert(1)</script>"
    page = rendered(council_ran(**{
        "qwen2.5:7b": {"AV": answering("N", hostile)},
        "gemma4:latest": {"AV": answering("A", hostile)},
    }))
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_a_finding_the_council_was_not_put_to_is_named_with_the_reason():
    # A scoped run that left them off the page would say no council had run on
    # them, which is a different and false thing.
    page = rendered(
        council_ran(**DISSENTING),
        CouncilNotAsked("CVE-2", SOURCES_AGREE),
        CouncilNotAsked("CVE-3", SOURCES_AGREE),
    )
    assert "2 findings not asked" in page
    assert SOURCES_AGREE in page
    assert "CVE-2, CVE-3" in page


def test_the_reasons_a_finding_was_passed_over_are_kept_apart():
    page = rendered(
        CouncilNotAsked("CVE-2", SOURCES_AGREE), CouncilNotAsked("CVE-3", NO_TEXT_TO_READ)
    )
    assert SOURCES_AGREE in page
    assert NO_TEXT_TO_READ in page


def test_only_the_assessed_findings_are_counted_in_the_heading():
    page = rendered(council_ran(**DISSENTING), CouncilNotAsked("CVE-2", SOURCES_AGREE))
    assert "Council (1)" in page

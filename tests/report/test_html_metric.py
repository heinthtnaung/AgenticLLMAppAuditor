"""Guards on one open metric: every member behind it, and the quotation whole.

`docs/COUNCIL.md` keeps each member's answer and evidence per assessment, so a
member that spoke and is not in the disclosure is the record's own content lost
in the format most readers open.

**Every ruling here comes out of a real chairman**, through `council_runs`, and
not out of a dataclass filled in by hand: `MetricRuling` is one flat type with
every field optional, so a hand-built one can carry a shape no chairman emits.

What decides *which* metrics a reader is shown is `report.html_council`; this is
what one of them looks like opened.
"""

from cli.council_run import FALLBACKS
from council_runs import (
    BOTH,
    DISSENTING,
    INVENTED,
    LONG_QUOTE,
    UNTAGGED,
    answering,
    declining,
    published,
    rulings_with_fallbacks,
)
from report.html_metric import metric_details

BOTH_INVENTING = {
    "qwen2.5:7b": {"AV": answering("N", INVENTED)},
    "gemma4:latest": {"AV": answering("A", INVENTED)},
}


def ruling_on(metric: str, fallbacks=FALLBACKS, models=BOTH, **by_member):
    """Give one metric's ruling out of a real council run over the sample advisory."""
    rulings = rulings_with_fallbacks(fallbacks, models, **by_member)
    return next(one for one in rulings if one.metric == metric)


def contested_metric() -> str:
    """Open the metric two members quoted the advisory about and read differently."""
    return metric_details(ruling_on("AV", **DISSENTING))


def test_every_member_that_spoke_is_named():
    page = contested_metric()
    assert "qwen2.5:7b (qwen2.5)" in page
    assert "gemma4:latest (gemma4)" in page


def test_a_members_value_and_confidence_are_beside_its_name():
    page = contested_metric()
    assert '<span class="member-value">N</span>' in page
    assert '<span class="member-value">A</span>' in page
    assert "high confidence" in page


def test_a_quotation_is_shown_in_full_because_it_is_the_disagreement():
    # On a contested metric the quotation is the whole reason two models reached
    # different values, so no rendering may show an extract of it.
    page = contested_metric()
    assert LONG_QUOTE in page
    assert "..." not in page


def test_a_verified_quotation_says_it_was_found_and_not_that_one_was_offered():
    # `quoted` and `found in the advisory` are different facts, and the evidence
    # rule turns entirely on the difference.
    assert '<span class="verified">quotation found in the advisory</span>' in contested_metric()


def test_a_quotation_the_advisory_does_not_contain_is_marked_as_not_found():
    page = metric_details(ruling_on("AV", **BOTH_INVENTING))
    assert '<span class="unverified">quotation not found in the advisory</span>' in page


def test_a_metric_is_headed_by_its_outcome_and_how_many_spoke_to_it():
    page = contested_metric()
    assert '<details class="metric">' in page
    assert "<code>AV</code>" in page
    assert "contested" in page
    assert "2 members" in page


def test_a_contested_metric_shows_no_basis_because_the_chairman_has_none_to_give():
    # `ContestedMetric` carries no basis, no value and no confidence. A
    # disclosure printing one would be showing a field the record cannot fill.
    assert '<p class="ruling">' not in contested_metric()


def test_an_unresolved_metric_says_what_the_chairman_fell_back_to():
    fell = ruling_on("AV", {**FALLBACKS, "AV": published("N")}, **BOTH_INVENTING)
    page = metric_details(fell)
    assert "chairman: N" in page
    assert "fell back to ghsa" in page


def test_a_member_whose_name_is_its_family_is_not_written_twice():
    page = metric_details(ruling_on("AV", models=UNTAGGED))
    assert "gemma4 (gemma4)" not in page
    assert '<span class="member-name">gemma4</span>' in page


def test_a_member_that_declined_is_told_apart_from_one_that_guessed():
    mixed = ruling_on("AV", **{
        "qwen2.5:7b": {"AV": declining()},
        "gemma4:latest": {"AV": answering("A", "")},
    })
    page = metric_details(mixed)
    assert "declined" in page
    assert "guessed A with nothing quoted" in page


def test_a_member_whose_reply_could_not_be_read_says_why():
    broken = ruling_on("AV", **{
        "qwen2.5:7b": {"AV": declining()},
        "gemma4:latest": {"AV": answering("NONSENSE")},
    })
    assert "failed:" in metric_details(broken)


def test_a_quotation_that_could_close_a_tag_is_escaped():
    hostile = "</blockquote><script>alert(1)</script>"
    page = metric_details(ruling_on("AV", **{
        "qwen2.5:7b": {"AV": answering("N", hostile)},
        "gemma4:latest": {"AV": answering("A", hostile)},
    }))
    assert "<script>" not in page
    assert "&lt;script&gt;" in page

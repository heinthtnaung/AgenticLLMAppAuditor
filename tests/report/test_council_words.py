"""Guards on the sentences both council renderings say, and on the two saying them.

The defect these exist for is drift: two renderings of one record wording the
same field differently. So the wording is held here, and the last test renders a
record both ways and asks that the same facts come out worded the same.

**Every ruling here comes out of a real chairman**, through `council_runs`. The
projection has room for a basis on any ruling and the chairman puts one on a
settled ruling and nowhere else, so a ruling built by hand can be one no run
produces. A member's row is built by hand only in shapes a run records: a
guess, a decline, a failed call.
"""

import html

from council_runs import (
    AGREED,
    ALONE,
    AWKWARD_ADVISORY,
    AWKWARD_QUOTE,
    DECLINED_ON_AV,
    DISSENTING,
    EVIDENCE,
    LONG_QUOTE,
    OPEN_TWO_WAYS,
    QUOTED_BY_ONE,
    SOLE,
    answering,
    council_ran,
    fell_back,
)
from report.council_record import CouncilAssessment, MemberIdentity, MemberSaid, SaidKind
from report.council_words import (
    ONE_QUOTATION_EACH,
    SINGLE_ASSESSOR,
    UNVERIFIED,
    VERIFIED,
    chairman_said,
    checked,
    could_not_settle,
    counted,
    unanswered,
    uncross_checked,
    who,
)
from report.html_council import council_section
from report.record import build_report
from report.text_council import council_block
from report_samples import PROVENANCE, catalogue, component, finding

DJANGO = component()
QWEN = MemberIdentity("small-local", "ollama", "qwen2.5:7b", "qwen2.5", True, "v3")
GEMMA = MemberIdentity("gemma4", "ollama", "gemma4:latest", "gemma4", True, "v3")

# Both members quote the awkward sentence verbatim and reach different values,
# so AV is contested and both renderings show the quotation in full.
QUOTING_AWKWARDLY = {
    "qwen2.5:7b": {"AV": answering("N", AWKWARD_QUOTE)},
    "gemma4:latest": {"AV": answering("A", AWKWARD_QUOTE)},
}


def test_a_member_is_named_by_its_family_only_when_that_is_not_its_name_again():
    assert who(QWEN) == "small-local (qwen2.5)"
    assert who(GEMMA) == "gemma4"


def test_verified_says_the_quotation_was_found_and_not_merely_that_one_was_offered():
    # A member can quote something that is not in the advisory, and the evidence
    # rule turns entirely on the difference.
    assert checked(True) == VERIFIED
    assert checked(False) == UNVERIFIED
    assert "not" not in VERIFIED


def test_a_guess_names_the_value_it_could_not_quote():
    guessed = MemberSaid(QWEN, SaidKind.GUESSED, value="R")
    assert unanswered(guessed) == "guessed R with nothing quoted"


def test_a_member_that_declined_says_only_that():
    assert unanswered(MemberSaid(QWEN, SaidKind.DECLINED)) == "declined"


def test_a_failed_call_carries_the_reason_it_failed():
    broken = MemberSaid(QWEN, SaidKind.FAILED, reason="the server said no")
    assert unanswered(broken) == "failed: the server said no"


def ruled(outcome, metric: str):
    """Give the chairman's ruling on one metric, as a real council recorded it."""
    return next(one for one in outcome.rulings if one.metric == metric)


def test_the_chairman_gives_what_it_settled_then_why_then_how_sure():
    assert chairman_said(ruled(council_ran(), "AV")) == ["chairman: N", AGREED, "high confidence"]


def test_a_value_fallen_back_to_names_the_source_it_came_from():
    assert chairman_said(ruled(fell_back(), "AV")) == ["chairman: N", "fell back to ghsa"]


def test_a_ruling_that_decided_nothing_is_given_nothing_to_say():
    assert chairman_said(ruled(council_ran(**DISSENTING), "AV")) == []


def test_one_of_a_thing_is_counted_in_the_singular():
    assert counted(1, "metric") == "1 metric"
    assert counted(2, "metric") == "2 metrics"
    assert counted(0, "member") == "0 members"


def test_what_a_council_could_not_settle_is_named_in_specification_order():
    # Unresolved and contested are recorded apart, and a reader looking for AC
    # finds it where the specification puts it, not after every unresolved one.
    assert could_not_settle(council_ran(**OPEN_TWO_WAYS)) == "could not settle AC, S"


def a_run_of_every_shape():
    """Give a report whose council records every sentence the two renderings share.

    Four real runs rather than one, because no single advisory produces them
    all: a contested metric needs two members quoting and disagreeing, a
    published fallback needs nobody's quotation to verify, single-assessor
    needs a roster of one, and a quotation an escaping renderer would change
    needs an advisory that contains it.
    """
    outcomes = (
        council_ran(**DISSENTING),
        fell_back(),
        council_ran(advisory_id="CVE-ALONE", models=ALONE),
        council_ran(advisory_id="CVE-AWKWARD", details=AWKWARD_ADVISORY, **QUOTING_AWKWARDLY),
    )
    raised = tuple(finding(DJANGO, advisory_id=one.advisory_id) for one in outcomes)
    return build_report(PROVENANCE, catalogue(DJANGO), raised, {}, outcomes)


def test_both_renderings_word_one_record_the_same_way():
    # One record, two renderings. Whatever each chooses to show, the sentences
    # they share have to be the same sentences.
    report = a_run_of_every_shape()
    said = [
        SINGLE_ASSESSOR, VERIFIED, UNVERIFIED, EVIDENCE, SOLE, LONG_QUOTE, "2 members",
        "guessed A with nothing quoted", "qwen2.5:7b (qwen2.5)", "fell back to ghsa",
        AWKWARD_QUOTE, "7 metrics settled", "could not settle AV", "high confidence",
    ]
    # Unescaped, because the page is compared on the text a reader sees.
    page = html.unescape(council_section(report))
    terminal = " ".join(council_block(report).split())
    assert [one for one in said if one not in page] == []
    assert [one for one in said if one not in terminal] == []


def test_a_vector_resting_on_one_members_quotations_is_marked_on_both_pages():
    # Once the accepted gap: two members reached, so no single-assessor mark, and
    # yet the second quoted nothing and every metric settled on the first alone.
    lone = council_ran(**QUOTED_BY_ONE)
    assert isinstance(lone, CouncilAssessment) and not lone.single_assessor
    assert uncross_checked(lone) == [ONE_QUOTATION_EACH]
    one = finding(DJANGO, advisory_id=lone.advisory_id)
    report = build_report(PROVENANCE, catalogue(DJANGO), (one,), {}, (lone,))
    assert ONE_QUOTATION_EACH in html.unescape(council_section(report))
    assert ONE_QUOTATION_EACH in " ".join(council_block(report).split())


def test_a_vector_two_members_agreed_on_carries_no_mark():
    assert uncross_checked(council_ran()) == []


def test_a_vector_resting_on_one_member_on_a_single_metric_carries_no_mark():
    # Seven metrics were cross-checked, so the vector was, whatever AV rests on.
    mixed = council_ran(**DECLINED_ON_AV)
    assert [one.basis for one in mixed.rulings] == [SOLE] + [AGREED] * 7
    assert uncross_checked(mixed) == []


def test_a_run_that_reached_one_member_keeps_the_single_assessor_mark_and_no_other():
    assert uncross_checked(council_ran(models=ALONE)) == [SINGLE_ASSESSOR]

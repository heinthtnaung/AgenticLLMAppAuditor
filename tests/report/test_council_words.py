"""Guards on the sentences both council renderings say, and on the two saying them.

The defect these exist for is drift: the terminal said `quoted` where the page
said `quotation found in the advisory`, and the two were describing one field of
one record. So the wording is held here, and the last test renders a record both
ways and asks that the same facts come out worded the same.

**The function tests build a ruling by hand and the record test does not.**
`chairman_said` is given whatever the projection can hold and the input need not
be a record any chairman emits; a test that renders a *report* is a claim about
what a run produces, so that one goes through `council_runs` and the real
chairman. This file shipped the difference the wrong way round: a `basis` on an
unresolved ruling, which `src/council/ruling.py` puts on a settled one and
nowhere else.
"""

from cli.council_run import FALLBACKS
from council_runs import (
    ALONE,
    DISSENTING,
    EVIDENCE,
    INVENTED,
    LONG_QUOTE,
    answering,
    council_ran,
    outcome_from,
    published,
    rulings_with_fallbacks,
)
from report.council_record import (
    MemberIdentity,
    MemberSaid,
    MetricRuling,
    Outcome,
    SaidKind,
)
from report.council_words import (
    SINGLE_ASSESSOR,
    UNVERIFIED,
    VERIFIED,
    chairman_said,
    checked,
    counted,
    unanswered,
    who,
)
from report.html_council import council_section
from report.record import build_report
from report.text_council import council_block
from report_samples import PROVENANCE, catalogue, component, finding

DJANGO = component()
QWEN = MemberIdentity("small-local", "ollama", "qwen2.5:7b", "qwen2.5", True, "v3")
GEMMA = MemberIdentity("gemma4", "ollama", "gemma4:latest", "gemma4", True, "v3")

QUOTATION = "a remote attacker can inject a crafted template fragment"
BASIS = "members offering quotations disagreed, and the verified one settled it"

# One member quotes text the advisory does not carry and the other quotes nothing
# at all, so no evidence settles the metric and the published fallback fills it.
NOTHING_VERIFIED = {
    "qwen2.5:7b": {"AV": answering("N", INVENTED)},
    "gemma4:latest": {"AV": answering("A", "")},
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


def test_the_chairman_gives_what_it_decided_then_why_then_what_it_rested_on():
    ruling = MetricRuling(
        "S", Outcome.UNRESOLVED, (), value="U", basis=BASIS, confidence="low",
        fallback_source="ghsa",
    )
    assert chairman_said(ruling) == ["chairman: U", BASIS, "low confidence", "fell back to ghsa"]


def test_a_ruling_that_decided_nothing_is_given_nothing_to_say():
    assert chairman_said(MetricRuling("AC", Outcome.CONTESTED, ())) == []


def test_one_of_a_thing_is_counted_in_the_singular():
    assert counted(1, "metric") == "1 metric"
    assert counted(2, "metric") == "2 metrics"
    assert counted(0, "member") == "0 members"


def a_run_of_every_shape():
    """Give a report whose council records every sentence the two renderings share.

    Three real runs rather than one, because no single advisory produces them
    all: a contested metric needs two members quoting and disagreeing, a
    published fallback needs nobody's quotation to verify, and single-assessor
    needs a roster of one.
    """
    fell_back = rulings_with_fallbacks({**FALLBACKS, "AV": published("N")}, **NOTHING_VERIFIED)
    outcomes = (
        council_ran(**DISSENTING),
        outcome_from(fell_back, advisory_id="CVE-FALLBACK"),
        council_ran(advisory_id="CVE-ALONE", models=ALONE),
    )
    raised = tuple(finding(DJANGO, advisory_id=one.advisory_id) for one in outcomes)
    return build_report(PROVENANCE, catalogue(DJANGO), raised, {}, outcomes)


def test_both_renderings_word_one_record_the_same_way():
    # One record, two renderings. Whatever each chooses to show, the sentences
    # they share have to be the same sentences.
    report = a_run_of_every_shape()
    said = [
        SINGLE_ASSESSOR, VERIFIED, UNVERIFIED, EVIDENCE, LONG_QUOTE, "2 members",
        "guessed A with nothing quoted", "qwen2.5:7b (qwen2.5)", "fell back to ghsa",
    ]
    page, terminal = council_section(report), " ".join(council_block(report).split())
    assert [one for one in said if one not in page] == []
    assert [one for one in said if one not in terminal] == []

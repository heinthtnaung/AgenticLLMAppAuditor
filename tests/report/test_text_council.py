"""Guards on the council in a terminal: the metrics a reader must decide, and no less.

`docs/COUNCIL.md` keeps each member's answer and evidence per assessment, and the
terminal is the rendering most runs produce. So these hold it to the same facts
the web page shows: the chairman's basis, the quotation whole, whether that
quotation **verified**, and a run one member answered marked as one.

The page still counts the settled metrics rather than printing them. What it now
counts them by is the basis, because a metric the chairman settled by overruling
a dissenter reads nothing like one nobody argued about, and a bare `settled` says
neither.
"""

from report.council_record import (
    CouncilAssessment,
    CouncilNotAsked,
    CouncilWithoutVector,
    MemberIdentity,
    MemberSaid,
    MetricRuling,
    Outcome,
    SaidKind,
)
from report.council_words import SINGLE_ASSESSOR
from report.record import build_report
from report.text_council import PAGE_WIDTH, council_block
from report_samples import PROVENANCE, TOTAL_LOSS, catalogue, component, finding

DJANGO = component()
QWEN = MemberIdentity("small-local", "ollama", "qwen2.5:7b", "qwen2.5", True, "v3")
GEMMA = MemberIdentity("gemma4", "ollama", "gemma4:latest", "gemma4", True, "v3")

LONG_QUOTATION = (
    "An attacker who can reach the administrative endpoint may supply a crafted template "
    "fragment, which the renderer evaluates before any authorisation check runs"
)
AGREED = "every member that offered a quotation supported this value"
OVER_A_DISSENT = "members offering quotations disagreed, and the verified one settled it"

CONTESTED = MetricRuling(
    metric="AC",
    outcome=Outcome.CONTESTED,
    said=(
        MemberSaid(QWEN, SaidKind.ANSWERED, "H", LONG_QUOTATION, "high", True),
        MemberSaid(GEMMA, SaidKind.ANSWERED, "L", "a remote attacker can inject", "low", False),
    ),
)
SETTLED = MetricRuling("AV", Outcome.SETTLED, (), value="N", basis=AGREED, confidence="high")
OVERRULED = MetricRuling("UI", Outcome.SETTLED, (), value="N", basis=OVER_A_DISSENT)


AGREED_SOURCES = "no published source disagrees, so there is nothing to reconcile"
NO_TEXT = "the advisory carries no text for a member to read"


def block(*outcomes) -> str:
    """Render the council block of a report carrying these outcomes."""
    raised = tuple(finding(DJANGO, advisory_id=one.advisory_id) for one in outcomes)
    return council_block(build_report(PROVENANCE, catalogue(DJANGO), raised, {}, outcomes))


def contested_block() -> str:
    """Render one advisory whose chairman could not settle a metric."""
    return block(CouncilWithoutVector("CVE-1", False, (), ("AC",), (CONTESTED, SETTLED)))


def folded(rendered: str) -> str:
    """Fold a rendering to one line, so a re-flowed quotation can be looked for whole."""
    return " ".join(rendered.split())


def test_a_run_with_no_council_shows_nothing():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    assert council_block(report) == ""


def test_a_contested_metric_shows_every_member_with_its_evidence():
    # The case the project exists for: two families, one advisory, different
    # values, each with a quotation. A count cannot express it, and a human
    # exercising an override needs to see who said what.
    rendered = contested_block()
    assert "AC  ·  contested  ·  2 members" in rendered
    assert "small-local (qwen2.5)  H  ·  high confidence" in rendered
    assert "gemma4  L  ·  low confidence" in rendered


def test_a_quotation_is_shown_whole_because_it_is_the_disagreement():
    # It used to be cut at sixty characters. On a contested metric the quotation
    # is the entire reason two models reached different values.
    assert LONG_QUOTATION in folded(contested_block())


def test_a_quotation_too_long_for_the_page_is_re_flowed_and_not_shortened():
    rendered = contested_block()
    assert "..." not in rendered
    assert max(len(line) for line in rendered.split("\n")) <= PAGE_WIDTH


def test_whether_a_quotation_verified_is_said_and_not_merely_that_one_was_offered():
    # `quoted` and `found in the advisory` are different facts, and the evidence
    # rule turns entirely on the difference.
    rendered = contested_block()
    assert "quotation found in the advisory" in rendered
    assert "quotation not found in the advisory" in rendered


def test_a_metric_settled_over_a_dissent_is_told_apart_from_one_nobody_argued_about():
    # The basis is the answer to "why did this member win", and the page used to
    # say `settled` and never that the chairman had to overrule anybody.
    rendered = block(CouncilAssessment("CVE-1", TOTAL_LOSS, False, (SETTLED, OVERRULED)))
    assert "2 metrics settled" in rendered
    assert f"1  {AGREED}" in rendered
    assert f"1  {OVER_A_DISSENT}" in rendered


def test_the_settled_metrics_are_counted_rather_than_printed():
    # Eight metrics by n members for every finding is more page than anyone
    # reads, and most of it is agreement.
    rendered = contested_block()
    assert "1 metric settled" in rendered
    assert "AV" not in rendered


def test_the_chairman_says_what_it_decided_on_a_metric_it_could_not_settle():
    fell = MetricRuling("S", Outcome.UNRESOLVED, (), value="U", fallback_source="ghsa")
    rendered = block(CouncilWithoutVector("CVE-1", False, ("S",), (), (fell,)))
    assert "chairman: U  ·  fell back to ghsa" in rendered


def test_a_single_assessor_run_says_so_so_nobody_reads_a_council_into_it():
    # `docs/COUNCIL.md`: the record marks the run single-assessor, so no reader
    # takes council-grade confidence from one model.
    alone = MetricRuling("AC", Outcome.UNRESOLVED, (
        MemberSaid(QWEN, SaidKind.ANSWERED, "H", "a crafted payload", "high", True),
    ))
    assert SINGLE_ASSESSOR in block(CouncilWithoutVector("CVE-1", True, ("AC",), (), (alone,)))


def test_a_settled_council_is_marked_single_assessor_too_when_one_member_ran():
    rendered = block(CouncilAssessment("CVE-1", TOTAL_LOSS, True, (SETTLED,)))
    assert SINGLE_ASSESSOR in rendered
    assert TOTAL_LOSS in rendered


def test_a_council_of_more_than_one_is_not_marked_single_assessor():
    assert SINGLE_ASSESSOR not in contested_block()


def test_a_member_whose_name_is_its_family_is_not_written_twice():
    twice = MetricRuling("AC", Outcome.UNRESOLVED, (
        MemberSaid(GEMMA, SaidKind.ANSWERED, "L", "a remote attacker", "low", True),
    ))
    rendered = block(CouncilWithoutVector("CVE-1", False, ("AC",), (), (twice,)))
    assert "gemma4 (gemma4)" not in rendered
    assert "gemma4  L" in rendered


def test_a_member_that_declined_is_told_apart_from_one_that_guessed():
    mixed = MetricRuling("UI", Outcome.UNRESOLVED, (
        MemberSaid(QWEN, SaidKind.DECLINED),
        MemberSaid(GEMMA, SaidKind.GUESSED, value="R"),
    ))
    rendered = block(CouncilWithoutVector("CVE-1", False, ("UI",), (), (mixed,)))
    assert "declined" in rendered
    assert "guessed R with nothing quoted" in rendered


def test_a_member_whose_call_failed_says_why_on_the_page():
    broken = MetricRuling("AV", Outcome.UNRESOLVED, (
        MemberSaid(QWEN, SaidKind.FAILED, reason="the server said no"),
    ))
    assert "failed: the server said no" in block(
        CouncilWithoutVector("CVE-1", False, ("AV",), (), (broken,))
    )


def test_a_council_that_settled_nothing_says_what_stopped_it():
    rendered = contested_block()
    assert "no vector" in rendered
    assert "could not settle AC" in rendered


def test_a_finding_the_council_was_not_put_to_is_named_with_the_reason():
    # A scoped run that left them out would say no council had run on them,
    # which is a different and false thing.
    rendered = block(
        CouncilWithoutVector("CVE-1", False, (), ("AC",), (CONTESTED,)),
        CouncilNotAsked("CVE-2", AGREED_SOURCES),
        CouncilNotAsked("CVE-3", AGREED_SOURCES),
    )
    assert "2 findings not asked" in rendered
    assert AGREED_SOURCES in rendered
    assert "CVE-2, CVE-3" in rendered


def test_the_reasons_a_finding_was_passed_over_are_kept_apart():
    rendered = block(
        CouncilNotAsked("CVE-2", AGREED_SOURCES), CouncilNotAsked("CVE-3", NO_TEXT)
    )
    assert AGREED_SOURCES in rendered
    assert NO_TEXT in rendered


def test_only_the_assessed_findings_are_counted_in_the_heading():
    # Counting the ones it was never put to would say the council did more than
    # it did, which is the claim the scoping has to not make.
    rendered = block(
        CouncilWithoutVector("CVE-1", False, (), ("AC",), (CONTESTED,)),
        CouncilNotAsked("CVE-2", AGREED_SOURCES),
    )
    assert "COUNCIL (1)" in rendered

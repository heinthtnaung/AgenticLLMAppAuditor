"""Guards on the council on the page: the metrics a reader must decide, and no more."""

from report.council_record import (
    CouncilAssessment,
    CouncilWithoutVector,
    MemberIdentity,
    MemberSaid,
    MetricRuling,
    Outcome,
    SaidKind,
)
from report.record import build_report
from report.text_council import council_block
from report_samples import PROVENANCE, TOTAL_LOSS, catalogue, component, finding

DJANGO = component()
QWEN = MemberIdentity("qwen2.5:7b", "ollama", "qwen2.5:7b", "qwen2.5", True, "v3")
GEMMA = MemberIdentity("gemma4", "ollama", "gemma4:latest", "gemma4", True, "v3")

CONTESTED = MetricRuling(
    metric="AC",
    outcome=Outcome.CONTESTED,
    said=(
        MemberSaid(QWEN, SaidKind.ANSWERED, "H", "requires a crafted payload", "high", True),
        MemberSaid(GEMMA, SaidKind.ANSWERED, "L", "a remote attacker can inject", "low", True),
    ),
)
SETTLED = MetricRuling("AV", Outcome.SETTLED, (), value="N", basis="nobody dissented")


def block(outcome):
    """Render the council block of a report carrying this outcome."""
    one = finding(DJANGO, advisory_id=outcome.advisory_id)
    return council_block(build_report(PROVENANCE, catalogue(DJANGO), (one,), {}, (outcome,)))


def test_a_run_with_no_council_shows_nothing():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    assert council_block(report) == ""


def test_a_contested_metric_shows_every_member_with_its_evidence():
    # The case the project exists for: two families, one advisory, different
    # values, each with a quotation that verifies. A count cannot express it,
    # and a human exercising an override needs to see who said what.
    rendered = block(CouncilWithoutVector("CVE-1", False, (), ("AC",), (CONTESTED, SETTLED)))
    assert "AC  contested" in rendered
    assert "qwen2.5:7b (qwen2.5)  H  high  quoted" in rendered
    assert "gemma4 (gemma4)  L  low  quoted" in rendered
    assert "requires a crafted payload" in rendered


def test_the_settled_metrics_are_counted_rather_than_printed():
    # Eight metrics by n members for every finding is more page than anyone
    # reads, and most of it is agreement.
    rendered = block(CouncilWithoutVector("CVE-1", False, (), ("AC",), (CONTESTED, SETTLED)))
    assert "1 metrics settled" in rendered
    assert "AV" not in rendered


def test_a_council_that_settled_everything_prints_no_metric_detail():
    rendered = block(CouncilAssessment("CVE-1", TOTAL_LOSS, False, (SETTLED,)))
    assert "settled" in rendered
    assert TOTAL_LOSS in rendered
    assert "nobody dissented" not in rendered


def test_an_unverified_quotation_is_marked_as_not_being_in_the_advisory():
    invented = MetricRuling("AC", Outcome.UNRESOLVED, (
        MemberSaid(QWEN, SaidKind.ANSWERED, "H", "text nobody wrote", "high", verified=False),
    ))
    rendered = block(CouncilWithoutVector("CVE-1", False, ("AC",), (), (invented,)))
    assert "not in the advisory" in rendered


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


def test_an_unresolved_metric_names_the_source_it_fell_back_to():
    fell = MetricRuling("S", Outcome.UNRESOLVED, (), value="U", fallback_source="ghsa")
    assert "fell back to ghsa" in block(CouncilWithoutVector("CVE-1", False, ("S",), (), (fell,)))


def test_a_long_quotation_is_shortened_to_keep_one_member_on_one_line():
    wordy = MetricRuling("AC", Outcome.CONTESTED, (
        MemberSaid(QWEN, SaidKind.ANSWERED, "H", "word " * 40, "high", verified=True),
        MemberSaid(GEMMA, SaidKind.ANSWERED, "L", "a remote attacker", "high", verified=True),
    ))
    rendered = block(CouncilWithoutVector("CVE-1", False, (), ("AC",), (wordy,)))
    assert "..." in rendered
    assert max(len(line) for line in rendered.split("\n")) <= 120

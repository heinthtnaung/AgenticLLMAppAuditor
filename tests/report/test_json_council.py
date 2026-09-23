"""Guards on the council in the audit record: everything the design keeps, kept."""

from report.council_record import (
    CouncilAssessment,
    CouncilWithoutVector,
    MemberIdentity,
    MemberSaid,
    MetricRuling,
    Outcome,
    SaidKind,
)
from report.json_council import council_of
from report.record import build_report
from report_samples import PROVENANCE, TOTAL_LOSS, catalogue, component, finding

DJANGO = component()
QWEN = MemberIdentity("qwen2.5:7b", "ollama", "qwen2.5:7b", "qwen2.5", True, "member-base-metric-3")
GEMMA = MemberIdentity("gemma4", "ollama", "gemma4:latest", "gemma4", True, "member-base-metric-3")


def contested() -> MetricRuling:
    """One metric two families read differently, each with a quotation that verifies."""
    return MetricRuling(
        metric="AC",
        outcome=Outcome.CONTESTED,
        said=(
            MemberSaid(QWEN, SaidKind.ANSWERED, "H", "a crafted payload", "high", verified=True),
            MemberSaid(GEMMA, SaidKind.ANSWERED, "L", "a remote attacker", "high", verified=True),
        ),
    )


def rendered(outcome):
    """Render one advisory's council entry from the record."""
    one = finding(DJANGO, advisory_id=outcome.advisory_id)
    report = build_report(PROVENANCE, catalogue(DJANGO), (one,), {}, (outcome,))
    return council_of(report, outcome.advisory_id)


def test_every_member_that_spoke_is_in_the_record():
    settled = CouncilAssessment("CVE-1", TOTAL_LOSS, False, (contested(),))
    members = rendered(settled)["metrics"][0]["members"]
    assert [one["member"] for one in members] == ["qwen2.5:7b", "gemma4"]


def test_a_members_lineage_is_recorded_because_agreement_without_it_means_nothing():
    settled = CouncilAssessment("CVE-1", TOTAL_LOSS, False, (contested(),))
    members = rendered(settled)["metrics"][0]["members"]
    assert [one["family"] for one in members] == ["qwen2.5", "gemma4"]
    assert all(one["provider"] and one["model"] and one["prompt_version"] for one in members)


def test_an_answer_is_recorded_with_its_evidence_and_whether_it_checked_out():
    settled = CouncilAssessment("CVE-1", TOTAL_LOSS, False, (contested(),))
    first = rendered(settled)["metrics"][0]["members"][0]
    assert first["said"] == "answered"
    assert (first["value"], first["confidence"]) == ("H", "high")
    assert first["evidence"] == "a crafted payload"
    assert first["evidence_verified"] is True


def test_the_chairmans_decision_is_recorded_beside_the_members():
    settled = CouncilAssessment("CVE-1", TOTAL_LOSS, False, (contested(),))
    metric = rendered(settled)["metrics"][0]
    assert metric["metric"] == "AC"
    assert metric["outcome"] == "contested"
    assert metric["value"] is None


def test_a_settled_metric_records_what_settled_it():
    ruling = MetricRuling("AV", Outcome.SETTLED, (), value="N", basis="nobody dissented",
                          confidence="high")
    metric = rendered(CouncilAssessment("CVE-1", TOTAL_LOSS, False, (ruling,)))["metrics"][0]
    assert metric["value"] == "N"
    assert (metric["basis"], metric["confidence"]) == ("nobody dissented", "high")


def test_an_unresolved_metric_records_which_source_it_fell_back_to():
    ruling = MetricRuling("S", Outcome.UNRESOLVED, (), value="U", fallback_source="ghsa")
    metric = rendered(CouncilAssessment("CVE-1", TOTAL_LOSS, False, (ruling,)))["metrics"][0]
    assert metric["fallback_source"] == "ghsa"


def test_a_member_that_declined_is_told_apart_from_one_that_guessed():
    ruling = MetricRuling("UI", Outcome.UNRESOLVED, (
        MemberSaid(QWEN, SaidKind.DECLINED),
        MemberSaid(GEMMA, SaidKind.GUESSED, value="N"),
    ))
    members = rendered(CouncilWithoutVector("CVE-1", False, ("UI",), (), (ruling,)))["metrics"][0]
    assert [one["said"] for one in members["members"]] == ["declined", "guessed"]
    assert members["members"][0]["value"] is None
    assert members["members"][1]["value"] == "N"


def test_a_member_whose_call_failed_records_why():
    ruling = MetricRuling("AV", Outcome.UNRESOLVED, (
        MemberSaid(QWEN, SaidKind.FAILED, reason="the server said no"),
    ))
    first = rendered(CouncilWithoutVector("CVE-1", False, ("AV",), (), (ruling,)))["metrics"][0]
    assert first["members"][0]["said"] == "failed"
    assert first["members"][0]["reason"] == "the server said no"


def test_a_council_that_did_not_run_on_an_advisory_is_null():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    assert council_of(report, "CVE-2019-14234") is None

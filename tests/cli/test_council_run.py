"""Guards on the council wiring: a roster from the command line, and no source preferred."""

import json

from council.ruling import NoFallbackPublished
from report.record import CouncilAssessment, CouncilWithoutVector
from cli.council_run import FALLBACKS, assessments, build_roster
from cvss.metrics import METRIC_ORDER
from findings.finding import build_finding
from cli_samples import ADVISORY, LODASH

QUOTATION = "A remote attacker can inject commands"
LEGAL = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}
FINDING = build_finding(LODASH, ADVISORY)


def answering(evidence: str = QUOTATION, declining: tuple[str, ...] = ()):
    """A client whose members answer every metric, or decline the ones named."""
    def said(member, prompt):
        if prompt.metric in declining:
            return json.dumps({"value": "NO_EVIDENCE", "evidence": ""})
        value = LEGAL[prompt.metric]
        return json.dumps({"value": value, "evidence": evidence, "confidence": "high"})

    return {"ollama": said}


def test_the_models_named_become_local_members_in_the_order_given():
    roster = build_roster(("small", "large"))
    assert [member.name for member in roster.members] == ["small", "large"]
    assert all(member.runs_local for member in roster.members)


def test_a_member_is_reached_through_ollama_on_this_machine():
    assert build_roster(("qwen2.5:7b",)).members[0].provider == "ollama"


def test_the_family_is_guessed_from_the_tag():
    # A roster file would carry it properly. It is only read to judge how much a
    # roster's agreement is worth, so a wrong guess costs a reader, not a number.
    assert build_roster(("qwen2.5:7b-instruct",)).members[0].family == "qwen2.5"


def test_no_published_source_is_offered_as_a_fallback():
    # The chairman falls back to a published vector when nobody found evidence,
    # and choosing which source that is, is the precedence the design refuses to
    # set. So none is offered, for every metric.
    assert set(FALLBACKS) == set(METRIC_ORDER)
    assert all(isinstance(one, NoFallbackPublished) for one in FALLBACKS.values())
    assert "no published source may be preferred" in FALLBACKS["AV"].reason


def test_a_council_that_settles_every_metric_hands_over_a_vector():
    settled = assessments((FINDING,), build_roster(("small",)), answering())
    assert len(settled) == 1
    assert isinstance(settled[0], CouncilAssessment)
    assert settled[0].advisory_id == ADVISORY.advisory_id
    assert settled[0].vector == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


def test_one_member_alone_is_recorded_as_a_single_assessor():
    assert assessments((FINDING,), build_roster(("small",)), answering())[0].single_assessor


def test_a_council_that_leaves_a_metric_unsettled_hands_over_no_vector():
    # With no fallback offered, an unresolved metric has no value and a partial
    # vector is not something the engine may be handed.
    outcome = assessments((FINDING,), build_roster(("small",)), answering(declining=("S",)))[0]
    assert isinstance(outcome, CouncilWithoutVector)
    assert not hasattr(outcome, "vector")


def test_a_council_that_settled_nothing_still_says_it_ran_and_what_stopped_it():
    # Discarding the run along with the vector told the report no council had
    # run at all, and what it could not settle is the escalation policy's input.
    outcome = assessments((FINDING,), build_roster(("small",)), answering(declining=("S",)))[0]
    assert outcome.advisory_id == ADVISORY.advisory_id
    assert outcome.unresolved_metrics == ("S",)
    assert outcome.contested_metrics == ()


def test_a_council_whose_members_quote_nothing_real_settles_every_metric_open():
    unquotable = answering(evidence="text the advisory does not contain")
    outcome = assessments((FINDING,), build_roster(("small",)), unquotable)[0]
    assert isinstance(outcome, CouncilWithoutVector)
    assert outcome.unresolved_metrics == METRIC_ORDER


def test_an_advisory_with_no_text_is_not_put_to_anybody():
    silent = build_finding(LODASH, ADVISORY.__class__(
        advisory_id="CVE-1", purl=LODASH.purl, fixed_version=None,
        summary="", details="   ", vectors={},
    ))
    assert assessments((silent,), build_roster(("small",)), answering()) == ()

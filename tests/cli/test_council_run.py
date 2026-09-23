"""Guards on the council wiring: which findings it is put to, and no source preferred.

**Scoped by default.** A measured two-member run over 18 findings spent roughly
72% of 43 minutes on findings whose sources already agreed, and the council
exists to reconcile sources. So these hold the scope to the findings that need
one -- and hold every skip to naming its reason, because a finding the council
was not asked about and a run where nobody was named to ask are different facts.
"""

import io
import json

from council.ruling import NoFallbackPublished
from report.council_record import CouncilAssessment, CouncilNotAsked, CouncilWithoutVector
from cli.council_run import (
    FALLBACKS,
    NO_TEXT_TO_READ,
    SOURCES_AGREE,
    assessments,
    build_roster,
    watching,
)
from cvss.metrics import METRIC_ORDER
from findings.finding import build_finding
from cli_samples import ADVISORY, LODASH

QUOTATION = "A remote attacker can inject commands"
AGREED = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
LEGAL = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}
FINDING = build_finding(LODASH, ADVISORY)


def advisory_like(advisory_id: str, **overrides):
    """Build one advisory against lodash, with whichever sources a test needs on it."""
    fields = {
        "advisory_id": advisory_id,
        "purl": LODASH.purl,
        "fixed_version": None,
        "summary": "",
        "details": ADVISORY.details,
        "vectors": {"ghsa": AGREED, "nvd": AGREED},
    }
    return ADVISORY.__class__(**{**fields, **overrides})


UNDISPUTED = build_finding(LODASH, advisory_like("CVE-AGREED"))
UNSCORED = build_finding(LODASH, advisory_like("CVE-UNSCORED", vectors={}))


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


def test_an_advisory_with_no_text_is_not_put_to_anybody_and_the_record_says_why():
    # Dropping it said no council had run on that finding, which is a different
    # and false thing: a council ran, and this advisory gave it nothing to read.
    silent = build_finding(LODASH, ADVISORY.__class__(
        advisory_id="CVE-1", purl=LODASH.purl, fixed_version=None,
        summary="", details="   ", vectors={},
    ))
    outcome = assessments((silent,), build_roster(("small",)), answering())[0]
    assert outcome == CouncilNotAsked("CVE-1", NO_TEXT_TO_READ)


def test_the_total_counts_only_the_members_this_run_will_ask():
    # A hosted member with no egress is never asked, and a total counting it is
    # a progress line that never reaches its end.
    from council.roster import Member, Roster

    hosted = Member("remote", "openrouter", "x/y", "x", runs_local=False)
    roster = Roster((*build_roster(("small",)).members, hosted))
    assert watching((FINDING,), roster, io.StringIO()).calls == 8


def test_the_total_counts_only_the_findings_the_council_can_read():
    # An advisory with no text is never put to anybody.
    silent = build_finding(LODASH, ADVISORY.__class__(
        advisory_id="CVE-2", purl=LODASH.purl, fixed_version=None,
        summary="", details="  ", vectors={},
    ))
    counted = watching((FINDING, silent), build_roster(("small",)), io.StringIO())
    assert (counted.findings, counted.calls) == (1, 8)


def test_a_finding_whose_sources_agree_is_not_put_to_the_council():
    # The council reconciles sources. A finding with nothing to reconcile is not
    # its work, and 13 of 18 on the corpus under test are exactly that.
    outcome = assessments((UNDISPUTED,), build_roster(("small",)), answering())[0]
    assert outcome == CouncilNotAsked("CVE-AGREED", SOURCES_AGREE)


def test_a_finding_whose_sources_disagree_is_put_to_the_council():
    assessed = assessments((FINDING,), build_roster(("small",)), answering())
    assert [one.advisory_id for one in assessed] == [ADVISORY.advisory_id]
    assert isinstance(assessed[0], CouncilAssessment)


def test_a_finding_no_source_scored_is_put_to_the_council():
    # Its sources do not agree either -- there are none -- and a council vector
    # is the only severity this finding will ever carry.
    assessed = assessments((UNSCORED,), build_roster(("small",)), answering())
    assert isinstance(assessed[0], CouncilAssessment)


def test_every_finding_is_asked_about_when_the_operator_asks_for_that():
    # Scoping cannot discover that two agreeing sources are both wrong, and
    # `docs/COUNCIL.md` says no source is the reference the others are measured
    # against. So an operator may refuse the saving.
    assessed = assessments(
        (UNDISPUTED,), build_roster(("small",)), answering(), every_finding=True
    )
    assert isinstance(assessed[0], CouncilAssessment)


def test_the_assessed_findings_come_before_the_ones_passed_over():
    given = (UNDISPUTED, FINDING)
    assessed = assessments(given, build_roster(("small",)), answering())
    assert [type(one).__name__ for one in assessed] == ["CouncilAssessment", "CouncilNotAsked"]


def test_the_total_counts_only_the_findings_this_run_will_be_asked_about():
    counted = watching((FINDING, UNDISPUTED), build_roster(("small",)), io.StringIO())
    assert (counted.findings, counted.calls) == (1, 8)


def test_the_total_counts_every_finding_when_every_finding_is_asked_about():
    roster = build_roster(("small",))
    counted = watching((FINDING, UNDISPUTED), roster, io.StringIO(), every_finding=True)
    assert (counted.findings, counted.calls) == (2, 16)

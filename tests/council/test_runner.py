"""Guards on the runner: it dispatches, it redacts, and it hides nobody.

No model is asked. Every test passes its own client mapping, which is the seam
the runner takes for exactly this reason.
"""

import json

import pytest

from council.chairman import agreed_vector
from council.roster import Roster
from council.ruling import Basis, PublishedFallback, SettledMetric, UnresolvedMetric
from council.answer import MemberAnswer, MemberFoundNoEvidence, MemberGuessed
from council.runner import CouncilRun, MemberFailure, assess
from council.transport import ModelUnavailable
from council_samples import hosted, member

RAW_ADVISORY = (
    "CVE-2021-44228: A flaw in Apache Log4j2. An unauthenticated remote attacker "
    "who can control log messages can execute arbitrary code. "
    "Scored CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H by the vendor."
)

FALLBACKS = {
    metric: PublishedFallback(value=value, source="ghsa")
    for metric, value in {
        "AV": "L", "AC": "H", "PR": "H", "UI": "R", "S": "U", "C": "N", "I": "N", "A": "N",
    }.items()
}

QUOTABLE = "unauthenticated remote attacker"
DECLINED = json.dumps({"value": "NO_EVIDENCE", "evidence": ""})

# A second legal value for each metric, so a guess can lean the other way.
OTHER_VALUE = {"AV": "L", "AC": "H", "PR": "L", "UI": "R", "S": "C", "C": "L", "I": "L", "A": "L"}

# A value each metric actually allows. "N" is legal for AV and not for AC or S,
# so a client that said one thing everywhere would be testing the refusal path.
LEGAL_VALUE = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}


def replying(evidence: str = QUOTABLE):
    """A client answering each metric with a value that metric allows."""
    return lambda asked, prompt: json.dumps(
        {"value": LEGAL_VALUE[prompt.metric], "evidence": evidence, "confidence": "high"}
    )


def clients_of(ask, provider: str = "ollama"):
    """Put one client behind one provider."""
    return {provider: ask}


def test_every_metric_is_put_to_the_roster_and_handed_over_as_a_vector():
    run = assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, clients_of(replying()))
    assert isinstance(run, CouncilRun)
    assert [round_.metric for round_ in run.rounds] == ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
    assert all(isinstance(round_.ruling, SettledMetric) for round_ in run.rounds)
    assert str(agreed_vector(run.rulings, version="3.1")).startswith("CVSS:3.1/AV:N/")
    assert not hasattr(run, "score")


def test_the_member_is_shown_the_redacted_advisory_and_never_the_raw_one():
    # The quotation check refuses text still carrying a CVE id, so a runner that
    # passed the raw advisory would raise here rather than quietly report an
    # absence the advisory never had.
    shown = []
    def remember(member_asked, prompt):
        shown.append(prompt.advisory_shown)
        return replying()(member_asked, prompt)

    assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, clients_of(remember))
    assert all("CVE-2021-44228" not in text for text in shown)
    assert all("[identifier withheld]" in text for text in shown)


def test_a_quotation_spanning_a_redaction_still_verifies_through_the_runner():
    spanning = "[identifier withheld]: A flaw in Apache Log4j2"
    clients = clients_of(replying(evidence=spanning))
    run = assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, clients)
    assert isinstance(run.rounds[0].ruling, SettledMetric)


def test_members_are_asked_in_roster_order():
    # Ordered by cost, which is what makes an escalation policy mean anything.
    roster = Roster((member("cheap"), member("dear"), member("dearest")))
    run = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(replying()))
    assert run.asked == ("cheap", "dear", "dearest")
    names = [reply.member.name for reply in run.rounds[0].replies]
    assert names == ["cheap", "dear", "dearest"]


def test_a_member_that_could_not_be_asked_reaches_the_run_record():
    # Who can be reached is `council.providers`; what the run guarantees is that
    # everyone it could not ask is on the record beside those it did.
    roster = Roster((member("local"), hosted("remote")))
    run = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(replying()))
    assert run.asked == ("local",)
    assert [entry.member.name for entry in run.skipped] == ["remote"]


def test_a_member_that_fails_costs_its_metric_and_not_the_run():
    def falls_over(member_asked, prompt):
        if member_asked.name == "broken":
            raise ModelUnavailable("the server said no")
        return replying()(member_asked, prompt)

    roster = Roster((member("sound"), member("broken")))
    run = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(falls_over))
    assert all(isinstance(round_.ruling, SettledMetric) for round_ in run.rounds)
    assert {failure.member_name for failure in run.failures} == {"broken"}
    assert len(run.failures) == 8


@pytest.mark.parametrize(
    "said",
    ["not json at all", json.dumps({"value": "Z", "evidence": QUOTABLE, "confidence": "high"})],
    ids=["not json", "a value the metric forbids"],
)
def test_a_reply_that_cannot_be_read_is_a_failure_and_not_a_crash(said):
    run = assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, clients_of(lambda m, p: said))
    assert len(run.failures) == 8
    assert all(isinstance(failure, MemberFailure) for failure in run.failures)
    assert isinstance(run.rounds[0].ruling, UnresolvedMetric)


def test_a_metric_nobody_could_answer_falls_back_and_says_which_source():
    declines = clients_of(lambda asked, prompt: DECLINED)
    run = assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, declines)
    ruling = run.rounds[0].ruling
    assert isinstance(ruling, UnresolvedMetric)
    assert ruling.fallback.source == "ghsa"
    assert ruling.fallback.value == "L"


def test_a_run_that_reaches_one_member_is_a_single_assessor():
    # Three configured of whom two cannot be reached cross-checks nothing either.
    alone = Roster((member(),))
    reduced = Roster((member("local"), hosted("one", egress=True), hosted("two")))
    assert assess(RAW_ADVISORY, alone, FALLBACKS, clients_of(replying())).single_assessor
    assert assess(RAW_ADVISORY, reduced, FALLBACKS, clients_of(replying())).single_assessor


def test_two_reachable_members_are_not_a_single_assessor():
    roster = Roster((member("one"), member("two")))
    assert not assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(replying())).single_assessor


@pytest.mark.parametrize("dropped", ["AV", "S", "A"])
def test_a_run_without_a_fallback_for_every_metric_is_refused_before_any_model_is_asked(dropped):
    asked = []
    incomplete = {metric: value for metric, value in FALLBACKS.items() if metric != dropped}
    with pytest.raises(ValueError, match=f"No fallback ready for {dropped}"):
        assess(RAW_ADVISORY, Roster((member(),)), incomplete, clients_of(asked.append))
    assert asked == []


@pytest.mark.parametrize("given", [None, [], "ghsa"], ids=["none", "list", "str"])
def test_fallbacks_that_are_no_mapping_are_refused(given):
    with pytest.raises(TypeError, match="must be a mapping of metric to fallback"):
        assess(RAW_ADVISORY, Roster((member(),)), given, clients_of(replying()))


def test_the_same_replies_give_the_same_run():
    roster = Roster((member(),))
    first = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(replying()))
    second = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(replying()))
    assert first.rulings == second.rulings


def guessing(asked, prompt):
    """A client that leans the other way with nothing to quote for it."""
    return json.dumps({"value": OTHER_VALUE[prompt.metric], "evidence": "", "confidence": "low"})


def test_replies_carrying_no_weight_still_reach_the_record():
    # The condition the AGREED basis rests on. The basis ranges over the members
    # that offered a quotation, which is honest only while a reader can see the
    # replies it leaves out: here a guess at AV:L sits beside a ruling of AV:N,
    # and without it on the round AGREED would be claiming a unanimity that did
    # not happen. The only thing filtered out is a call that gave nothing back.
    def quietly(asked, prompt):
        if asked.name == "declines":
            return DECLINED
        if asked.name == "guesses":
            return guessing(asked, prompt)
        return replying()(asked, prompt)

    roster = Roster((member("sure"), member("declines"), member("guesses")))
    round_ = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(quietly)).rounds[0]
    kinds = [type(reply) for reply in round_.replies]
    assert kinds == [MemberAnswer, MemberFoundNoEvidence, MemberGuessed]
    assert (round_.replies[2].member.name, round_.replies[2].value) == ("guesses", "L")
    assert (round_.ruling.value, round_.ruling.basis) == ("N", Basis.AGREED)
    assert round_.failures == ()

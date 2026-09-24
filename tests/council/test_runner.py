"""Guards on the runner: it dispatches, it redacts, and it hides nobody.

No model is asked. Every test passes its own client mapping, which is the seam
the runner takes for exactly this reason.
"""

import json

import pytest

from council.chairman import agreed_vector
from council.prompt import PROMPT_VERSION
from council.roster import Roster
from council.ruling import Basis, SettledMetric, UnresolvedMetric
from council.answer import MemberAnswer, MemberFoundNoEvidence, MemberGuessed
from council.run import CouncilRun, MemberFailure
from council.runner import assess
from council.transport import ModelUnavailable
from council_samples import (
    DECLINED,
    FALLBACKS,
    QUOTABLE,
    RAW_ADVISORY,
    clients_of,
    guessing,
    hosted,
    member,
    replying,
)


def test_every_metric_is_put_to_the_roster_and_handed_over_as_a_vector():
    run = assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, clients_of(replying()))
    assert isinstance(run, CouncilRun)
    assert [round_.metric for round_ in run.rounds] == ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
    assert all(isinstance(round_.ruling, SettledMetric) for round_ in run.rounds)
    assert str(agreed_vector(run.rulings, version="3.1")).startswith("CVSS:3.1/AV:N/")
    assert not hasattr(run, "score")


def test_the_runner_builds_the_prompt_the_member_reads_and_the_record_names():
    # A runner passing the raw advisory would raise on the CVE id rather than
    # quietly report an absence. The recorded version is that same prompt's, so
    # a fixture's version can never be what a run carries.
    seen = []
    def remember(member_asked, prompt):
        """Keep the prompt a member was shown, then answer it."""
        seen.append(prompt)
        return replying()(member_asked, prompt)

    run = assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, clients_of(remember))
    assert all("CVE-2021-44228" not in asked.advisory_shown for asked in seen)
    assert all("[identifier withheld]" in asked.advisory_shown for asked in seen)
    assert run.rounds[0].replies[0].member.prompt_version == PROMPT_VERSION


@pytest.mark.parametrize(
    ("evidence", "kind"),
    [("[identifier withheld]: A flaw in Apache Log4j2", SettledMetric),
     ("[identifier withheld]", UnresolvedMetric)],
    ids=["spanning a marker", "nothing but the marker"],
)
def test_a_quotation_must_carry_the_advisorys_words_and_not_only_our_markers(evidence, kind):
    # The marker alone is a substring of what a member reads, so it would settle a
    # metric on evidence supporting nothing. A quotation containing a marker is
    # not refused outright: the first case is a real quotation of what it read.
    run = assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, clients_of(replying(evidence)))
    assert all(isinstance(round_.ruling, kind) for round_ in run.rounds)


def test_a_member_that_could_not_be_asked_reaches_the_run_record():
    # Who can be reached is `council.providers`; what the run guarantees is that
    # everyone it could not ask is on the record beside those it did.
    roster = Roster((member("local"), hosted("remote")))
    run = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(replying()))
    assert (run.asked, [entry.member.name for entry in run.skipped]) == (("local",), ["remote"])


def test_a_member_that_fails_costs_its_metric_and_not_the_run():
    def falls_over(member_asked, prompt):
        """Fail the call to the member named broken, and answer every other."""
        if member_asked.name == "broken":
            raise ModelUnavailable("the server said no")
        return replying()(member_asked, prompt)

    roster = Roster((member("sound"), member("broken")))
    run = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(falls_over))
    assert all(isinstance(round_.ruling, SettledMetric) for round_ in run.rounds)
    assert {one.member for one in run.failures} == {member("broken").identify(PROMPT_VERSION)}
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
    ruling = assess(RAW_ADVISORY, Roster((member(),)), FALLBACKS, declines).rounds[0].ruling
    assert isinstance(ruling, UnresolvedMetric)
    assert (ruling.fallback.source, ruling.fallback.value) == ("ghsa", "L")


def test_single_assessor_counts_the_members_a_run_actually_reaches():
    # Three configured of whom two cannot be reached cross-checks nothing either.
    alone = Roster((member(),))
    reduced = Roster((member("local"), hosted("one", egress=True), hosted("two")))
    pair = Roster((member("one"), member("two")))
    assert assess(RAW_ADVISORY, alone, FALLBACKS, clients_of(replying())).single_assessor
    assert assess(RAW_ADVISORY, reduced, FALLBACKS, clients_of(replying())).single_assessor
    assert not assess(RAW_ADVISORY, pair, FALLBACKS, clients_of(replying())).single_assessor


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
    roster, clients = Roster((member(),)), clients_of(replying())
    assert (
        assess(RAW_ADVISORY, roster, FALLBACKS, clients).rulings
        == assess(RAW_ADVISORY, roster, FALLBACKS, clients).rulings
    )


def test_replies_carrying_no_weight_still_reach_the_record():
    # The condition the AGREED basis rests on. The basis ranges over the members
    # that offered a quotation, which is honest only while a reader can see the
    # replies it leaves out: here a guess at AV:L sits beside a ruling of AV:N,
    # and without it on the round AGREED would be claiming a unanimity that did
    # not happen. The only thing filtered out is a call that gave nothing back.
    def quietly(asked, prompt):
        """Decline or guess for the members named so, and answer for the rest."""
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

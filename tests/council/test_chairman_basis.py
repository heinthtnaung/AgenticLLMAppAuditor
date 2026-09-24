"""Guards on what a settled metric rests on: one quotation, agreement, or a dissent overruled.

The basis changes what the record admits and never the ruling, which evidence
still decides. It ranges over the members that offered a quotation, verified or
not, so a member that declined, guessed or failed neither agrees nor dissents.
"""

import pytest

from council.chairman import rule_on_metric
from council.roster import Roster
from council.ruling import Basis, PublishedFallback
from council.runner import assess
from council_samples import (
    ADVISORY, FALLBACKS, NOT_IN_THE_ADVISORY, RAW_ADVISORY, answer, clients_of, found_nothing,
    guessed, guessing, member, replying,
)

FALLBACK = PublishedFallback(value="L", source="nvd")


def rule(replies):
    """Rule on AV from the replies a test is about."""
    return rule_on_metric("AV", replies, ADVISORY, FALLBACK)


@pytest.mark.parametrize(
    "beside",
    [[], [found_nothing(name="two")], [guessed(value="L", name="two")]],
    ids=["nothing, as a failed call leaves it", "a decline", "a guess"],
)
def test_one_quotation_and_no_other_rests_on_that_quotation_alone(beside):
    # A guess carries no weight at all, and that includes no weight towards
    # agreement: agreeing needs a second member that quoted something.
    ruling = rule([answer(name="one"), *beside])
    assert (ruling.value, ruling.basis) == ("N", Basis.SOLE)


def test_two_quotations_for_one_value_agree_whether_or_not_both_verified():
    replies = [answer(name="one"), answer(name="two", evidence=NOT_IN_THE_ADVISORY)]
    assert rule(replies).basis is Basis.AGREED


def test_a_quoting_dissenter_the_evidence_overruled_is_recorded_as_overruled():
    replies = [answer(name="one"), answer(name="two", value="L", evidence=NOT_IN_THE_ADVISORY)]
    assert rule(replies).basis is Basis.EVIDENCE


def test_the_basis_changes_what_the_record_admits_and_never_the_ruling():
    alone = rule([answer(name="one"), guessed(value="L", name="two")])
    agreed = rule([answer(name="one"), answer(name="two")])
    assert (alone.value, alone.confidence, alone.supporting[0].member.name) == (
        agreed.value, agreed.confidence, agreed.supporting[0].member.name,
    )


def test_a_member_guessing_every_metric_leaves_each_resting_on_one_quotation():
    # Two members reached, so no single-assessor mark, and yet nothing on the
    # record was agreed with: one quoted the advisory on every metric and the
    # other guessed every one.
    def quietly(asked, prompt):
        """Guess every metric for the member named so, and answer for the other."""
        if asked.name == "guesses":
            return guessing(asked, prompt)
        return replying()(asked, prompt)

    roster = Roster((member("quotes"), member("guesses")))
    run = assess(RAW_ADVISORY, roster, FALLBACKS, clients_of(quietly))
    assert not run.single_assessor
    assert [round_.ruling.basis for round_ in run.rounds] == [Basis.SOLE] * 8

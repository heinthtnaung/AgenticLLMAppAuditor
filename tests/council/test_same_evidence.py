"""Guards on the same-evidence flag: two members, one verified set of words, two values."""

import pytest

from council.answer import MemberFoundNoEvidence, MemberGuessed, MemberOrderSensitive
from council.same_evidence import read_differently, same_words
from council_samples import ADVISORY, NOT_IN_THE_ADVISORY, answer, identity

WHOLE = "An unauthenticated remote attacker can\nsend a crafted request"
PART = "unauthenticated remote attacker"
ELSEWHERE = "The component does not validate the supplied path."


@pytest.mark.parametrize(
    ("one", "other"),
    [
        ("remote attacker", "remote attacker"),
        ("remote  attacker", "remote\nattacker"),
        ("the host’s filesystem", "the host's filesystem"),
        ("remote attacker", "An unauthenticated remote attacker can"),
        ("path", "the supplied path."),
        ("the supplied path.", "path"),
        ("the parser (v1.2", "in the parser (v1.2 and later"),
        ("(PR:N)", "privileges(PR:N)"),
        ("-y", "x-y"),
        ("x-", "x-y"),
    ],
    ids=["equal", "equal once whitespace folds", "equal once quotes fold", "inside",
         "inside, up to a full stop", "either way round", "a bracket matched as text",
         "punctuation at both ends", "punctuation first", "punctuation last"],
)
def test_quotations_equal_or_one_inside_the_other_uncut_are_the_same(one, other):
    assert same_words(one, other)


@pytest.mark.parametrize(
    ("one", "other"),
    [
        ("path", "the supplied paths"),
        ("path", "a sociopath"),
        ("Remote attacker", "remote attacker"),
        ("remote attacker can", "attacker can send"),
        ("remote attacker", "the supplied path."),
        ("v1.2", "v1x2 fixed"),
    ],
    ids=["inside a longer word", "at a longer word's end", "another case", "overlapping only",
         "unrelated", "a full stop matched as text"],
)
def test_quotations_otherwise_are_not_the_same(one, other):
    assert not same_words(one, other)


def test_a_quotation_with_no_text_is_refused_rather_than_found_inside_everything():
    with pytest.raises(ValueError, match="no text"):
        same_words(" \n", "remote attacker")


def two(value: str, evidence: str, other_value: str = "L", other_evidence: str = PART):
    """Give two members' answers on AV: small-local's, then other-local's."""
    first = answer(value=value, evidence=evidence)
    return first, answer(value=other_value, evidence=other_evidence, name="other-local")


def test_two_values_read_from_the_same_verified_words_are_flagged():
    assert read_differently(two("N", WHOLE), ADVISORY)


@pytest.mark.parametrize(
    "replies",
    [
        two("L", WHOLE),
        two("N", ELSEWHERE),
        two("N", f"{PART} {NOT_IN_THE_ADVISORY}"),
    ],
    ids=["one value", "different words", "one quotation not in the advisory"],
)
def test_one_value_different_words_or_an_unverified_quotation_are_not_flagged(replies):
    assert not read_differently(replies, ADVISORY)


def test_only_answers_count_so_a_decline_guess_or_order_sensitive_reply_flags_nothing():
    who = identity("other-local")
    others = [
        MemberFoundNoEvidence("AV", who),
        MemberGuessed("AV", "L", who),
        MemberOrderSensitive("AV", "L", "A", who),
    ]
    assert not read_differently([answer(evidence=WHOLE), *others], ADVISORY)


def test_one_pair_among_three_members_is_enough_to_flag():
    third = answer(value="A", evidence=ELSEWHERE, name="third-local")
    assert read_differently([*two("N", WHOLE), third], ADVISORY)

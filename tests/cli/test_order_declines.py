"""Guards on naming the order of the options a member declined in, off its two readings."""

import pytest

from cli.order_declines import declined_in, in_both_orders, unverified_in
from council.answer import (
    Confidence,
    MemberAnswer,
    MemberFoundNoEvidence,
    MemberGuessed,
    MemberIdentity,
)
from council.run import MemberFailure, OrderReadings
from report.council_record import MemberIdentity as Named
from report.council_record import MemberSaid, ReadingOrder, SaidKind

SHOWN = "A remote attacker can inject commands through a template option."
QUOTED = "A remote attacker can inject commands"
INVENTED = "the maintainers have not replied"
WHO = MemberIdentity("small-local", "ollama", "small:1b", "small", True, "v-in-order")
IN_ORDER, REVERSED = ReadingOrder.IN_ORDER, ReadingOrder.REVERSED


def answer(evidence: str = QUOTED) -> MemberAnswer:
    """Give a quoted answer on AV."""
    return MemberAnswer("AV", "N", evidence, Confidence.HIGH, WHO)


def decline() -> MemberFoundNoEvidence:
    """Give a decline on AV."""
    return MemberFoundNoEvidence("AV", WHO)


@pytest.mark.parametrize(
    ("in_order", "reversed_order", "declined"),
    [
        (decline(), answer(), (IN_ORDER,)),
        (answer(), decline(), (REVERSED,)),
        (decline(), decline(), (IN_ORDER, REVERSED)),
        (answer(), answer(), ()),
        (MemberFailure(WHO, "AV", "timed out"), decline(), (REVERSED,)),
    ],
    ids=["in order", "reversed", "both", "neither", "beside a failure"],
)
def test_the_orders_a_member_said_no_evidence_in_are_named(in_order, reversed_order, declined):
    assert declined_in(OrderReadings(in_order, reversed_order)) == declined


@pytest.mark.parametrize(
    ("in_order", "reversed_order", "unverified"),
    [
        (answer(INVENTED), answer(), (IN_ORDER,)),
        (answer(), answer(INVENTED), (REVERSED,)),
        (answer(INVENTED), answer(INVENTED), (IN_ORDER, REVERSED)),
        (answer(), answer(), ()),
    ],
    ids=["in order", "reversed", "both", "neither"],
)
def test_the_orders_whose_quotation_is_not_in_the_advisory_are_named(
    in_order, reversed_order, unverified
):
    assert unverified_in(OrderReadings(in_order, reversed_order), SHOWN) == unverified


def test_a_decline_and_a_guess_quote_nothing_so_neither_is_a_quotation_not_found():
    guess = MemberGuessed("AV", "N", WHO)
    assert unverified_in(OrderReadings(decline(), guess), SHOWN) == ()


def test_both_orders_are_added_to_what_the_member_said_and_nothing_else_changes():
    named = Named("small-local", "ollama", "small:1b", "small", True, "v-in-order", "v-rev")
    said = MemberSaid(named, SaidKind.DECLINED)
    added = in_both_orders(said, OrderReadings(answer(INVENTED), decline()), SHOWN)
    assert (added.declined_in, added.unverified_in) == ((REVERSED,), (IN_ORDER,))
    assert (added.member, added.kind, added.value) == (said.member, said.kind, said.value)


def test_a_guess_in_one_order_is_in_neither_list_which_is_the_known_gap():
    """The gap this record leaves, asserted so that closing it cannot happen unremarked."""
    # RED HERE MEANS THE GAP HAS BEEN CLOSED, not that something broke. A guess
    # quotes nothing and names a value, so it is neither a decline nor a quotation
    # not found, and the record cannot say which order of a member's two guessed.
    both = OrderReadings(answer(), MemberGuessed("AV", "N", WHO))
    assert (declined_in(both), unverified_in(both, SHOWN)) == ((), ())

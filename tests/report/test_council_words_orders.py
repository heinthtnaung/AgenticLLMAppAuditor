"""Guards on naming the order a member declined in, where only one of its two orders did."""

import pytest

from report.council_record import MemberIdentity, MemberSaid, ReadingOrder, SaidKind
from report.council_words import declined_one_way

WHO = MemberIdentity("small-local", "ollama", "small:1b", "small", True, "v-in", "v-reversed")
IN_ORDER, REVERSED = ReadingOrder.IN_ORDER, ReadingOrder.REVERSED


@pytest.mark.parametrize(
    ("declined", "unverified", "said"),
    [
        ((REVERSED,), (), ["with the options reversed: declined"]),
        ((IN_ORDER,), (), ["with the options in order: declined"]),
        ((), (REVERSED,), ["with the options reversed: quotation not found in the advisory"]),
        (
            (IN_ORDER,), (REVERSED,),
            [
                "with the options in order: declined",
                "with the options reversed: quotation not found in the advisory",
            ],
        ),
    ],
    ids=["declined reversed", "declined in order", "misquoted reversed", "one of each"],
)
def test_an_order_that_declined_alone_is_named(declined, unverified, said):
    member = MemberSaid(WHO, SaidKind.DECLINED, declined_in=declined, unverified_in=unverified)
    assert declined_one_way(member) == said


@pytest.mark.parametrize(
    ("declined", "unverified"),
    [((IN_ORDER, REVERSED), ()), ((), (IN_ORDER, REVERSED)), ((), ())],
    ids=["declined both ways", "misquoted both ways", "neither, or asked once"],
)
def test_no_order_is_named_where_both_did_the_same_or_neither_declined(declined, unverified):
    member = MemberSaid(WHO, SaidKind.DECLINED, declined_in=declined, unverified_in=unverified)
    assert declined_one_way(member) == []

"""Which order of the options a member declined in, read off its two readings of one metric.

`council.order_check` makes a member's two readings one reply, and a decline in
either order is a decline, so the one reply cannot say which order declined. The
run keeps both readings (`council.run.OrderReadings`), and this reads them.

**Two ways to decline, kept apart as the record keeps them.** Saying
`NO_EVIDENCE` is the record's `declined`; quoting text the advisory does not
contain is its `evidence_verified` false. A guess quotes nothing and is neither.

**Nothing here moves a ruling.** The chairman has already ruled on the one
reply by the time this runs, and it reads nothing this writes.
"""

from dataclasses import replace

from council.answer import MemberAnswer, MemberFoundNoEvidence
from council.evidence import is_quotation_from
from council.order_check import Reading
from council.run import OrderReadings
from report.council_record import MemberSaid, ReadingOrder


def in_both_orders(said: MemberSaid, readings: OrderReadings, advisory_shown: str) -> MemberSaid:
    """Add to what a member said the orders it declined in, and those it misquoted in."""
    return replace(
        said,
        declined_in=declined_in(readings),
        unverified_in=unverified_in(readings, advisory_shown),
    )


def declined_in(readings: OrderReadings) -> tuple[ReadingOrder, ...]:
    """Name the orders in which a member said the advisory offers no evidence."""
    pairs = by_order(readings)
    return tuple(order for order, one in pairs if isinstance(one, MemberFoundNoEvidence))


def unverified_in(readings: OrderReadings, advisory_shown: str) -> tuple[ReadingOrder, ...]:
    """Name the orders in which a member quoted text the advisory does not contain."""
    pairs = by_order(readings)
    return tuple(order for order, one in pairs if misquoted(one, advisory_shown))


def misquoted(reading: Reading, advisory_shown: str) -> bool:
    """Say whether a reading offered a quotation the advisory does not contain."""
    if not isinstance(reading, MemberAnswer):
        return False
    return not is_quotation_from(reading.evidence, advisory_shown)


def by_order(readings: OrderReadings) -> tuple[tuple[ReadingOrder, Reading], ...]:
    """Pair each of a member's two readings with the order it was read in."""
    return (
        (ReadingOrder.IN_ORDER, readings.in_order),
        (ReadingOrder.REVERSED, readings.reversed_order),
    )

"""Saying a council run is alive, on the error stream and never on stdout.

A two-member roster over eighteen findings is 576 model calls, every metric
asked in both orders, and the runner makes them one after another: every call
waits for the one before it. The CPU full run took 71 min 39 s at half that
(`measurements/README.md`), and that much silence is indistinguishable from a
hung run.

**Never stdout.** `--format json` writes the audit record there and it has to
stay pipeable and byte-identical; progress and the record share a process and
nothing else.

**Counts, not timings, and the design makes that enough rather than merely
accepting it.** A line is printed *before* the call it describes, so a slow
member is a line that sits there -- which is how a reader sees which member is
slow, with their own perception supplying the elapsed time a clock would. There
is no clock anywhere in `src/`; it is what keeps the record byte-identical
between runs, it is asserted in `README.md`, `docs/diagrams.md` and
`docs/SCORING_MODEL.md`, and it is not worth narrowing all three to print a
number a reader already has.
"""

from dataclasses import dataclass, field
from typing import TextIO

METRICS_PER_FINDING = 8
# How many times each member is asked each metric: in the options' order, and reversed.
BOTH_ORDERS = 2
ONE_ORDER = 1
# Said after the metric on a reversed call, so its line is not the in-order call's twice.
REVERSED_LABEL = " (options reversed)"
COUNCIL_LINE = "council"
# An escalation call is counted apart: how many a run makes is known only once
# the council has left something open, so it has no total to count towards.
ESCALATION_LINE = "escalation"


@dataclass
class CouncilProgress:
    """How far a council run has got, said on the error stream as it goes.

    Mutable, unlike everything else here, because counting is state and the
    alternative is threading a counter through the call chain it is counting.
    """

    findings: int
    members: int
    out: TextIO
    # Each metric asked in the options' order and reversed, where the run checks both.
    orders: int = ONE_ORDER
    asked: int = field(default=0, init=False)
    escalated: int = field(default=0, init=False)
    reached: int = field(default=0, init=False)
    advisory_id: str = field(default="", init=False)

    @property
    def calls(self) -> int:
        """Give how many model calls the whole run will make."""
        return self.findings * METRICS_PER_FINDING * self.members * self.orders

    def starting(self, advisory_id: str) -> None:
        """Note that the council has moved on to another advisory."""
        self.reached += 1
        self.advisory_id = advisory_id

    def asking(self, metric: str, member: str, reversed_options: bool = False) -> None:
        """Say which member is about to be asked which metric, and in which order, before it is."""
        self.asked += 1
        self.say(f"{COUNCIL_LINE} {self.asked}/{self.calls}", metric, member, reversed_options)

    def escalating(self, metric: str, member: str, reversed_options: bool = False) -> None:
        """Say which metric the escalation model is about to be asked, and in which order."""
        self.escalated += 1
        self.say(f"{ESCALATION_LINE} {self.escalated}", metric, member, reversed_options)

    def say(self, counted: str, metric: str, member: str, reversed_options: bool) -> None:
        """Write the line for one call about to be made, flushed so it shows before the call."""
        order = REVERSED_LABEL if reversed_options else ""
        self.out.write(
            f"{counted}  finding {self.reached}/{self.findings} {self.advisory_id}  "
            f"{metric}{order}  {member}\n"
        )
        self.out.flush()


@dataclass(frozen=True)
class NoProgress:
    """Say nothing, which is what a run with nothing slow in it needs."""

    def starting(self, advisory_id: str) -> None:
        """Note nothing."""

    def asking(self, metric: str, member: str, reversed_options: bool = False) -> None:
        """Say nothing."""

    def escalating(self, metric: str, member: str, reversed_options: bool = False) -> None:
        """Say nothing."""


NO_PROGRESS = NoProgress()


def orders_asked(order_check: bool) -> int:
    """Give how many times each member is asked each metric, once or in both orders."""
    return BOTH_ORDERS if order_check else ONE_ORDER

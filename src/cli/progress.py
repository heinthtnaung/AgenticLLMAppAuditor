"""Saying a council run is alive, on the error stream and never on stdout.

A two-member roster over eighteen findings is 576 model calls, every metric
asked in both orders, and the runner makes them one after another: every call
waits for the one before it. The CPU full run took 71 min 39 s at half that
(`measurements/README.md`), and that much silence is indistinguishable from a
hung run.

**Never stdout.** `--format json` writes the audit record there and it has to
stay pipeable and byte-identical; progress and the record share a process and
nothing else.

**One line per call, or one bar.** A terminal gets one line per phase, redrawn in
place (`cli.progress_bar`); a redirected stream and `--debug` both get the full
log, one line per call, so a saved run keeps every member it named. Which one is
chosen is the stream's `isatty()` and the flag; the counting below is the same
either way.

**Counts, not timings, and the design makes that enough rather than merely
accepting it.** Both displays print *before* the call, and neither carries a
clock: the bar supplies a running count and a percentage, and the log prints one
line per call naming the member it is about to ask. So in the log -- off a
terminal, or under `--debug` -- a slow member is a line that sits there naming
it, which is how `--debug` shows which model is slow; the bar names no member and
a reader there supplies the elapsed time from the frame that stops advancing.
There is no clock anywhere in `src/`; it is what keeps the record byte-identical
between runs, it is asserted in `docs/USAGE.md`, `docs/SETUP.md`,
`docs/DEVELOPMENT.md`, `docs/diagrams.md` and `docs/SCORING_MODEL.md`, and it
is not worth narrowing all five to print a number a reader already has.
"""

from dataclasses import dataclass, field
from typing import TextIO

from cli.progress_bar import BarDisplay, bar_for

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
# One call per finding whose sources disagree, made once the council is done.
EXPLANATION_LINE = "explanation"


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
    # The log is the default; `--debug` keeps it even at a terminal, where a bar is drawn instead.
    debug: bool = False
    asked: int = field(default=0, init=False)
    escalated: int = field(default=0, init=False)
    reached: int = field(default=0, init=False)
    advisory_id: str = field(default="", init=False)
    bar: BarDisplay | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Choose the display once the stream is known: a bar on a terminal, else the log."""
        self.bar = bar_for(self.out, self.debug)

    @property
    def calls(self) -> int:
        """Give how many model calls the whole run will make."""
        return self.findings * METRICS_PER_FINDING * self.members * self.orders

    def starting(self, advisory_id: str) -> None:
        """Note that the council has moved on to another advisory."""
        self.reached += 1
        self.advisory_id = advisory_id

    def returning_to(self, position: int, advisory_id: str) -> None:
        """Note that escalation has come back to an advisory the council read earlier in the run."""
        # Set, not counted: the council reached it already, at this place among the findings.
        self.reached = position
        self.advisory_id = advisory_id

    def asking(self, metric: str, member: str, reversed_options: bool = False) -> None:
        """Say which member is about to be asked which metric, and in which order, before it is."""
        self.asked += 1
        if self.bar is not None:
            self.bar.council(COUNCIL_LINE, self.asked, self.calls, self.reached, self.findings)
            return
        self.say(f"{COUNCIL_LINE} {self.asked}/{self.calls}", metric, member, reversed_options)

    def escalating(self, metric: str, member: str, reversed_options: bool = False) -> None:
        """Say which metric the escalation model is about to be asked, and in which order."""
        self.escalated += 1
        if self.bar is not None:
            self.bar.escalation(
                ESCALATION_LINE, self.escalated, self.reached, self.findings, self.advisory_id
            )
            return
        self.say(f"{ESCALATION_LINE} {self.escalated}", metric, member, reversed_options)

    def finish(self) -> None:
        """Close the bar's line so later output starts fresh; nothing to do for the log."""
        if self.bar is not None:
            self.bar.finish()

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

    def returning_to(self, position: int, advisory_id: str) -> None:
        """Note nothing."""

    def asking(self, metric: str, member: str, reversed_options: bool = False) -> None:
        """Say nothing."""

    def escalating(self, metric: str, member: str, reversed_options: bool = False) -> None:
        """Say nothing."""

    def finish(self) -> None:
        """Note nothing."""


NO_PROGRESS = NoProgress()


@dataclass
class ExplanationProgress:
    """How far the explanations have got, said on the error stream before each call."""

    findings: int
    out: TextIO
    # The log is the default; `--debug` keeps it even at a terminal, where a bar is drawn instead.
    debug: bool = False
    asked: int = field(default=0, init=False)
    bar: BarDisplay | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Choose the display once the stream is known: a bar on a terminal, else the log."""
        self.bar = bar_for(self.out, self.debug)

    def explaining(self, advisory_id: str, model: str) -> None:
        """Say which finding the explainer is about to be asked about, before it is."""
        self.asked += 1
        if self.bar is not None:
            self.bar.explanation(EXPLANATION_LINE, self.asked, self.findings, advisory_id)
            return
        self.out.write(
            f"{EXPLANATION_LINE} {self.asked}/{self.findings}  finding {advisory_id}  {model}\n"
        )
        self.out.flush()

    def finish(self) -> None:
        """Close the bar's line so later output starts fresh; nothing to do for the log."""
        if self.bar is not None:
            self.bar.finish()


@dataclass(frozen=True)
class NoExplanationProgress:
    """Say nothing about explanations, which is what a run nobody is watching needs."""

    def explaining(self, advisory_id: str, model: str) -> None:
        """Say nothing."""

    def finish(self) -> None:
        """Note nothing."""


NO_EXPLANATION_PROGRESS = NoExplanationProgress()


def orders_asked(order_check: bool) -> int:
    """Give how many times each member is asked each metric, once or in both orders."""
    return BOTH_ORDERS if order_check else ONE_ORDER

"""Saying a council run is alive, on the error stream and never on stdout.

A two-member roster over eighteen findings is 288 model calls, and the runner
makes them one after another: every call waits for the one before it. The CPU
full run took 71 min 39 s (`measurements/README.md`), and that much silence is
indistinguishable from a hung run.

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


@dataclass
class CouncilProgress:
    """How far a council run has got, said on the error stream as it goes.

    Mutable, unlike everything else here, because counting is state and the
    alternative is threading a counter through the call chain it is counting.
    """

    findings: int
    members: int
    out: TextIO
    asked: int = field(default=0, init=False)
    reached: int = field(default=0, init=False)
    advisory_id: str = field(default="", init=False)

    @property
    def calls(self) -> int:
        """Give how many model calls the whole run will make."""
        return self.findings * METRICS_PER_FINDING * self.members

    def starting(self, advisory_id: str) -> None:
        """Note that the council has moved on to another advisory."""
        self.reached += 1
        self.advisory_id = advisory_id

    def asking(self, metric: str, member: str) -> None:
        """Say which member is about to be asked which metric, before it is asked."""
        self.asked += 1
        self.out.write(
            f"council {self.asked}/{self.calls}  "
            f"finding {self.reached}/{self.findings} {self.advisory_id}  "
            f"{metric}  {member}\n"
        )
        self.out.flush()


@dataclass(frozen=True)
class NoProgress:
    """Say nothing, which is what a run with nothing slow in it needs."""

    def starting(self, advisory_id: str) -> None:
        """Note nothing."""

    def asking(self, metric: str, member: str) -> None:
        """Say nothing."""


NO_PROGRESS = NoProgress()

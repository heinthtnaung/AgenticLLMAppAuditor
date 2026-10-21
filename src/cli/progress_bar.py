"""Drawing council progress as one line redrawn in place, for a terminal error stream.

The line-by-line log in `cli.progress` is the full record, and it stays the
default when the error stream is not a terminal and under `--debug`; a watcher at
a terminal sees this instead. It carries counts and a percentage and no timing:
there is no clock anywhere in `src/` (`cli.progress`), and a reader watching the
line redraw supplies the elapsed time a clock would. Every phase label is passed
in by `cli.progress`, so the bar and the log say the same words from one source.
"""

from dataclasses import dataclass, field
from typing import TextIO

# Eighteen cells wide, so the bar and its counts sit well inside one terminal line.
BAR_WIDTH = 18
FILLED = "█"  # a full block, one column wide
EMPTY = "░"  # a light-shaded block, one column wide
# Return to the first column without a newline, so the next frame overwrites this one.
RETURN = "\r"
# Ends a phase's line, so the next phase and any later output start below it, not on it.
NEWLINE = "\n"
# One under eighty, so the padded line never wraps an eighty-column terminal onto a second row.
LINE_WIDTH = 79
WHOLE = 100
NO_PHASE = ""


def filled_cells(done: int, total: int) -> int:
    """Give how many of the bar's cells are filled at this fraction, clamped to the bar's width."""
    if total <= 0:
        return 0
    return min(BAR_WIDTH, done * BAR_WIDTH // total)


def percent(done: int, total: int) -> int:
    """Give the whole-number percentage done, clamped to a hundred and zero for an empty run."""
    if total <= 0:
        return 0
    return min(WHOLE, done * WHOLE // total)


def bar(done: int, total: int) -> str:
    """Draw the fixed-width bar filled to the run's fraction, framed in brackets."""
    filled = filled_cells(done, total)
    return f"[{FILLED * filled}{EMPTY * (BAR_WIDTH - filled)}]"


@dataclass
class BarDisplay:
    """One progress line redrawn in place, a new line begun each time the phase changes."""

    out: TextIO
    phase: str = field(default=NO_PHASE, init=False)

    def council(self, label: str, done: int, total: int, reached: int, findings: int) -> None:
        """Redraw the council bar: a bar, the call count, the percentage, and which finding."""
        self.enter(label)
        counts = f"{done}/{total}  {percent(done, total)}%"
        self.redraw(f"{label} {bar(done, total)} {counts}  finding {reached}/{findings}")

    def escalation(
        self, label: str, done: int, reached: int, findings: int, advisory_id: str
    ) -> None:
        """Redraw the escalation line: a running count, since the run cannot know its total yet."""
        self.enter(label)
        self.redraw(f"{label} {done}  finding {reached}/{findings} {advisory_id}")

    def explanation(self, label: str, done: int, total: int, advisory_id: str) -> None:
        """Redraw the explanation bar: one call per disputed finding, so it has its own total."""
        self.enter(label)
        counts = f"{done}/{total}  {percent(done, total)}%"
        self.redraw(f"{label} {bar(done, total)} {counts}  finding {advisory_id}")

    def finish(self) -> None:
        """End the open line with a newline, so later output starts below the bar, not on it."""
        if self.phase == NO_PHASE:
            return
        self.out.write(NEWLINE)
        self.out.flush()
        self.phase = NO_PHASE

    def enter(self, phase: str) -> None:
        """Close the previous phase's line when the phase changes, so each gets its own line."""
        if self.phase not in (NO_PHASE, phase):
            self.out.write(NEWLINE)
        self.phase = phase

    def redraw(self, line: str) -> None:
        """Rewrite one line in place, padded to a fixed width so a shorter frame clears the last."""
        self.out.write(RETURN + line[:LINE_WIDTH].ljust(LINE_WIDTH))
        self.out.flush()


def bar_for(out: TextIO, debug: bool) -> BarDisplay | None:
    """Give a bar to redraw in place on a terminal, or None for the line-by-line log."""
    # `--debug` and a redirected stream both want the full log, so the bar is for neither.
    if debug or not out.isatty():
        return None
    return BarDisplay(out)

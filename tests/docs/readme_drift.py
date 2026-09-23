"""Two ways of asking whether a README block still reproduces, and the report when it does not.

**A block printed whole is compared whole.** Every line, in place, against the
same run of the tool's output -- so a row whose number changed catches even if
another row moved to cover for it. `technical-writer-1` regenerates those blocks
from a run and pastes them entire rather than hand-editing a column, which is
what makes the strict comparison safe to apply.

**A block marked `(elided)` gets the weaker check**, because it has to: the
README's first output block drops three of five disagreements and eleven of
thirteen agreements, which is right for a reader and cannot be compared entire.
Its lines are asked to appear, in the order it prints them, and nothing more.
**So that block cannot catch a line the tool has newly inserted between two it
prints, nor one appended after the last.** Only the marker decides which check
runs; inferring it would mean trying the strict one and falling back, which
downgrades a block on the very day it drifts.

One line is deliberately not compared to the end. The provenance line carries
the advisory database's build date, which changes on a routine refresh without
the README being wrong, so everything up to `built ` is compared and the date is
not -- which still fails a Syft or Trivy version bump, as it should.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import zip_longest
from typing import Iterator

PROVENANCE = re.compile(r"^  syft .* advisory database built ")

UNCHANGED = "equal"

NOTHING_THERE = "(nothing is printed there now)"
NOT_ON_THE_PAGE = "(the block does not print this line)"
NO_MATCH = "(nothing here matches; read the full output below)"
OUT_OF_ORDER = "(still printed, but no longer in this position)"


@dataclass(frozen=True)
class Drift:
    """One README line and whatever the tool prints where that line used to be."""

    printed: str
    current: str


def stable(line: str) -> str:
    """Drop the tail of a line that moves without the README being wrong."""
    dated = PROVENANCE.match(line)
    return dated.group(0) if dated else line


def drift_of(printed: tuple[str, ...], printed_now: list[str], elided: bool) -> list[Drift]:
    """Compare one README block against the output it claims to be, as strictly as it allows."""
    if elided:
        return elided_drift([line for line in printed if line.strip()], printed_now)
    return whole_block_drift(list(printed), printed_now)


def whole_block_drift(printed: list[str], printed_now: list[str]) -> list[Drift]:
    """Give every way a block printed whole differs from the run of output it claims to be."""
    comparable = [stable(line) for line in printed_now]
    at = best_alignment([stable(line) for line in printed], comparable)
    return list(differences(printed, printed_now[at : at + len(printed)]))


def differences(printed: list[str], window: list[str]) -> Iterator[Drift]:
    """Walk the page against the output beside it, so a missing line is not read as changed."""
    page = [stable(one) for one in printed]
    matcher = SequenceMatcher(None, page, [stable(one) for one in window])
    for tag, page_from, page_to, output_from, output_to in matcher.get_opcodes():
        if tag == UNCHANGED:
            continue
        yield from paired(printed[page_from:page_to], window[output_from:output_to])


def paired(was: list[str], now: list[str]) -> list[Drift]:
    """Line up one run of changed lines against its replacement, naming a gap on either side."""
    filled = zip_longest(was, now, fillvalue="")
    return [Drift(page or NOT_ON_THE_PAGE, output or NOTHING_THERE) for page, output in filled]


def best_alignment(printed: list[str], comparable: list[str]) -> int:
    """Give the offset where the block lines up with most of the output, for the clearest report."""
    starts = range(max(1, len(comparable) - len(printed) + 1))
    return max(starts, key=lambda at: agreeing(printed, comparable[at : at + len(printed)]))


def agreeing(printed: list[str], aligned: list[str]) -> int:
    """Count the lines two runs of text share at the same position."""
    return sum(1 for was, now in zip(printed, aligned) if was == now)


def looks_elided(printed: tuple[str, ...], printed_now: list[str]) -> bool:
    """Say whether every line of an unmarked block does appear in order, just not as one run."""
    # The only evidence that lets a failure suggest `(elided)`. Suggesting it
    # anywhere else would invite somebody to silence a genuinely stale block.
    return not elided_drift([line for line in printed if line.strip()], printed_now)


def elided_drift(printed: list[str], printed_now: list[str]) -> list[Drift]:
    """Give the lines a selective block no longer prints in order, and what stands where each is."""
    comparable = [stable(line) for line in printed_now]
    gone: list[Drift] = []
    at = 0
    for line in printed:
        where = placed(stable(line), comparable, at)
        if where < 0:
            where = alike(line, printed_now, at)
            gone.append(Drift(line, standing_at(line, comparable, printed_now, where)))
        at = max(at, where + 1)
    return gone


def placed(wanted: str, comparable: list[str], at: int) -> int:
    """Give where a line next appears in the output after the last one that matched, or -1."""
    return comparable.index(wanted, at) if wanted in comparable[at:] else -1


def alike(line: str, printed_now: list[str], at: int) -> int:
    """Give the one later line starting the way a README line does, or -1 where there is no one."""
    # Only a sole candidate is offered. An advisory id appears in several
    # sections, so naming the wrong one reads as a correction and is worse
    # than admitting the pairing could not be made.
    starts = line.split()[0]
    matching = [i for i in range(at, len(printed_now)) if printed_now[i].split()[:1] == [starts]]
    return matching[0] if len(matching) == 1 else -1


def standing_at(line: str, comparable: list[str], printed_now: list[str], where: int) -> str:
    """Say what the tool prints in place of a README line, or why nothing could be paired to it."""
    if where >= 0:
        return printed_now[where]
    if stable(line) in comparable:
        return OUT_OF_ORDER
    return NO_MATCH

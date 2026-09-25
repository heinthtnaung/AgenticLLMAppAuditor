"""The first gate: does a roster replayed from the passes print what a recorded audit printed?

The recorded report and the replay are read by one parser, the replay rendered
first by the product's own `report.text_council.advisory_lines`. So everything a
reader of the report sees is compared -- each heading and vector, each metric
the council could not settle, and every member's kind, value, confidence,
verification and quotation -- and nothing about the layout is.

**Two changes since the recorded runs are allowed for, by name.** Quotations
are compared with their whitespace removed, because the renderer has stopped
breaking lines at hyphens. And the basis lines are reconciled rather than
matched: before `4526250` a value one member quoted alone read "every member
that offered a quotation supported this value", which is now `SOLE`. So in a
recording that names no `SOLE`, the `AGREED` count must equal the replay's
`AGREED` and `SOLE` together and `EVIDENCE` must match; a recording that names
`SOLE` was rendered after the change and must match exactly. The sum is the
one place the gate is weaker than the report: in a pre-`SOLE` recording, which
of those settled metrics one member quoted alone is not written down anywhere.
"""

import re
from dataclasses import dataclass
from itertools import chain
from typing import Iterable, Mapping

from council.ruling import Basis
from report.council_record import CouncilOutcome
from report.council_words import SETTLED
from report.text_council import ADVISORY_DEPTH, QUOTATION_DEPTH, advisory_lines
from report.text_layout import INDENT

BLOCK_OPENING = "COUNCIL ("
SETTLED_LINE = re.compile(rf"^(\d+) metrics? {SETTLED}$")
BASIS_LINE = re.compile(r"^(\d+)  (.+)$")
BASIS_WORDS = {basis.value for basis in Basis}


@dataclass(frozen=True)
class FindingFacts:
    """What the report shows about one finding, with its layout taken out."""

    heading: str
    settled: int
    bases: Mapping[str, int]
    entries: tuple[str, ...]


def recorded_findings(report_text: str) -> dict[str, FindingFacts]:
    """Read the council block of a recorded text report into facts per finding."""
    lines = report_text.splitlines()
    openings = [i for i, line in enumerate(lines) if line.startswith(BLOCK_OPENING)]
    if len(openings) != 1:
        raise ValueError(f"a report has one {BLOCK_OPENING!r} block; this one has {len(openings)}")
    block = lines[openings[0] + 1 :]
    return findings_of(block[: block.index("")] if "" in block else block)


def replayed_findings(outcomes: Iterable[CouncilOutcome]) -> dict[str, FindingFacts]:
    """Render replayed records as the report would, and read them back into facts per finding."""
    return findings_of(list(chain.from_iterable(advisory_lines(one) for one in outcomes)))


def findings_of(lines: list[str]) -> dict[str, FindingFacts]:
    """Split a council block at each finding's heading and read each finding."""
    starts = [i for i, line in enumerate(lines) if depth(line) == ADVISORY_DEPTH]
    ends = [*starts[1:], len(lines)]
    chunks = [lines[start:end] for start, end in zip(starts, ends)]
    return {chunk[0].split()[0]: facts_of(chunk) for chunk in chunks}


def facts_of(chunk: list[str]) -> FindingFacts:
    """Read one finding: its heading, its settled count, its bases, and everything unsettled."""
    body = [(depth(line), line.strip()) for line in chunk[1:]]
    texts = [text for _, text in body]
    rest = [(level, text) for level, text in body if not is_count(text)]
    return FindingFacts(chunk[0].strip(), settled_count(texts), basis_counts(texts), merged(rest))


def is_count(text: str) -> bool:
    """Say whether a line counts settled metrics, in total or under one basis."""
    return bool(SETTLED_LINE.match(text)) or is_basis(text)


def settled_count(texts: list[str]) -> int:
    """Give how many metrics a finding's lines say were settled."""
    found = [SETTLED_LINE.match(text) for text in texts]
    return sum(int(one.group(1)) for one in found if one)


def basis_counts(texts: list[str]) -> dict[str, int]:
    """Give how many settled metrics each basis carries, by its words."""
    return dict(basis_count(text) for text in texts if is_basis(text))


def is_basis(text: str) -> bool:
    """Say whether a line counts settled metrics under one basis."""
    found = BASIS_LINE.match(text)
    return bool(found) and found.group(2) in BASIS_WORDS


def basis_count(text: str) -> tuple[str, int]:
    """Read one basis line as the basis and its count."""
    found = BASIS_LINE.match(text)
    return found.group(2), int(found.group(1))


def merged(body: list[tuple[int, str]]) -> tuple[str, ...]:
    """Join each quotation's lines onto the member line above it, whitespace removed."""
    entries: list[str] = []
    for level, text in body:
        if level == QUOTATION_DEPTH and entries:
            entries[-1] += "".join(text.split())
            continue
        entries.append(text)
    return tuple(entries)


def depth(line: str) -> int:
    """Give how many indents deep a line of the block sits."""
    return (len(line) - len(line.lstrip(" "))) // len(INDENT)


def differences(
    recorded: Mapping[str, FindingFacts], replayed: Mapping[str, FindingFacts]
) -> list[str]:
    """Name every way the replay differs from the recording; none is the gate passing."""
    unmatched = sorted(set(recorded) ^ set(replayed))
    found = [f"{key} is in only one of the two" for key in unmatched]
    shared = [key for key in recorded if key in replayed]
    each = [finding_differences(key, recorded[key], replayed[key]) for key in shared]
    return found + list(chain.from_iterable(each))


def finding_differences(key: str, old: FindingFacts, new: FindingFacts) -> list[str]:
    """Name every way one finding differs, the basis lines reconciled rather than matched."""
    found = []
    if old.heading != new.heading:
        found.append(f"{key}: heading {old.heading!r} is now {new.heading!r}")
    if old.settled != new.settled:
        found.append(f"{key}: {old.settled} settled is now {new.settled}")
    if not bases_reconcile(old.bases, new.bases):
        found.append(f"{key}: bases {dict(old.bases)} do not reconcile with {dict(new.bases)}")
    found.extend(entry_differences(key, old.entries, new.entries))
    return found


def entry_differences(key: str, old: tuple[str, ...], new: tuple[str, ...]) -> list[str]:
    """Name each unsettled-metric line that differs, and a difference in how many there are."""
    found = [f"{key}: {was!r} is now {now!r}" for was, now in zip(old, new) if was != now]
    if len(old) != len(new):
        found.append(f"{key}: {len(old)} unsettled lines are now {len(new)}")
    return found


def bases_reconcile(old: Mapping[str, int], new: Mapping[str, int]) -> bool:
    """Say whether recorded bases match the replay's, `SOLE` counted under a pre-`SOLE` `AGREED`."""
    # A recording that names SOLE was rendered after the change, and must match exactly.
    if Basis.SOLE.value in old:
        return dict(old) == dict(new)
    agreed = new.get(Basis.AGREED.value, 0) + new.get(Basis.SOLE.value, 0)
    same_agreed = old.get(Basis.AGREED.value, 0) == agreed
    return same_agreed and old.get(Basis.EVIDENCE.value, 0) == new.get(Basis.EVIDENCE.value, 0)

"""The markers on the page, and every way one can go missing without anybody noticing.

`README.md` prints real CLI output beside the answer file that produced it, and
twice in one afternoon a rendering change left those blocks false while the
suite stayed green. Each block carries an HTML comment naming the command that
made it, invisible where the page renders:

    <!-- readme-check: answers -->                          the answer file the runs are given
    <!-- readme-check: run (elided) -->                     the audit with no answers
    <!-- readme-check: run --answers -->                    with that file as it stands
    <!-- readme-check: run --answers EXP-1=No EXP-4=Yes --> with two answers changed

**The protection has to sit at the block, not at the page.** Refusing a page
that has lost *every* marker is not enough: one marker deleted, misspelled, or
pushed off its fence by a blank line takes its own block out of the check while
every other block still passes and the suite stays green. That is the same
silent-success defect this project refuses everywhere else -- an empty advisory
database exiting 0, an omitted answer scored as `No` -- reappearing inside the
guard written to prevent it. So two things hold here:

**The number of runs is pinned.** A count somebody has to bump is cheap, and it
fails both ways *for a marker*: one added without its block fails, and one
removed from its block fails. It says nothing whatever about a block that never
carried a marker, which is the gap named at the end of this docstring.

**A comment that was meant to be a marker is named, not skipped.** Anything
whose first word mentions this check but which the marker pattern cannot read
is reported with its line and its text, which is what tells a misspelling and a
detached marker apart from a block nobody meant to check.

**One gap is left open, and it is named here rather than assumed covered.** Both
of those guard a marker that exists. Neither notices **an output block pasted
onto the page carrying no marker at all**: the count of marked blocks is still
right, there is no malformed comment to spot, and that block is unchecked from
birth. Two rules would close it and both were turned down. Requiring every fence
in the usage section to be marked needs a boundary the page does not have, which
the test would be drawing on the writer's behalf. Requiring it of any fence
holding a report heading needs this file to keep its own copy of `SOURCES
DISAGREE` and the rest, which are inline literals in `src/report` -- and a copy
goes stale in the direction that hides, because after a rename the marked blocks
fail loudly while the detector quietly stops detecting.

**The gap is narrower than that, and still open.** `readme_tool_output` pairs
each printed fence with the nearest `bash` fence above it, and
`test_readme_markers.py` asserts that exactly one fence following a command
that starts this tool carries no marker: the council progress under "A council
run says where it has got to". It is a council run's stderr and needs Ollama,
so no `run` marker can rerun it. An unmarked block pasted after an `audit`
command is caught by that count. One pasted where no `audit` command is the
nearest above it -- at the end of the page, or under a Trivy command -- is not,
and `test_a_block_pasted_with_no_marker_is_not_noticed_which_is_the_known_gap`
asserts that case.

So the mitigation is still partly the writer's, and the disclosure is this
file's. Every fence showing this tool's output carries a marker except the
council progress; three `run` blocks carry one today, and a fourth arrives with
its marker and a raised `EXPECTED_RUN_BLOCKS` in the same change. What this
file adds is the unmarked fences printed beside **any** failure it reports --
which puts an uncovered block in front of somebody already reading a failure,
and in front of nobody at all while the rest of the page is right.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
README_PATH = PROJECT_ROOT / "README.md"

ANSWERS_DIRECTIVE = "answers"
RUN_DIRECTIVE = "run"

MARKED_BLOCK = re.compile(
    r"^<!-- readme-check: (?P<directive>[^\n]+?) -->\n```[^\n]*\n(?P<body>.*?)^```",
    re.MULTILINE | re.DOTALL,
)

# A comment whose first word mentions this check but which `MARKED_BLOCK` cannot
# read: a misspelling, or a marker a blank line has pushed off its fence. Only
# the first word is looked at, so prose mentioning the README is not caught.
NEAR_MARKER = re.compile(r"^<!--\s*\S*readme\S*[\s:]+[^\n]*-->\s*$", re.MULTILINE | re.IGNORECASE)
FENCE = re.compile(r"^```(?P<language>[^\n]*)\n(?P<body>.*?)^```", re.MULTILINE | re.DOTALL)

EXPECTED_RUN_BLOCKS = 3
FIRST_LINE_SHOWN = 72

UNMARKED_HEADING = (
    "Fences that print something and carry no marker above them. A block pasted in "
    "without one is never checked, and nothing else here will say so:"
)


def read_readme() -> str:
    """Give the README this project publishes."""
    return README_PATH.read_text(encoding="utf-8")


def line_of(page: str, offset: int) -> int:
    """Give the one-based line an offset falls on, so a failure can cite the page."""
    return page.count("\n", 0, offset) + 1


def found_blocks(page: str) -> list[tuple[str, str, int]]:
    """Give every readable marked block as its directive, its body, and its marker's line."""
    return [
        (match.group("directive").strip(), match.group("body"), line_of(page, match.start()))
        for match in MARKED_BLOCK.finditer(page)
    ]


def marked_blocks(page: str) -> list[tuple[str, str, int]]:
    """Give the marked blocks, refusing a page that has lost every one of its markers."""
    found = found_blocks(page)
    if found:
        return found
    raise ValueError(
        f"{README_PATH} carries no '<!-- readme-check: ... -->' marker, so this check has "
        "nothing to reproduce; the markers were renamed, moved off their fences, or removed"
    )


def refuse_stray_markers(page: str) -> None:
    """Refuse a marker this check cannot read, whose block would otherwise drop out in silence."""
    readable = {line for _, _, line in found_blocks(page)}
    strays = [
        f"{README_PATH}:{line_of(page, one.start())}  {one.group(0).strip()}"
        for one in NEAR_MARKER.finditer(page)
        if line_of(page, one.start()) not in readable
    ]
    if not strays:
        return
    named = "\n".join(f"  {one}" for one in strays)
    raise ValueError(
        "this is meant to be a marker and cannot be read, so its block is not being "
        "checked; the spelling is '<!-- readme-check: ... -->' and it goes on the line "
        f"directly above its fence, with no blank line between:\n{named}"
    )


def refuse_wrong_count(found: int, page: str) -> None:
    """Refuse a page with the wrong number of marked runs, naming the fences carrying no marker."""
    if found == EXPECTED_RUN_BLOCKS:
        return
    raise ValueError(
        f"{README_PATH} marks {found} '{RUN_DIRECTIVE}' blocks and this check expects "
        f"{EXPECTED_RUN_BLOCKS}. A marker lost to a deletion or a typo takes its block out "
        "of the check while every other block still passes, so the count is pinned: raise "
        "EXPECTED_RUN_BLOCKS in readme_markers.py if the page documents another run on "
        f"purpose.\n{unmarked_note(page)}"
    )


def unmarked_note(page: str) -> str:
    """Give the unmarked fences under a heading, to go beside any failure this check reports."""
    # Printed whether or not the count is short. It is the only output that can
    # surface a block nobody ever marked, which no count and no malformed
    # comment will ever notice -- see this file's docstring on the gap left open.
    return "\n".join([UNMARKED_HEADING, *(f"  {one}" for one in unmarked_fences(page))])


def unmarked_fences(page: str) -> list[str]:
    """Name the fences printing output with no marker above them, for a count that came up short."""
    marked = {line for _, _, line in found_blocks(page)}
    plain = [one for one in FENCE.finditer(page) if not one.group("language").strip()]
    return [described(page, one) for one in plain if line_of(page, one.start()) - 1 not in marked]


def described(page: str, fence: re.Match) -> str:
    """Give one fence as its line and its first printed line, so a reader can find it."""
    printed = [line for line in fence.group("body").splitlines() if line.strip()]
    opens = printed[0].strip()[:FIRST_LINE_SHOWN] if printed else "(prints nothing)"
    return f"{README_PATH}:{line_of(page, fence.start())}  {opens}"

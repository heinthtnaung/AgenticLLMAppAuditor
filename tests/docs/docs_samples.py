"""Damaging one marker on a page, and the blocks a test pastes onto one, for the guards' tests.

**The damage is always derived from the parsed page, never from a quoted
string.** A test that pastes in today's wording stops testing anything the day
the page is reworded, and passes -- which is the failure the whole docs check
exists to refuse, so it may not be committed inside the tests written to prove
it does not happen. Every helper here that finds its target raises rather than
return the page unchanged, because a mutation that mutated nothing is exactly
that failure.
"""

from cli.arguments import PROGRAM
from doc_markers import MARKER_NAME, RUN_DIRECTIVE, found_blocks
from doc_pages import Page, rewritten
from doc_runs import REPOSITORY, PrintedRun, printed_runs

# A block in the shape of a report, with numbers no run prints, as if pasted in.
UNMARKED_OUTPUT = (
    "```\n"
    "ORGANISATION RISK (18)  ·  the source changes the band on 99\n"
    "  CVE-2021-4279        ghsa 11.1 to nvd 22.2       Nonsense\n"
    "```"
)
MARKED_OUTPUT = f"<!-- {MARKER_NAME}: {RUN_DIRECTIVE} --answers -->\n{UNMARKED_OUTPUT}"
AUDIT_COMMAND = f"```bash\n{PROGRAM} {REPOSITORY}\n```"
# A command that is not this tool's, so the fence under it is not read as its output.
OTHER_COMMAND = "```bash\ntrivy --version\n```"


def run_changing_an_answer(page: Page) -> PrintedRun:
    """Give a documented run whose marker changes an answer, refusing a page where none does."""
    carrying = [one for one in printed_runs(page) if one.edits]
    if carrying:
        return carrying[0]
    raise ValueError("no marker on the page changes an answer, so this test would check nothing")


def marker_changed(page: Page, run: PrintedRun, old: str, new: str) -> Page:
    """Give the page with one marker's text altered, refusing a change that would alter nothing."""
    return line_changed(page, run.line_number, old, new)


def line_changed(page: Page, line_number: int, old: str, new: str) -> Page:
    """Give the page with one line's text altered, refusing a change that would alter nothing."""
    lines = page.text.splitlines(keepends=True)
    changed = lines[line_number - 1].replace(old, new)
    if changed == lines[line_number - 1]:
        raise ValueError(f"line {line_number} carries no {old!r} to change")
    lines[line_number - 1] = changed
    return rewritten(page, "".join(lines))


def marker_lines(page: Page, directive_word: str) -> list[int]:
    """Give the line each marker of one kind sits on, read off the page rather than quoted."""
    blocks = found_blocks(page)
    found = [line for directive, _, line in blocks if directive.split()[0] == directive_word]
    if found:
        return found
    raise ValueError(f"no '{directive_word}' marker on the page to damage, so nothing was tested")


def without_line(page: Page, line_number: int) -> Page:
    """Give the page with one line gone, as a deletion would leave it."""
    lines = page.text.splitlines(keepends=True)
    del lines[line_number - 1]
    return rewritten(page, "".join(lines))


def page_with(page: Page, addition: str) -> Page:
    """Give the page with something appended, which is where a new block would be least noticed."""
    return rewritten(page, f"{page.text}\n\n{addition}\n")

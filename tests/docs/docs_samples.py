"""Damaging one marker on the page, for the tests that check a damaged marker is refused.

**The damage is always derived from the parsed page, never from a quoted
string.** A test that pastes in today's wording stops testing anything the day
the page is reworded, and passes -- which is the failure the whole README check
exists to refuse, so it may not be committed inside the tests written to prove
it does not happen. Both helpers here raise rather than return the page
unchanged, because a mutation that mutated nothing is exactly that failure.
"""

from readme_runs import PrintedRun, printed_runs


def run_changing_an_answer(page: str) -> PrintedRun:
    """Give a documented run whose marker changes an answer, refusing a page where none does."""
    carrying = [one for one in printed_runs(page) if one.edits]
    if carrying:
        return carrying[0]
    raise ValueError("no marker on the page changes an answer, so this test would check nothing")


def marker_changed(page: str, run: PrintedRun, old: str, new: str) -> str:
    """Give the page with one marker's text altered, refusing a change that would alter nothing."""
    lines = page.splitlines(keepends=True)
    at = run.line_number - 1
    changed = lines[at].replace(old, new)
    if changed == lines[at]:
        raise ValueError(f"the marker at line {run.line_number} carries no {old!r} to damage")
    lines[at] = changed
    return "".join(lines)

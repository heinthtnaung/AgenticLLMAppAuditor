"""After forgetting runs, the history is re-read from the server -- and read at the right moment.

Split from `test_jsx_forget_report.py`, which holds what the page *tells a
reader*. This is how it re-reads the list, a second claim about the same
function, and it had two defects of its own.

**Re-read rather than spliced.** `stored_run_count` and the cap are the
server's figures. A page that removed the row locally would go on reporting the
old total beside a shorter list, and the group headers -- which say "N shown" --
would be counting rows against a figure that no longer described them.

**And re-read once the whole loop is done.** *When* matters as much as whether:
a re-read raised before the loop, or inside it, fetches a history the deletes
have not finished changing, so the forgotten rows come straight back while the
report says they went. A row shown as present after the tool reported it gone is
the same fact-shaped falsehood this project spends its design refusing, at page
scale.

**Both claims were present-somewhere checks until 2026-09-18, and both passed on
the page they were written to refuse.** `setRead((was) => was + 1)` moved above
the loop satisfied "the re-read is there"; `"}, [read]);"` searched across the
whole file satisfied "the fetch watches the counter" even when the array
belonged to some *other* effect. So the re-read is now joined to the loop's own
closing braces, and the dependency array is taken from the effect that actually
fetches. Each has its defect planted as a non-match, and the two-effect page is
written out in full rather than described.

What text cannot show: that React re-runs the effect, or that the fetch which
follows returns the shortened list. No test in this suite renders React -- a
recorded defect, not one this file closes.

Reads one page as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

PAGE = FRONTEND_SRC / "pages" / "HistoryPage.jsx"

# The re-read, and where it has to sit. The two closing braces are the catch
# block's and the loop's -- `test_jsx_forget_report.py::THE_CAUGHT_LOOP` is what
# pins that shape -- so this says the re-read follows the whole loop rather than
# appearing somewhere in the file.
# The loop's two closing braces, then the re-read. `setWorking(false)` and
# `setPicked(new Set())` were added between them on 2026-09-18, so the gap
# allows statements -- but not a `try` or a `for`, which is what would put the
# re-read back inside a loop and is the whole point of matching the braces.
THE_REREAD_AFTER_THE_LOOP = re.compile(
    r"\}\s*\}\s*(?:[^{}]*;\s*)*setRead\(\(was\) => was \+ 1\);")

# The two placements it refuses, written out so each plant is the real
# alternative rather than a strawman: before the loop, and inside it.
A_REREAD_BEFORE_THE_LOOP = (
    "    setRead((was) => was + 1);\n"
    "    for (const run of runs) {\n"
    "      try {\n        await forgetRun(run.run_id);\n      } catch (failure) {\n"
    "        refused.push(failure.message);\n      }\n    }\n")
A_REREAD_INSIDE_THE_LOOP = (
    "    for (const run of runs) {\n"
    "      try {\n        await forgetRun(run.run_id);\n      } catch (failure) {\n"
    "        refused.push(failure.message);\n      }\n"
    "      setRead((was) => was + 1);\n    }\n")

# What the effect that reads the history has to be watching. Taken from that
# effect rather than looked for in the file: a dependency array binds to one
# effect, and a page with two would satisfy a file-wide search with the array of
# whichever effect happened to carry the counter.
THE_EFFECT_OPENER = "useEffect("
THE_FETCH = "fetchHistory()"
THE_ARRAY_OPENER = "}, ["
THE_DEPENDENCY = "}, [read]);"

# Exactly that page: the fetch watching nothing, and a second effect carrying
# the counter.
A_COUNTER_ON_SOME_OTHER_EFFECT = (
    "  useEffect(() => {\n    fetchHistory().then(setHeld);\n  }, []);\n"
    "  useEffect(() => {\n    document.title = \"History\";\n  }, [read]);\n")


def page() -> str:
    """The history page's own source, comments stripped: its comments explain the timing in prose."""
    return strip_comments(PAGE.read_text(encoding="utf-8"))


def the_effect_that_fetches(text: str) -> str:
    """The one `useEffect` block that reads the history, or say how many there are."""
    blocks = [block for block in text.split(THE_EFFECT_OPENER) if THE_FETCH in block]
    assert len(blocks) == 1, f"expected one effect fetching the history, found {len(blocks)}"
    return blocks[0]


def dependency_of_the_fetching_effect(text: str) -> str:
    """The first dependency array closing that effect, which is the one it watches."""
    block = the_effect_that_fetches(text)
    assert THE_ARRAY_OPENER in block, (
        "the effect that fetches the history closes with no dependency array, so it "
        "re-runs on every render and watches nothing")
    opened = block.index(THE_ARRAY_OPENER)
    return block[opened:block.index(");", opened) + 2]


# --- the re-read happens, and happens last -------------------------------------

def test_the_list_is_re_read_once_the_whole_loop_is_done() -> None:
    """Re-read before or inside the loop and the forgotten rows come back, reported as gone."""
    assert THE_REREAD_AFTER_THE_LOOP.search(page())


def test_a_re_read_raised_before_the_loop_is_not_accepted() -> None:
    """Planted: a bare `setRead(...)` check passes on this page, and that page re-reads too early."""
    assert THE_REREAD_AFTER_THE_LOOP.search(A_REREAD_BEFORE_THE_LOOP) is None


def test_a_re_read_raised_inside_the_loop_is_not_accepted() -> None:
    """Planted: the other placement, which re-fetches once per run while deletes are in flight."""
    assert THE_REREAD_AFTER_THE_LOOP.search(A_REREAD_INSIDE_THE_LOOP) is None


# --- and the effect that fetches is the one watching it ------------------------

def test_the_effect_that_fetches_is_the_one_watching_that_counter() -> None:
    """A bump nothing watches re-reads nothing, and the page goes on showing the forgotten row."""
    assert dependency_of_the_fetching_effect(page()) == THE_DEPENDENCY


def test_a_counter_watched_by_some_other_effect_is_not_accepted() -> None:
    """Planted: exactly the two-effect page a file-wide search for the array would have passed."""
    assert dependency_of_the_fetching_effect(A_COUNTER_ON_SOME_OTHER_EFFECT) != THE_DEPENDENCY


def test_the_page_has_exactly_one_effect_reading_the_history() -> None:
    """Non-vacuity, and the assumption the reader above rests on: one fetch, one array."""
    assert the_effect_that_fetches(page())
    assert page().count(THE_FETCH) == 1

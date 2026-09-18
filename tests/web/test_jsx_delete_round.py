"""The loop that forgets runs: one at a time, each refusal its own, each count on the right side.

Split from `test_jsx_forget_report.py`, which holds what the page *tells a
reader*. This is the round that produces those numbers, and three things about
it are wrong in ways the tokens cannot show.

**Sequential, not `Promise.all`.** That combinator rejects on the first
rejection and hands back one reason; the four other answers are discarded. After
asking for five, "one of them said 409" is not what a reader needs to know --
how many went is.

**A refusal does not stop the rest.** Each run is its own decision on the
server: one that is no longer failed -- a row a second browser tab already
forgot, or a status that moved under the page -- must not cancel the four that
still are. The `try`/`catch` is inside the loop for that reason.

**And each count sits on the side of the `await` that knows what happened.**
`gone += 1` written *before* the call counts every run as forgotten, including
the ones the server refused, so the page reports "5 of 5 forgotten" over a round
where two were not.

**The round also clears what the last one said, before it starts.** Without
`setSaid(null)` a second round renders the previous round's "3 of 5 forgotten"
for as long as the new one is in flight -- a stale count read as this round's,
which is the failure mode this whole page is written against. It went unpinned
for a sharp reason worth recording: `test_jsx_forget_report.py` narrowed its
`setSaid(` check to the whole *report* expression precisely **because**
`setSaid(null)` satisfied the loose one -- and then nothing was left holding the
clear. The narrowing took the premise's only assertion with it. That file pins
`setError(null)` and counts the error setters; this is the `said` half, here
because `forget`'s internals are this file's subject.

**All three were token checks first, and all three were measured passing over
the defect they name.** A loop wrapped in one `try` puts the loop before the
catch before the push, satisfying every ordering this file could state. `gone +=
1` is present on whichever side of the await it sits. So each claim is one regex
over the round, with the real alternative written out as a plant rather than
described.

No test in this suite renders React -- recorded, and not closed here -- so this
is the source read as text: it shows the loop is *written* that way, and cannot
show what five clicks do.

Reads one page as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

PAGE = FRONTEND_SRC / "pages" / "HistoryPage.jsx"

# The one primitive, and the loop that applies it once per run.
THE_CALL = "await forgetRun(run.run_id)"
THE_LOOP = "for (const run of runs)"

# Where the failure is caught: the loop's body has to *open* with the `try`.
# Matched as one expression rather than as two positions, because a `try` around
# the whole loop satisfies every ordering this file could state while turning
# one refusal into four runs nobody attempted.
THE_CAUGHT_LOOP = re.compile(r"for \(const run of runs\) \{\s*try \{")

# The defect that regex exists to refuse, written out so the plant is the real
# alternative and not a strawman.
A_LOOP_WRAPPED_IN_ONE_CATCH = (
    "    try {\n"
    "      for (const run of runs) {\n"
    "        await forgetRun(run.run_id);\n"
    "        gone += 1;\n"
    "      }\n"
    "    } catch (failure) {\n"
    "      refused.push(failure.message);\n"
    "    }\n")

# The whole round as one expression: the loop, the call, the count **after** the
# call, and the catch that collects the refusal.
THE_COUNTED_ROUND = re.compile(
    r"for \(const run of runs\) \{\s*try \{\s*await forgetRun\(run\.run_id\);\s*"
    r"gone \+= 1;\s*\} catch \(failure\) \{\s*refused\.push\(failure\.message\);")

# The two miscounts it refuses, in full.
A_ROUND_COUNTING_BEFORE_THE_CALL = (
    "    for (const run of runs) {\n      try {\n        gone += 1;\n"
    "        await forgetRun(run.run_id);\n      } catch (failure) {\n"
    "        refused.push(failure.message);\n      }\n    }\n")
A_ROUND_COLLECTING_NOTHING = (
    "    for (const run of runs) {\n      try {\n"
    "        await forgetRun(run.run_id);\n        gone += 1;\n"
    "      } catch (failure) {\n      }\n    }\n")

# What must not be used, and why it has a name here: it is the obvious way to
# write this, and it discards every answer but one.
THE_COMBINATOR = "Promise.all"

# What the round clears before it starts, as the opening of the function: both
# states, and *first*, so a second round cannot render the first one's report.
# Matched from the signature so "before it starts" is part of the claim.
THE_CLEARED_START = re.compile(
    r"async function forget\(runs\) \{\s*setError\(null\);\s*setSaid\(null\);")

# A round that leaves the last one's report on screen, as its plant.
A_ROUND_THAT_CLEARS_NOTHING = (
    "  async function forget(runs) {\n    const refused = [];\n    let gone = 0;\n")

# A floor, so a file this test failed to read cannot satisfy the absence above.
MINIMUM_ELEMENTS = 5


def page() -> str:
    """The history page's own source, comments stripped: its comments name `Promise.all` in prose."""
    return strip_comments(PAGE.read_text(encoding="utf-8"))


def test_the_deletes_run_one_at_a_time() -> None:
    """One primitive per run: the server decides one run, and the page decides how many."""
    assert THE_LOOP in page()
    assert THE_CALL in page()


def test_the_page_does_not_wait_on_them_all_at_once() -> None:
    """`Promise.all` rejects on the first rejection and discards the other four answers."""
    assert THE_COMBINATOR not in page()


def test_a_refusal_is_caught_inside_the_loop() -> None:
    """A `catch` outside it turns one refusal into four runs nobody attempted."""
    assert THE_CAUGHT_LOOP.search(page())


def test_a_loop_wrapped_in_one_catch_is_not_accepted() -> None:
    """Planted: source order alone passes on exactly that page, which was measured."""
    assert THE_CAUGHT_LOOP.search(A_LOOP_WRAPPED_IN_ONE_CATCH) is None


def test_the_combinator_would_be_reported_if_it_were_used() -> None:
    """Planted: the absence above holds of any file this test failed to read."""
    assert THE_COMBINATOR in "await Promise.all(runs.map(forgetRun));"


# --- it clears the last round's report before it starts -----------------------

def test_the_round_clears_what_the_last_one_said() -> None:
    """Otherwise a second round shows the first one's count while the new one is in flight."""
    assert THE_CLEARED_START.search(page())


def test_a_round_that_clears_nothing_is_not_accepted() -> None:
    """Planted: the narrowing in `test_jsx_forget_report.py` took this premise's only check with it."""
    assert THE_CLEARED_START.search(A_ROUND_THAT_CLEARS_NOTHING) is None


# --- and each count lands on the side of the await that knows -----------------

def test_both_outcomes_are_counted_where_the_outcome_is_known() -> None:
    """Two counts, and each on the side of the await that knows which one happened."""
    assert THE_COUNTED_ROUND.search(page())


def test_a_round_that_counts_before_it_calls_is_not_accepted() -> None:
    """Planted: `gone += 1` is present either way, and this page reports every run as forgotten."""
    assert THE_COUNTED_ROUND.search(A_ROUND_COUNTING_BEFORE_THE_CALL) is None


def test_a_round_that_collects_no_refusal_is_not_accepted() -> None:
    """Planted: the other half, where the refusals are swallowed and the report says nothing."""
    assert THE_COUNTED_ROUND.search(A_ROUND_COLLECTING_NOTHING) is None


def test_the_sweep_read_a_page_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable page satisfies the one absence check above."""
    assert len(re.findall(r"<[A-Za-z]", page())) >= MINIMUM_ELEMENTS

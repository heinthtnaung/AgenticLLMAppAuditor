"""Forgetting five runs and being refused two is neither a success nor a failure.

`HistoryPage.jsx` forgets a group's failed runs one at a time, because the server
has one primitive: `DELETE /api/runs/{id}`, one run, one decision. What a page
built on that owes a reader is a *count*, and three things have to hold for the
count to mean anything.

**The round that produces the numbers is `test_jsx_delete_round.py`.** This
file is what the page then *says* about them.

**The number is reported with its denominator, and the refusals with their
reasons.** "3 of 5 forgotten, 2
refused" rather than "done": this project's rule that no rate is ever a field in
`evaluation.json` is the same instinct one page deep, and a bare "done" over a
partial result is the gap-shown-as-success that the whole tool is against.

**Two of this file's checks were satisfied by something other than the claim**,
each recorded beside its constant: `setSaid(` by the `setSaid(null)` that opens
the function, and `said.refused.length` by the notice's own class expression --
so the file passed on a page reporting the successes and never the refusals,
while the paragraph above promised the opposite in as many words. A docstring
ahead of its assertion is the fault that keeps recurring here, and reading each
paragraph against the assertion holding it is what found the second.

**What is kept apart from what**: `said` is not `error`. A run where two were
refused is a *result*, and `HistoryPage.jsx` early-returns the error notice **in
place of the whole card** -- asserted below, because it is what makes the guard
necessary rather than decorative -- so a delete path reaching `setError` would
replace the list with a failure message and lose the three runs that did go.

That was "both setters are mentioned somewhere" until 2026-09-18, and could not
have held: `forget` opens with `setError(null)`. The **catch's own span** is read
now, from the catch that collects a refusal to the re-read after the loop, and
the setter must be absent from it.

**How the list is re-read afterwards is `test_jsx_history_refresh.py`**; that a
click reaches any of this is `test_jsx_history_wiring.py`. Both split out when
the subjects together passed the ~200-line rule.

No test in this suite renders React -- recorded, and not closed here -- so this
is the source read as text: it shows the page is *written* that way, and cannot
show what five clicks do.

Reads one page as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

PAGE = FRONTEND_SRC / "pages" / "HistoryPage.jsx"

# The two numbers the headline is built from. `asked` is the denominator, and is
# what makes "3 forgotten" mean something.
#
# `said.refused.length` is deliberately **not** here: it appears in the notice's
# own `notice--${said.refused.length ? ...}` class expression, so a check for
# the accessor is answered for free by the colour of the box and says nothing
# about the refusals being reported. That was measured -- collapsing the
# `<strong>` to `{said.gone} of {said.asked} forgotten.` and dropping the detail
# line left a red notice saying "3 of 5 forgotten." and never mentioning that
# two were refused or why, with this file green and its own docstring promising
# the opposite in as many words. The clause and the detail are named below
# instead.
THE_FIGURES = ("said.gone", "said.asked")

# The message itself, as the page writes it.
THE_REPORT = "{said.gone} of {said.asked} forgotten"

# The refusals, in the two places they have to reach a reader: the count, in the
# headline beside the successes, and the reasons under it.
THE_REFUSED_CLAUSE = "{said.refused.length > 0 && `, ${said.refused.length} refused`}"
THE_REFUSED_DETAIL = '<span className="notice__detail">{said.refused.join("; ")}</span>'

# What the page was reduced to when only the figures were checked.
A_HEADLINE_WITH_NO_REFUSALS = (
    "          <strong>{said.gone} of {said.asked} forgotten.</strong>\n")

# The two states kept apart: what the last delete did, and what went wrong with
# the page. A result is not an error, and the page renders the error *instead
# of* the card.
# The report itself, not the setter: `forget` opens with `setSaid(null)`, so a
# check for `setSaid(` is satisfied by the *clearing* and says nothing about a
# result ever being written.
THE_RESULT_STATE = "setSaid({ asked: runs.length, gone, refused })"
THE_ERROR_STATE = "setError("

# The premise the check above rests on, asserted rather than assumed: the page
# **early-returns** the error notice, so setting an error replaces the whole
# card. Both ends, the way `test_css_viewer_frame.py` asserts both ends of its
# one rule -- if the error notice ever renders *beside* the card instead, the
# guard below becomes harmless rather than necessary, and a reader of either
# file alone could not tell.
THE_ERROR_REPLACES_THE_CARD = re.compile(r"if \(error\) \{\s*return \(")

# The same notice rendered alongside, as the plant: on that page a refusal would
# be noise beside the list rather than the list's replacement.
AN_ERROR_RENDERED_BESIDE_THE_CARD = (
    "  return (\n    <div className=\"card\">\n"
    "      {error && <p className=\"notice notice--error\">{error}</p>}\n")

# The delete path's own span: the catch that collects a refusal, through the end
# of the loop, up to the re-read. Nothing in here may raise the page's error
# state. Bounded on the re-read rather than on the catch's closing brace,
# because a `{}` written inside the body would end that bound early and put a
# later `setError` outside the span this is meant to search.
THE_DELETE_PATH = re.compile(r"\} catch \(failure\) \{.*?setRead\(", re.DOTALL)

# The collapse it refuses: a catch that reports the refusal as a page error, and
# so replaces the list with a notice about one run out of five.
A_CATCH_THAT_COLLAPSES_INTO_THE_ERROR = (
    "      } catch (failure) {\n"
    "        refused.push(failure.message);\n"
    "        setError(failure.message);\n"
    "      }\n    }\n    setRead((was) => was + 1);\n")

# What the page legitimately sets an error for. Four occurrences, in two pairs:
# `forget` and `clear` each clear it as their round begins, the history fetch
# raises when the list could not be read at all, and `clear` raises on its own
# failure.
#
# **`clear` may do what `forget` may not**, and the difference is not a
# relaxation. `forget` deletes run by run, so a refusal is one outcome among
# several and belongs in the `said` report beside the count that went -- an
# error there would throw away four successes to show one refusal. `clear` is a
# single statement on the server with no partial outcome, so its failure really
# is the whole story. The collapse this file exists to refuse is still refused:
# it is asserted over `forget`'s own catch span, not over this count.
EXPECTED_ERROR_SETTERS = 4
THE_ERROR_CLEARED = "setError(null)"

# A floor, so a file this test failed to read cannot satisfy the absence above.
MINIMUM_ELEMENTS = 5


def page() -> str:
    """The history page's own source, comments stripped: its comments name `Promise.all` in prose."""
    return strip_comments(PAGE.read_text(encoding="utf-8"))


def the_delete_path(text: str) -> str:
    """From the catch that collects a refusal to the re-read after the loop."""
    found = THE_DELETE_PATH.search(text)
    assert found, "the delete loop no longer catches a refusal and then re-reads"
    return found.group(0)


# --- the number is reported with its denominator, and the refusals with reasons -

def test_the_message_carries_the_denominator() -> None:
    """"3 forgotten" says nothing; "3 of 5" says what a reader asked for and what happened."""
    assert THE_REPORT in page()


def test_every_figure_the_headline_needs_is_rendered() -> None:
    """Named one by one, so a dropped figure is reported as itself."""
    missing = [figure for figure in THE_FIGURES if figure not in page()]
    assert missing == []


def test_the_refusals_are_counted_in_the_headline() -> None:
    """"3 of 5 forgotten." in a red box never says two were refused. This is that clause."""
    assert THE_REFUSED_CLAUSE in page()


def test_the_reasons_for_the_refusals_are_shown_under_it() -> None:
    """A count with no reason leaves a reader nothing to act on: the server said why."""
    assert THE_REFUSED_DETAIL in page()


def test_a_headline_that_reports_only_the_successes_is_not_accepted() -> None:
    """Planted: `said.refused.length` is answered by the notice's own class expression."""
    assert THE_REFUSED_CLAUSE not in A_HEADLINE_WITH_NO_REFUSALS
    assert THE_REFUSED_DETAIL not in A_HEADLINE_WITH_NO_REFUSALS


# --- a partial result is not the page's error branch ---------------------------

def test_a_delete_reports_its_outcome_as_a_result() -> None:
    """The report, not the setter: `forget` opens by clearing `said`, which is not a result."""
    assert THE_RESULT_STATE in page()


def test_the_pages_error_notice_replaces_the_card_rather_than_joining_it() -> None:
    """The premise: this is why a refusal reaching `setError` loses the runs that did go."""
    assert THE_ERROR_REPLACES_THE_CARD.search(page())


def test_an_error_rendered_beside_the_card_is_not_that_premise() -> None:
    """Planted: on such a page the guard below is harmless, and that should be visible."""
    assert THE_ERROR_REPLACES_THE_CARD.search(AN_ERROR_RENDERED_BESIDE_THE_CARD) is None


def test_the_delete_path_never_raises_the_pages_error_state() -> None:
    """The error notice replaces the whole card, so one refusal would hide the runs that went."""
    assert THE_ERROR_STATE not in the_delete_path(page())


def test_a_catch_that_reports_a_refusal_as_a_page_error_is_not_accepted() -> None:
    """Planted: `forget` opens with `setError(null)`, so "both are mentioned" was true regardless."""
    assert THE_ERROR_STATE in the_delete_path(A_CATCH_THAT_COLLAPSES_INTO_THE_ERROR)


def test_the_page_sets_an_error_only_where_an_error_is_the_whole_story() -> None:
    """Four times: each round clears it, the list read raises, and the whole-history wipe does."""
    assert page().count(THE_ERROR_STATE) == EXPECTED_ERROR_SETTERS
    assert THE_ERROR_CLEARED in page()


def test_the_sweep_read_a_page_and_not_an_empty_file() -> None:
    """Non-vacuity: an unreadable page satisfies the one absence check above."""
    assert len(re.findall(r"<[A-Za-z]", page())) >= MINIMUM_ELEMENTS

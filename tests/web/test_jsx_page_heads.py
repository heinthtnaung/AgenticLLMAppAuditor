"""The history page carries no head, and the two figures that were beside its prose stayed.

`App.jsx` holds `HEADS`, a title and a sentence per page, and renders one when
the route has an entry. The history page's entry was removed on 2026-09-18 at
the user's request, along with the sentence that stood under it. Two things have
to be true for that to be a removal rather than a break:

**The lookup has to be by route, and it has to be guarded.** `HEADS[route.page]`
is `undefined` for a page with no entry, and `<PageHead title={undefined}>`
renders a heading with no text -- an empty band above the card rather than
nothing at all. The render reads `head && ...`, and that guard is now
load-bearing for a page that really exists, where before it was only ever true.

**One entry in the table is necessary and not sufficient**, which was measured:
replacing the lookup with `HEADS.audit` gives every page the audit head, so the
history page regains the very head the user asked to have removed -- with
`head_keys() == {"audit"}` still true and the suite green. The premise the table
check rests on is that the table is consulted *by route*, and it is asserted
below.

**And the figures are not prose.** What went was the sentence "A finished run
keeps its findings even after its files are cleaned from disk"; what stayed is
`{stored} runs stored, showing the newest {shown}` -- checked with the words
beside the numbers, because both accessors also appear in the `capped`
comparison and a bare-name check would pass on a page that computed the pair and
rendered neither. Those are not decoration:
the list is capped at `HISTORY_LIST_LIMIT` and a reader comparing the two
numbers is the only way they learn the history is longer than the page shows.
Dropping them with the sentence would let the page silently omit rows, and each
group header then says "N shown" against nothing that explains it.

The card is titled "History" -- renamed from "Past runs" in the same change --
so the page is still named somewhere a reader can see, which is what makes
dropping the head a removal of duplication rather than of the title.

**What this file cannot see**: whether the head renders where a reader expects
it, or at all. No test in this suite renders React, which is recorded and not
closed here. The parse is a regex over an object literal, the same shape
`test_option_fields.py` uses to read `INITIAL`.

Reads two components as text. No fastapi, no node, no build.
"""

import re

from .jsx_sweep import FRONTEND_SRC, strip_comments

APP = FRONTEND_SRC / "App.jsx"
HISTORY_PAGE = FRONTEND_SRC / "pages" / "HistoryPage.jsx"

# The head table, and one page's key inside it.
HEADS_OBJECT = re.compile(r"const HEADS = \{(.*?)\n\};", re.DOTALL)
HEAD_KEY = re.compile(r"^  ([A-Za-z_]\w*):", re.MULTILINE)

# The one page that still has a head. The run page renders its own, because its
# head carries a button needing a record `App.jsx` has not fetched.
THE_ONLY_HEAD = "audit"

# The page whose head was removed, spelled as `router.js` spells it.
THE_HEADLESS_PAGE = "history"

# How the table is consulted, and the guard that keeps a page with no entry from
# rendering an empty heading. The lookup is named because a constant subscript
# -- `HEADS.audit` -- hands the audit head to every page while leaving the table
# one entry long.
THE_LOOKUP = "const head = HEADS[route.page];"
THE_GUARD = "head && <PageHead"

# The constant subscript, as its plant.
A_LOOKUP_THAT_IGNORES_THE_ROUTE = "  const head = HEADS.audit;\n"

# What the card is called now, and what it was called before.
THE_TITLE = "History"
THE_OLD_TITLE = "Past runs"

# The two figures the prose was cut around, **as the page renders them**.
# `stored_run_count` is the store's own total and `held.runs.length` is what this
# page was handed. Written with the words beside them rather than as bare
# accessors: both names also appear in `THE_CAP_TEST` below, so a check for the
# accessor alone is satisfied by the comparison and says nothing about either
# number reaching a reader.
THE_STORED_FIGURE = "{held.stored_run_count} run"
THE_SHOWN_FIGURE = "showing the newest ${held.runs.length}"
THE_CAP_TEST = "held.stored_run_count > held.runs.length"

# The sentence that went, in both places it was written. Matched on a fragment
# rather than the whole thing, so re-wrapping it would not hide it.
THE_REMOVED_SENTENCE = "keeps its findings"

# A floor, so a file this test failed to read cannot satisfy the absences above.
MINIMUM_ELEMENTS = 8


def app() -> str:
    """The shell's own source, comments stripped: its comment explains the removal in prose."""
    return strip_comments(APP.read_text(encoding="utf-8"))


def history_page() -> str:
    """The history page's own source, comments stripped."""
    return strip_comments(HISTORY_PAGE.read_text(encoding="utf-8"))


def head_keys() -> set[str]:
    """Every page `HEADS` has an entry for."""
    found = HEADS_OBJECT.search(app())
    assert found, f"{APP.name} no longer declares `const HEADS = {{...}};`"
    return set(HEAD_KEY.findall(found.group(1)))


# --- one head, and a guard for the pages without one ---------------------------

def test_the_head_table_has_exactly_one_entry() -> None:
    """One page, not two: the history page's entry went and no third appeared."""
    assert head_keys() == {THE_ONLY_HEAD}


def test_the_history_page_has_no_head_entry() -> None:
    """Named on its own, so the failure reads as what it is rather than as a set diff."""
    assert THE_HEADLESS_PAGE not in head_keys()


def test_the_head_is_looked_up_by_the_route_that_is_showing() -> None:
    """Measured MISSED: `HEADS.audit` gives the history page back the head it lost."""
    assert THE_LOOKUP in app()


def test_a_lookup_that_ignores_the_route_is_not_accepted() -> None:
    """Planted: the table is still one entry long, so its own check cannot see this."""
    assert THE_LOOKUP not in A_LOOKUP_THAT_IGNORES_THE_ROUTE


def test_the_render_guards_a_page_with_no_entry() -> None:
    """`HEADS[route.page]` is `undefined`, and an unguarded `<PageHead>` is an empty band."""
    assert THE_GUARD in app()


def test_the_head_table_was_found_and_read() -> None:
    """Non-vacuity: an unreadable object would be an empty set, and satisfy the absence above."""
    assert len(head_keys()) >= 1
    assert len(re.findall(r"<[A-Za-z]", app())) >= MINIMUM_ELEMENTS


# --- and the page names itself on its own card ---------------------------------

def test_the_card_is_titled_history() -> None:
    """Dropping the head is removing a duplicate title, not removing the title."""
    assert f'card__title">{THE_TITLE}<' in history_page()


def test_the_old_title_is_gone() -> None:
    """Renamed rather than kept in a second place: two names for one page is one too many."""
    assert THE_OLD_TITLE not in history_page()
    assert THE_OLD_TITLE not in app()


# --- the figures stayed, and the sentence did not ------------------------------

def test_both_figures_are_still_rendered() -> None:
    """Rendered, not merely computed: the cap is what a list silently omitting rows hides behind."""
    assert THE_STORED_FIGURE in history_page()
    assert THE_SHOWN_FIGURE in history_page()


def test_a_figure_that_is_only_compared_is_not_counted_as_rendered() -> None:
    """Planted: both accessors appear in the cap test, so the bare names prove nothing."""
    only_compared = "  const capped = held.stored_run_count > held.runs.length;\n"
    assert THE_STORED_FIGURE not in only_compared
    assert THE_SHOWN_FIGURE not in only_compared


def test_the_page_still_compares_the_two_figures() -> None:
    """A number shown beside another is not a comparison; this is where "showing the newest" comes from."""
    assert THE_CAP_TEST in history_page()


def test_the_sentence_that_was_removed_is_in_neither_file() -> None:
    """Removed once, not moved: the same prose surviving in the card would be the same duplication."""
    assert THE_REMOVED_SENTENCE not in history_page()
    assert THE_REMOVED_SENTENCE not in app()


def test_the_removed_sentence_would_be_found_if_it_were_there() -> None:
    """Planted: the two absences above hold of any string this file failed to read."""
    assert THE_REMOVED_SENTENCE in "A finished run keeps its findings after a clean."

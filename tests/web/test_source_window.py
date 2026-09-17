"""Which lines `GET /api/runs/{id}/source` hands back, and what it says about them.

The page shows a surface's own line so a reader does not have to open the
repository to see what was found. This file is the arithmetic and the labelling;
`test_source_refusals.py` is every path that must not read a file at all.

**Three windows, because the arithmetic has three cases.** A line in the middle
of a file gets `CONTEXT_LINES` either side; a line near the top cannot, and the
window is clipped at line 1 rather than starting at zero or at a negative
offset; a line near the bottom is clipped at the last line. Each is asserted as
a literal list of the file's own lines, so a window that came back one short or
one shifted is visible rather than plausible -- an off-by-one here shows the
reader a *different line* under the number the finding named, which is worse
than showing nothing.

**`first_line` is the contract with the page.** The lines arrive as a bare list,
so the number of the first one is the only thing that lets the page label the
rest. It is asserted beside every window for that reason.

**`unchecked` is never silent, and that is the point of the field.** `fetch_repo`
deletes `.git` once it has pinned the commit, so `check_tree_matches_pin` has
nothing to diff against and can only report that it cannot check -- every tree
this tool produces is in that state. If anything edited the tree after the
audit, what comes back is *today's* line. The reply says so rather than letting
the page present it as audited evidence, which is the fact-shaped guess this
project refuses everywhere else.

Nothing here clones, calls a model or opens a socket: the tree is written into
`tmp_path` by `source_fixtures`, and the download root is redirected there
before the route reads it.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import source_routes                                          # noqa: E402

from .source_fixtures import (                                 # noqa: E402
    COMMIT, LINE_COUNT, NESTED_FILE, NESTED_TEXT, SOURCE_FILE, SOURCE_LINES,
    a_client_and_its_tree, source_window)

# The line a finding might name, and what a window around it contains. Written
# as literals rather than derived from `CONTEXT_LINES`, so a change to that
# constant is a test to re-read and not a test that quietly follows.
MIDDLE_LINE = 10
MIDDLE_FIRST = 4
MIDDLE_LAST = 16

# The first line of the file: nothing above it, so the window opens at 1.
FIRST_LINE = 1
FIRST_WINDOW_LAST = 7

# The last line of the file: nothing below it, so the window closes at the end.
LAST_WINDOW_FIRST = LINE_COUNT - source_routes.CONTEXT_LINES

# What the reply carries. Named as a set so a key added without a reader, or one
# removed from under the page, is a failure here.
REPLY_FIELDS = {"file", "line", "first_line", "lines", "unchecked"}

# What `check_tree_matches_pin` can only ever say about a tool-fetched tree.
CANNOT_BE_CHECKED = "carries no history"


def lines_from(first: int, last: int) -> list[str]:
    """The file's own lines from one number to another, counting from one."""
    return SOURCE_LINES[first - 1:last]


# --- the window, in its three cases -------------------------------------------

def test_a_line_in_the_middle_gets_context_on_both_sides(monkeypatch, tmp_path) -> None:
    """The ordinary case: six lines either side, so the line sits in what it belongs to."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    window = source_window(client, SOURCE_FILE, MIDDLE_LINE)
    assert window["lines"] == lines_from(MIDDLE_FIRST, MIDDLE_LAST)
    assert window["first_line"] == MIDDLE_FIRST


def test_the_window_is_clipped_at_the_top_of_the_file(monkeypatch, tmp_path) -> None:
    """Line 1 has nothing above it: the window opens at 1, never at 1 minus six."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    window = source_window(client, SOURCE_FILE, FIRST_LINE)
    assert window["first_line"] == FIRST_LINE
    assert window["lines"] == lines_from(FIRST_LINE, FIRST_WINDOW_LAST)


def test_the_window_is_clipped_at_the_end_of_the_file(monkeypatch, tmp_path) -> None:
    """And the other end: a short tail must not pad, repeat or run off the list."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    window = source_window(client, SOURCE_FILE, LINE_COUNT)
    assert window["first_line"] == LAST_WINDOW_FIRST
    assert window["lines"] == lines_from(LAST_WINDOW_FIRST, LINE_COUNT)


def test_the_named_line_is_the_one_in_the_middle_of_what_came_back(
        monkeypatch, tmp_path) -> None:
    """The join the page makes: `line` minus `first_line` indexes into `lines`."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    window = source_window(client, SOURCE_FILE, MIDDLE_LINE)
    assert window["lines"][window["line"] - window["first_line"]] == \
        SOURCE_LINES[MIDDLE_LINE - 1]


def test_a_window_is_no_wider_than_the_context_the_module_declares(
        monkeypatch, tmp_path) -> None:
    """A quotation, not a file viewer: the cap is `CONTEXT_LINES` either side of one line."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    window = source_window(client, SOURCE_FILE, MIDDLE_LINE)
    assert len(window["lines"]) == 2 * source_routes.CONTEXT_LINES + 1


# --- which file, and what the reply says about it -----------------------------

def test_a_file_in_a_subdirectory_is_read_too(monkeypatch, tmp_path) -> None:
    """Surfaces are not all in the root, and a path with a separator is the common one."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    window = source_window(client, NESTED_FILE, FIRST_LINE)
    assert window["lines"] == NESTED_TEXT.splitlines()[:FIRST_LINE + source_routes.CONTEXT_LINES]
    assert window["file"] == NESTED_FILE


def test_the_reply_echoes_the_file_and_line_that_were_asked_for(monkeypatch,
                                                                tmp_path) -> None:
    """The page renders several of these at once, so a window has to say which it is."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    window = source_window(client, SOURCE_FILE, MIDDLE_LINE)
    assert (window["file"], window["line"]) == (SOURCE_FILE, MIDDLE_LINE)


def test_the_reply_carries_exactly_the_fields_the_page_reads(monkeypatch,
                                                             tmp_path) -> None:
    """Exact, not a superset: a field with no reader is one nobody maintains."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    assert set(source_window(client, SOURCE_FILE, MIDDLE_LINE)) == REPLY_FIELDS


# --- and it never claims the line was the audited one -------------------------

def test_the_reply_says_the_tree_could_not_be_checked_against_its_pin(
        monkeypatch, tmp_path) -> None:
    """Always, for a tool-fetched tree: the fetch deleted the history that would answer."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    assert CANNOT_BE_CHECKED in source_window(client, SOURCE_FILE, MIDDLE_LINE)["unchecked"]


def test_the_note_names_the_commit_the_tree_is_pinned_to(monkeypatch, tmp_path) -> None:
    """Non-vacuity: a constant string would satisfy the check above and say nothing."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    assert COMMIT[:12] in source_window(client, SOURCE_FILE, MIDDLE_LINE)["unchecked"]


def test_an_edited_tree_answers_with_what_is_on_disk_now(monkeypatch, tmp_path) -> None:
    """The honest half of `unchecked`: the endpoint reads now, and cannot know otherwise.

    Asserted rather than left implicit because the alternative reading -- that
    the window is evidence of what was audited -- is the one a page would
    naturally present, and it is false. The tool did not write this edit and
    never would; a person with the disk did.
    """
    client, tree = a_client_and_its_tree(monkeypatch, tmp_path)
    edited = "# edited after the audit, by someone who is not this tool\n"
    (tree / SOURCE_FILE).write_text(edited + "\n".join(SOURCE_LINES) + "\n",
                                    encoding="utf-8")
    window = source_window(client, SOURCE_FILE, FIRST_LINE)
    assert window["lines"][0] == edited.rstrip("\n")

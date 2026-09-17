"""Every reason the tree could not be checked reaches `unchecked`, and none of them is a 500.

`GET /api/runs/{id}/source` shows the line a surface names, and `unchecked` is
the field that says whether the tree it was read from is still the tree that was
audited. `check_tree_matches_pin` *raises* for three of the four answers it can
give -- a pin that cannot be read, a drifted commit, a dirty tree -- and the
route caught none of them. Measured before the fix, against a staged tree:

    a pin holding `{` -> 500
    a pin holding `[]` -> 500   (`AttributeError`, not even a `ValueError`)

So the states this endpoint exists to warn about arrived as a crash, while the
field written to carry them sat empty. Each is now the sentence `fetch_repo`
wrote, handed back with a 200 and a real window beside it -- a tree that cannot
be checked is not a tree that cannot be read, so the reply is the same shape
either way and the note is the only difference. Asserted beside the first
refusal, so "answered 200" is not satisfied by an empty body.

**No git here, and no repository this project does not own.** `source_fixtures`
writes the tree into `tmp_path` and redirects the download root there; the tests
that need a tree with history plant a `.git` directory and answer
`fetch_repo._run` from memory, as `tests/fetch_helpers.py` does for the fetcher.
The real `check_tree_matches_pin` -- the comparison and both of its sentences --
is still the code under test, on a machine with no git installed.

Which lines come back is `test_source_window.py`; every path that must not read
a file at all is `test_source_refusals.py`.
"""

from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient                     # noqa: E402

import fetch_repo                                             # noqa: E402
from keys.grading_keys import MANIFEST_SUFFIX                 # noqa: E402

from .corrupt_fixtures import CORRUPT_SHAPES                  # noqa: E402
from .source_fixtures import (                                # noqa: E402
    APP, COMMIT, COMMIT_DATE, OK, SOURCE_FILE, SOURCE_LINES, ask_for_source,
    client_over, source_window, stage_tree)

# The line asked for when the subject is the note rather than the arithmetic.
A_LINE = 10

# A commit the tree is at that is not the one the pin names. Full length,
# because the refusal quotes the first twelve characters of both.
DRIFTED_HEAD = "9f9f9f9f" * 5

# One line of `git status --porcelain`, in its own format: a tracked file
# modified in the working tree. This is what a person editing an audited
# repository leaves behind.
A_DIRTY_LINE = f" M {SOURCE_FILE}"

# What survives into the note. `check_tree_matches_pin` strips the block it
# quotes, so porcelain's leading status column goes with the surrounding
# whitespace; the file name, which is the only actionable part, does not.
QUOTED_IN_THE_NOTE = A_DIRTY_LINE.strip()

# What each refusal says. The sentences are the point of the field: a reader who
# sees only "unchecked" learns nothing about which of the three happened.
DRIFT_SAID = "pins"
DIRTY_SAID = "is modified against its pinned commit"

# A tree at its pinned commit with nothing edited is checked, and says so by
# saying nothing. The one answer that is not a note.
CHECKED = ""

CORRUPT_IDS = [text for text, _message in CORRUPT_SHAPES]


class StubGit:
    """Answers the git commands `check_tree_matches_pin` runs, from memory rather than a process."""

    def __init__(self, head: str, dirty: str = "") -> None:
        """Hold the commit the tree is at, and whatever `git status` should report."""
        self.head = head
        self.dirty = dirty

    def __call__(self, arguments: list[str], cwd: Path | None = None) -> str:
        """Answer one command, refusing any the check is not supposed to run."""
        if arguments[0] == "rev-parse":
            return f"{self.head}\n"
        if arguments[0] == "log":
            return f"{COMMIT_DATE}\n"
        if arguments[0] == "status":
            return f"{self.dirty}\n"
        raise AssertionError(f"the pin check ran an unexpected git command: {arguments}")


def pin_beside(tmp_path: Path) -> Path:
    """The pin `stage_tree` wrote, which every test here replaces or leaves alone."""
    return fetch_repo.manifest_path(tmp_path / "fetched", APP)


def client_over_a_corrupt_pin(monkeypatch, tmp_path: Path, text: str) -> TestClient:
    """A staged tree whose pin a hand edit broke, and a client over the run that audited it."""
    stage_tree(tmp_path)
    pin_beside(tmp_path).write_text(text, encoding="utf-8")
    return client_over(monkeypatch, tmp_path)


def client_over_a_tree_with_history(monkeypatch, tmp_path: Path, head: str,
                                    dirty: str = "") -> TestClient:
    """The same staging, plus the `.git` a hand-cloned tree keeps and a git answered from memory."""
    tree = stage_tree(tmp_path)
    (tree / fetch_repo.HISTORY_DIR).mkdir()
    monkeypatch.setattr(fetch_repo, "_run", StubGit(head, dirty))
    return client_over(monkeypatch, tmp_path)


def note_from(client: TestClient) -> str:
    """The `unchecked` sentence one window came back with."""
    return source_window(client, SOURCE_FILE, A_LINE)["unchecked"]


# --- a pin a hand edit broke ----------------------------------------------------

@pytest.mark.parametrize("text,message", CORRUPT_SHAPES, ids=CORRUPT_IDS)
def test_a_corrupt_pin_is_reported_in_unchecked_rather_than_crashing(
        monkeypatch, tmp_path, text: str, message: str) -> None:
    """Both faults, through the route: the reason the tree is unchecked is the reason given."""
    client = client_over_a_corrupt_pin(monkeypatch, tmp_path, text)
    assert message in note_from(client)


@pytest.mark.parametrize("text,_message", CORRUPT_SHAPES, ids=CORRUPT_IDS)
def test_the_note_names_the_file_that_has_to_be_fixed(monkeypatch, tmp_path,
                                                      text: str, _message: str) -> None:
    """A reader on the page is the person who edits the pin, so the note names it."""
    client = client_over_a_corrupt_pin(monkeypatch, tmp_path, text)
    assert f"{APP}{MANIFEST_SUFFIX}" in note_from(client)


@pytest.mark.parametrize("text,_message", CORRUPT_SHAPES, ids=CORRUPT_IDS)
def test_a_corrupt_pin_is_answered_with_200(monkeypatch, tmp_path,
                                            text: str, _message: str) -> None:
    """The status the page can read: a 500 keeps only `detail` and loses the sentence."""
    client = client_over_a_corrupt_pin(monkeypatch, tmp_path, text)
    assert ask_for_source(client, SOURCE_FILE, A_LINE).status_code == OK


def test_a_corrupt_pin_still_comes_back_with_the_window_it_was_asked_for(
        monkeypatch, tmp_path) -> None:
    """Non-vacuity for the 200 above: an unreadable pin is not an unreadable file."""
    client = client_over_a_corrupt_pin(monkeypatch, tmp_path, CORRUPT_SHAPES[0][0])
    window = source_window(client, SOURCE_FILE, A_LINE)
    assert window["lines"][window["line"] - window["first_line"]] == SOURCE_LINES[A_LINE - 1]


# --- a tree that moved, and a tree somebody edited --------------------------------

def test_a_drifted_commit_reaches_the_page_as_a_note(monkeypatch, tmp_path) -> None:
    """The check's sharpest sentence, which a 500 threw away: this is not that commit."""
    client = client_over_a_tree_with_history(monkeypatch, tmp_path, DRIFTED_HEAD)
    assert DRIFT_SAID in note_from(client)


def test_the_drift_note_names_both_commits(monkeypatch, tmp_path) -> None:
    """Non-vacuity: the tree's own head and the pinned one, so a reader can tell which moved."""
    client = client_over_a_tree_with_history(monkeypatch, tmp_path, DRIFTED_HEAD)
    note = note_from(client)
    assert DRIFTED_HEAD[:12] in note
    assert COMMIT[:12] in note


def test_a_dirty_tree_reaches_the_page_as_a_note(monkeypatch, tmp_path) -> None:
    """Right commit, edited afterwards -- the state the whole `unchecked` field is about."""
    client = client_over_a_tree_with_history(monkeypatch, tmp_path, COMMIT, A_DIRTY_LINE)
    assert DIRTY_SAID in note_from(client)


def test_the_dirty_note_carries_the_line_git_reported(monkeypatch, tmp_path) -> None:
    """Non-vacuity: which file was edited is the only actionable part of that sentence."""
    client = client_over_a_tree_with_history(monkeypatch, tmp_path, COMMIT, A_DIRTY_LINE)
    assert QUOTED_IN_THE_NOTE in note_from(client)


def test_a_drifted_tree_is_answered_with_200_and_its_window(monkeypatch, tmp_path) -> None:
    """The same 200 as every other answer: the page shows the line and labels it."""
    client = client_over_a_tree_with_history(monkeypatch, tmp_path, DRIFTED_HEAD)
    window = source_window(client, SOURCE_FILE, A_LINE)
    assert window["lines"][window["line"] - window["first_line"]] == SOURCE_LINES[A_LINE - 1]


# --- and the one tree that really is what it claims to be -------------------------

def test_a_tree_at_its_pinned_commit_with_nothing_edited_says_nothing(
        monkeypatch, tmp_path) -> None:
    """The off position, and the only state in this file that is not a note.

    Without it every assertion above is satisfied by a route that reports a
    problem whatever the tree is. The no-history case -- what a tool-fetched
    tree always answers -- is `test_source_window.py`.
    """
    client = client_over_a_tree_with_history(monkeypatch, tmp_path, COMMIT)
    assert note_from(client) == CHECKED

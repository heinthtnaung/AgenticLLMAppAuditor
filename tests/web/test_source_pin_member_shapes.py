"""A pin whose `upstream_commit` is not a string, seen from the page.

`test_source_pin_notes.py` holds every reason a tree could not be checked
against its pin, for a pin that is broken as a *file*. This is the one that is
broken as a *member*: `{"upstream_commit": 12345}` parses, is a json object, and
passes the guard written for those -- then `check_tree_matches_pin` composes its
note around `wanted[:12]` and raises `TypeError: 'int' object is not
subscriptable`. `_pin_note` catches `ValueError`, which that is not, so the
window came back as a **500** and the field that exists to carry exactly this
kind of doubt stayed empty.

One shape short of the file being unreadable, and answered the same way: a note
beside a real window, with a 200, because a tree that cannot be checked is not a
tree that cannot be read.

The unit half -- the field, its other reader, and the caller that slices it --
is `tests/cli/test_fetch_repo_pin_fields.py`.

Nothing here clones, and nothing reads a repository this project does not own:
`source_fixtures` writes the tree into `tmp_path` and points the download root
there first.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient                     # noqa: E402

import fetch_repo                                             # noqa: E402

from .source_fixtures import (                                # noqa: E402
    APP, COMMIT, OK, SOURCE_FILE, SOURCE_LINES, ask_for_source, client_over,
    source_window, stage_tree)

# What a hand edit leaves where a commit belongs. Valid json, in a valid json
# object, which is why the guard on the document let every one of them past.
NOT_A_COMMIT = {"an int": 12345, "a list": ["c" * 40], "null": None}
SHAPE_IDS = list(NOT_A_COMMIT)
SHAPES = list(NOT_A_COMMIT.values())

# The line asked for when the subject is the note rather than the arithmetic.
A_LINE = 10

# What a tool-fetched tree can only ever say: the fetch deleted the history that
# would have answered.
CANNOT_BE_CHECKED = "carries no history"


def client_over_a_pin_naming(monkeypatch, tmp_path: Path, commit: object) -> TestClient:
    """A staged tree whose pin holds `commit`, and a client over the run that audited it."""
    stage_tree(tmp_path)
    path = fetch_repo.manifest_path(tmp_path / "fetched", APP)
    document = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**document, "upstream_commit": commit}),
                    encoding="utf-8")
    return client_over(monkeypatch, tmp_path)


# --- the note, rather than the 500 ----------------------------------------------

@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
def test_a_commit_that_is_not_a_string_is_answered_with_a_note(monkeypatch, tmp_path,
                                                               shape: object) -> None:
    """The field exists to carry doubt about the tree; a crash carries none of it."""
    client = client_over_a_pin_naming(monkeypatch, tmp_path, shape)
    assert CANNOT_BE_CHECKED in source_window(client, SOURCE_FILE, A_LINE)["unchecked"]


@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
def test_the_window_is_still_answered_with_200(monkeypatch, tmp_path,
                                               shape: object) -> None:
    """The status a page can read: a 500 keeps only `detail` and loses the note."""
    client = client_over_a_pin_naming(monkeypatch, tmp_path, shape)
    assert ask_for_source(client, SOURCE_FILE, A_LINE).status_code == OK


def test_the_lines_asked_for_still_come_back(monkeypatch, tmp_path) -> None:
    """Non-vacuity for the 200: an unusable pin is not an unreadable file."""
    client = client_over_a_pin_naming(monkeypatch, tmp_path, NOT_A_COMMIT["an int"])
    window = source_window(client, SOURCE_FILE, A_LINE)
    assert window["lines"][window["line"] - window["first_line"]] == SOURCE_LINES[A_LINE - 1]


# --- and a pin that really names one --------------------------------------------

def test_a_pin_naming_a_real_commit_quotes_it_in_the_note(monkeypatch, tmp_path) -> None:
    """The off position: the twelve characters the note is built from are really read."""
    client = client_over_a_pin_naming(monkeypatch, tmp_path, COMMIT)
    assert COMMIT[:12] in source_window(client, SOURCE_FILE, A_LINE)["unchecked"]

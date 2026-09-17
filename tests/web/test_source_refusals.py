"""Which runs have source to read at all, and how much of a file this route will read.

The path rule -- that a read may not leave the run's own tree -- is
`test_source_confinement.py`. This file is the rest of what
`GET /api/runs/{id}/source` refuses, and each refusal carries its own sentence
because the fixes differ:

- **A run that resolved no app** never got as far as naming a tree.
- **A run whose tree is gone** has the name and nothing behind it: a local-path
  audit, which the tool never recorded a location for, or a cleaned `fetched/`.
- **A file over `MAX_SOURCE_BYTES`, or not UTF-8 at all.** A repository holds
  images and archives; this shows source or says it cannot, rather than
  streaming whatever is there at a browser that asked for a line of code. The
  cap is checked from both sides, because `>` and `>=` differ by one byte.
- **A line the file does not have** is a 404 that *names the real length*. Not
  politeness: it is the one signal a reader gets that the tree on disk is no
  longer the tree that was audited, which the reply's `unchecked` field says
  cannot be ruled out.

A read that must succeed sits beside each refusal, because a route that refused
everything would satisfy every assertion here.

Nothing here clones, calls a model or opens a socket, and nothing reads a
repository this project does not own: `source_fixtures` writes the tree into
`tmp_path` and redirects the download root there first.
"""

from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import source_routes                                          # noqa: E402

from .source_fixtures import (                                 # noqa: E402
    APP, LINE_COUNT, NO_SOURCE, NO_SUCH_RUN, OK, REFUSED, SOURCE_FILE,
    a_client_and_its_tree, a_finished_run, ask_for_source, client_over,
    refusal_from, stage_tree)

# The line a well-formed request names, when the subject is not the line.
A_REAL_LINE = 5

# What a run with no app, and a run whose tree is gone, each answer with.
NO_APP_SAID = "this run resolved no app"
NO_TREE_SAID = "Only a repository fetched by URL is kept"

# A run id no row carries, and one that is not the shape `RUN_ID` matches --
# both are "no run has that id", because a malformed one names no row either.
UNKNOWN_RUN_ID = "f" * 32
MALFORMED_RUN_ID = "not-a-hex-run-id"
NO_SUCH_RUN_SAID = "no run has that id"

# A run id shaped like a path. It never reaches the endpoint at all: the router
# matches one path segment, so this is a 404 from Starlette with no sentence of
# ours. Checked anyway, because "refused somewhere" is the claim that matters
# and where it is refused is what the reader needs told.
RUN_ID_SHAPED_LIKE_A_PATH = "../../etc/passwd"

# A file that is not text. The first byte pair is invalid UTF-8, which is what
# `read_text` raises on.
NOT_TEXT_FILE = "logo.bin"
NOT_TEXT_BYTES = b"\xff\xfe\x00binary, not source\x00"
NOT_UTF8_SAID = "is not UTF-8 text"

# A file over the cap, by one byte.
OVERSIZED_FILE = "vendored.js"
OVER_CAP_SAID = "this shows source, not whatever a repository happens to contain"

# A line number the file does not have, and one below the first.
PAST_THE_END = LINE_COUNT + 1
LINE_ZERO = 0
NEGATIVE_LINE = -1



def a_client_over_a_tree_with(monkeypatch, tmp_path: Path, name: str,
                              content: bytes):
    """A client over the ordinary tree, with one extra file planted inside it."""
    client, tree = a_client_and_its_tree(monkeypatch, tmp_path)
    (tree / name).write_bytes(content)
    return client


# --- which runs have a tree to read -------------------------------------------

def test_a_run_that_resolved_no_app_has_no_tree_to_read(monkeypatch, tmp_path) -> None:
    """A run that failed before the fetch named a tree: refused with its own sentence."""
    stage_tree(tmp_path)
    client = client_over(monkeypatch, tmp_path, a_finished_run(app=None))
    assert NO_APP_SAID in refusal_from(
        ask_for_source(client, SOURCE_FILE, A_REAL_LINE), NO_SOURCE)


def test_a_run_whose_tree_is_gone_says_which_audits_are_kept(monkeypatch,
                                                             tmp_path) -> None:
    """A local-path audit, or a cleaned `fetched/`: the name is recorded, the tree is not there."""
    client = client_over(monkeypatch, tmp_path)
    detail = refusal_from(ask_for_source(client, SOURCE_FILE, A_REAL_LINE), NO_SOURCE)
    assert NO_TREE_SAID in detail
    assert APP in detail


@pytest.mark.parametrize("asked", [UNKNOWN_RUN_ID, MALFORMED_RUN_ID])
def test_a_run_id_no_row_carries_reads_nothing(monkeypatch, tmp_path, asked: str) -> None:
    """An id with no row behind it reads no file, whether it is well formed or not.

    Measured, so it is said plainly: `RUN_ID` is *not* what this holds. Removing
    the match leaves both cases answering the same way, because the store has no
    such row either. The regex is the second line -- it keeps a malformed id out
    of the query at all -- and nothing here isolates it.
    """
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    assert NO_SUCH_RUN_SAID in refusal_from(
        ask_for_source(client, SOURCE_FILE, A_REAL_LINE, run_id=asked), NO_SUCH_RUN)


def test_a_run_id_shaped_like_a_path_never_reaches_the_endpoint(monkeypatch,
                                                                tmp_path) -> None:
    """Refused by the router, one layer earlier: a path segment cannot hold a path.

    So the sentence is Starlette's and not this module's, which is why it is
    asserted as a status and an absence rather than as a message. `RUN_ID` is
    still the check that matters -- it is what stops an id that *does* match one
    segment from reaching the store -- and the test above is the one that holds
    it.
    """
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    response = ask_for_source(client, SOURCE_FILE, A_REAL_LINE,
                              run_id=RUN_ID_SHAPED_LIKE_A_PATH)
    assert response.status_code == NO_SUCH_RUN
    assert "lines" not in response.json()


# --- and what is read is bounded ----------------------------------------------

def test_a_file_that_is_not_utf8_text_is_refused(monkeypatch, tmp_path) -> None:
    """A repository holds images and archives; this endpoint shows source or says it cannot."""
    client = a_client_over_a_tree_with(monkeypatch, tmp_path, NOT_TEXT_FILE,
                                       NOT_TEXT_BYTES)
    assert NOT_UTF8_SAID in refusal_from(
        ask_for_source(client, NOT_TEXT_FILE, A_REAL_LINE), REFUSED)


def test_a_file_over_the_cap_is_refused_before_it_is_read(monkeypatch, tmp_path) -> None:
    """The size is taken from `stat`, so an oversized file is never read into memory at all."""
    oversized = b"x" * (source_routes.MAX_SOURCE_BYTES + 1)
    client = a_client_over_a_tree_with(monkeypatch, tmp_path, OVERSIZED_FILE, oversized)
    assert OVER_CAP_SAID in refusal_from(
        ask_for_source(client, OVERSIZED_FILE, A_REAL_LINE), REFUSED)


def test_a_file_at_the_cap_is_still_read(monkeypatch, tmp_path) -> None:
    """The boundary, from the other side: `>` and not `>=`, and the difference is one byte."""
    at_cap = b"y\n" * (source_routes.MAX_SOURCE_BYTES // 2)
    client = a_client_over_a_tree_with(monkeypatch, tmp_path, OVERSIZED_FILE, at_cap)
    assert ask_for_source(client, OVERSIZED_FILE, A_REAL_LINE).status_code == OK


# --- a line the file does not have --------------------------------------------

def test_a_line_past_the_end_is_refused_and_names_the_real_length(monkeypatch,
                                                                  tmp_path) -> None:
    """The one signal that the tree on disk is not the tree that was audited."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    detail = refusal_from(ask_for_source(client, SOURCE_FILE, PAST_THE_END), NO_SOURCE)
    assert f"has {LINE_COUNT} lines" in detail
    assert f"names line {PAST_THE_END}" in detail


@pytest.mark.parametrize("asked", [LINE_ZERO, NEGATIVE_LINE])
def test_a_line_below_the_first_is_refused_too(monkeypatch, tmp_path,
                                               asked: int) -> None:
    """Lines count from one: zero and below index backwards into the list if left alone."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    assert ask_for_source(client, SOURCE_FILE, asked).status_code == NO_SOURCE


def test_the_last_line_of_the_file_is_not_past_the_end(monkeypatch, tmp_path) -> None:
    """The boundary from the other side, so the check above is not off by one."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    assert ask_for_source(client, SOURCE_FILE, LINE_COUNT).status_code == OK

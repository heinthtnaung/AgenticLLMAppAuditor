"""The one rule that keeps a file read on an unauthenticated server confined.

`GET /api/runs/{id}/source` is a **file-read primitive**. Everything else the
wrapper serves is an artifact this tool wrote, handed back by an allow-list in
`downloads.py`; this route reads an arbitrary path out of an audited repository,
because an audited tree is an open set of paths and an allow-list cannot
describe one. What stands in place of that allow-list is two facts, and this
file is both of them:

- **The directory is server-side.** It is `fetch_repo.DOWNLOAD_ROOT / record.app`
  -- the run's own recorded app name, which the tool derived from the tree it
  resolved. Nothing a caller sends contributes to it, and two tests hold that
  from both directions: the tree read follows the record when the record moves,
  and a query parameter naming another app changes nothing.
- **The file is resolved before it is judged.** `(tree / file).resolve()` must
  have the resolved tree among its parents, so `../` climbing out, an absolute
  path and a symlink pointing outside are one rule rather than three string
  checks that each have a hole.

Every attempt here reaches for a file that **really exists** outside the tree,
and two tests assert that staging rather than trusting it: refusing a path to
something that was never there proves nothing at all.

What a run may read *from* -- a run with no app, a tree that is gone, a file too
large or not text, a line past the end -- is `test_source_refusals.py`. Split
because this half is the security claim and deserves to be read on its own.

Nothing here clones, calls a model or opens a socket, and nothing reads a
repository this project does not own: `source_fixtures` writes the tree into
`tmp_path` and redirects the download root there first.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from .source_fixtures import (                                 # noqa: E402
    OK, REFUSED, RUN_ID, SOURCE_ENDPOINT, SOURCE_FILE, a_client_and_its_tree,
    a_finished_run, ask_for_source, client_over, refusal_from, source_window,
    stage_tree)

# The line a well-formed request names, when the subject is the path and not the
# line. `FIRST_LINE` is used where the whole window has to be a known list.
A_REAL_LINE = 5
FIRST_LINE = 1

# Paths that must never be read, each a different way of leaving the tree. The
# last is the one a string check on "../" would miss.
CLIMBING_OUT = "../../etc/passwd"
ONE_LEVEL_UP = "../secret.txt"
ABSOLUTE_PATH = "/etc/passwd"
INSIDE_LOOKING_OUT = "tools/../../secret.txt"

# A file that is simply not there, and a directory, which is not a file either.
MISSING_FILE = "no-such-module.py"
A_DIRECTORY = "tools"

# What the sentence says when a path does not name a file of this run's tree.
NOT_OF_THIS_TREE = "is not a file of this run's audited tree"

# The second app beside the first. Named by a caller trying to walk sideways
# into a tree some *other* run fetched -- a real shape here, since every fetch
# lands under one root.
OTHER_APP = "another-app"
SIDEWAYS = f"../{OTHER_APP}/{SOURCE_FILE}"

# What the sibling tree's file says, so which tree was read is visible in the
# lines rather than inferred from a status.
OTHER_TEXT = "# this line is in the other app tree and in no other\n"

# A link planted inside the tree, pointing out of it.
SYMLINK_NAME = "shortcut.py"

# What the file outside the tree would hold, so a leak would be unmistakable.
SECRET_FILE = "secret.txt"
SECRET_TEXT = "a file beside the tree that this endpoint must never hand back\n"


# --- the reads that must work, so the refusals below mean something -----------

def test_a_file_of_the_audited_tree_is_read(monkeypatch, tmp_path) -> None:
    """Non-vacuity for this whole file: a route that refused everything would pass it all."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    assert source_window(client, SOURCE_FILE, A_REAL_LINE)["line"] == A_REAL_LINE


# --- the path may not leave the tree ------------------------------------------

@pytest.mark.parametrize("asked", [CLIMBING_OUT, ONE_LEVEL_UP, ABSOLUTE_PATH,
                                   INSIDE_LOOKING_OUT])
def test_a_path_that_resolves_outside_the_tree_is_refused(monkeypatch, tmp_path,
                                                          asked: str) -> None:
    """Four spellings of the same attempt, refused by one rule rather than three checks.

    Measured: with the containment half removed, the first case is still refused
    -- `/etc/passwd` reached from under `tmp_path` is a file that does not exist,
    so `is_file()` catches it. It is kept because it is the spelling a reader
    expects to see; the three below it, the symlink and the sideways walk are
    the cases that isolate containment, and each of those really does reach a
    file that is there.
    """
    client, tree = a_client_and_its_tree(monkeypatch, tmp_path)
    (tree.parent / SECRET_FILE).write_text(SECRET_TEXT, encoding="utf-8")
    detail = refusal_from(ask_for_source(client, asked, A_REAL_LINE), REFUSED)
    assert NOT_OF_THIS_TREE in detail


def test_the_file_it_was_climbing_towards_really_exists(monkeypatch, tmp_path) -> None:
    """Guard on the guard: refusing a path to a file that is not there proves nothing."""
    _client, tree = a_client_and_its_tree(monkeypatch, tmp_path)
    (tree.parent / SECRET_FILE).write_text(SECRET_TEXT, encoding="utf-8")
    assert (tree / ONE_LEVEL_UP).resolve().is_file()


def test_no_refused_reply_carries_the_text_it_was_reaching_for(monkeypatch,
                                                               tmp_path) -> None:
    """The refusal is a sentence about the path; it must not quote what is at the end of it."""
    client, tree = a_client_and_its_tree(monkeypatch, tmp_path)
    (tree.parent / SECRET_FILE).write_text(SECRET_TEXT, encoding="utf-8")
    response = ask_for_source(client, ONE_LEVEL_UP, A_REAL_LINE)
    assert SECRET_TEXT.strip() not in response.text


def test_a_symlink_pointing_out_of_the_tree_is_refused(monkeypatch, tmp_path) -> None:
    """Resolution happens before the check, which is what makes a link the same case."""
    client, tree = a_client_and_its_tree(monkeypatch, tmp_path)
    outside = tree.parent / SECRET_FILE
    outside.write_text(SECRET_TEXT, encoding="utf-8")
    (tree / "shortcut.py").symlink_to(outside)
    detail = refusal_from(ask_for_source(client, "shortcut.py", A_REAL_LINE), REFUSED)
    assert NOT_OF_THIS_TREE in detail


def test_another_runs_tree_cannot_be_reached_sideways(monkeypatch, tmp_path) -> None:
    """Every fetch lands under one root, so a sibling tree is a real thing to aim at."""
    stage_tree(tmp_path, app=OTHER_APP)
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    detail = refusal_from(ask_for_source(client, SIDEWAYS, A_REAL_LINE), REFUSED)
    assert NOT_OF_THIS_TREE in detail


def test_the_sibling_tree_the_sideways_path_names_really_exists(monkeypatch,
                                                                tmp_path) -> None:
    """Guard on the guard above, for the same reason as the one about the secret."""
    other = stage_tree(tmp_path, app=OTHER_APP)
    assert (other / SOURCE_FILE).is_file()


@pytest.mark.parametrize("asked", [MISSING_FILE, A_DIRECTORY])
def test_a_path_inside_the_tree_that_is_not_a_file_is_refused(monkeypatch, tmp_path,
                                                              asked: str) -> None:
    """Inside and not a file: a missing module, and a directory, which cannot be read as one."""
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    assert NOT_OF_THIS_TREE in refusal_from(
        ask_for_source(client, asked, A_REAL_LINE), REFUSED)


# --- the directory is the run's own, never the caller's -----------------------

def test_the_tree_read_is_the_one_the_run_recorded(monkeypatch, tmp_path) -> None:
    """Move the record's app and the same request reads the other tree: the record decides."""
    stage_tree(tmp_path)
    other = stage_tree(tmp_path, app=OTHER_APP)
    (other / SOURCE_FILE).write_text(OTHER_TEXT, encoding="utf-8")
    client = client_over(monkeypatch, tmp_path, a_finished_run(app=OTHER_APP))
    assert source_window(client, SOURCE_FILE, FIRST_LINE)["lines"] == [
        OTHER_TEXT.rstrip("\n")]


def test_an_app_named_by_the_caller_changes_nothing(monkeypatch, tmp_path) -> None:
    """The other direction, and the one that matters: a request cannot name a tree.

    A parameter the endpoint does not declare is simply not read, so this is a
    guard against one being *added* -- the obvious way to make the page able to
    show a file from another run, and the way that turns a confined read into an
    open one.
    """
    other = stage_tree(tmp_path, app=OTHER_APP)
    (other / SOURCE_FILE).write_text(OTHER_TEXT, encoding="utf-8")
    client, _tree = a_client_and_its_tree(monkeypatch, tmp_path)
    answered = client.get(SOURCE_ENDPOINT.format(run_id=RUN_ID),
                          params={"file": SOURCE_FILE, "line": FIRST_LINE,
                                  "app": OTHER_APP})
    assert answered.status_code == OK
    assert OTHER_TEXT.rstrip("\n") not in answered.json()["lines"]



"""Nothing a caller sends becomes a path of its choosing, and the folder is always a run's.

`web/key_scope.py` is the one place a run id becomes a folder, and it can only
answer with `run_files.run_keys(...)`. That is the whole subject here, and it is
a stronger boundary than the one it replaced: `grading_keys/` holds the answers
this tool is scored against, and it is now **unreachable from this server**
rather than one directory away.

**It was one directory away, and that was a live defect, not a theoretical one.**
The store joined `keys.key_drafting.DRAFTED_KEYS_DIR` -- the checkout's
`grading_keys/drafts/` -- while `web/run_jobs.py` passed
`--drafts-dir artifacts/runs/<run_id>/keys` to every audit it started. The two
never met: the editor answered 404 for every key this server had written, and a
save would have gone into the folder holding a human's own corrected drafts. So
the last section below asserts the *absence* of that binding under `web/`, which
is the check that would have caught it from the other side.

**Nothing the caller sends is a name any more.** The run id is checked against
`run_routes.RUN_ID` before any join, and the app comes off the run's own record.
`key_draft_store.APP_NAME` still runs, and it is defence in depth now rather
than the front line: the record is server-written, but it is the value that
would reach the filesystem, and a hand-edited history database is how it could
carry a traversal.

**Two 404s that are not the same fact.** An id the pattern excludes never
reaches a join -- and a percent-encoded `../` never reaches the guard either,
because a decoded `/` means no route matches at all. Both are asserted by the
*detail* they answer with, because a test that only counted 404s could not tell
a guard that fired from a route that was never matched.

**And a "draft" is a file, which is not the same as a path that exists.** The
read tests `is_file()`, because a *directory* called `<app>.ground_truth.json`
would otherwise fail on being opened rather than being reported absent.

A draft that is *there* and unreadable is a 400 and a different file:
`test_key_draft_corruption.py`.

Driven through the routes rather than by calling the store directly: it raises
`HTTPException`, so its refusals only mean something as the status and detail a
caller actually sees.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import ast
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import run_files                                              # noqa: E402
from keys.grading_keys import GROUND_TRUTH_SUFFIX              # noqa: E402

from .key_fixtures import (                                   # noqa: E402
    APP, KEYS_ENDPOINT, NO_SUCH_DRAFT, RUN_ID, client_over, keys_dir, plant,
    planted_client, read_draft)

# Three 404s that mean different things. The first is the app guard, the second
# the run guard, and the third is Starlette answering that nothing matched.
NO_SUCH_NAME = "no draft has that name"
NO_SUCH_RUN = "no run has that id"
NOT_FOUND = "Not Found"

# Ids that reach the handler and are refused by `RUN_ID`. The backslash is the
# one with teeth: it is a path separator where `pathlib` would join it.
BACKSLASH_TRAVERSAL = "..%5C..%5Csecret"
AN_ID_WITH_A_SPACE = "demo run"
TOO_SHORT = "d" * 31
NOT_HEX = "z" * 32

# A percent-encoded `../`, which is decoded to a path with a separator in it and
# so matches no route. It never reaches the guard.
ENCODED_TRAVERSAL = "%2e%2e%2f%2e%2e%2fsecret"

# A well-formed id no row carries: looked, found nothing.
AN_UNUSED_ID = "e" * 32

# An app name the record could carry only after a hand edit, and the one whose
# dots are legal. `..` matches `APP_NAME` and joins to `...ground_truth.json`
# inside the folder rather than to its parent, which is why it is not a hole.
A_TRAVERSING_APP = "../../secret"
A_DOTTED_APP = ".."

# A name that matches the glob and is not a key: a directory somebody made.
A_DIRECTORY_APP = "not-really-a-draft"

# The folder the old store joined. No module under `web/` may bind it now.
DRAFTS_FOLDER = "DRAFTED_KEYS_DIR"

# The one join that is allowed, and the two modules entitled to make it: the
# writer that tells an audit where to draft, and the reader that serves it back.
# Both, and only both -- a third would be a third opinion about where a key
# lives, and two disagreeing opinions is the defect this file records.
THE_JOIN = "run_keys"
THE_WRITER = "run_jobs.py"
THE_READER = "key_scope.py"
WEB = Path(__file__).resolve().parents[2] / "web"


def modules_binding(name: str) -> list[str]:
    """Every module under `web/` that imports one name into its own namespace.

    Parsed rather than grepped: a name in a docstring or a comment is not a
    binding, and it is the binding a `monkeypatch.setattr` has to find.
    """
    found = []
    for path in sorted(WEB.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = any(alias.name == name
                       for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                       for alias in node.names)
        if imported:
            found.append(path.name)
    return found


def modules_calling(attribute: str) -> list[str]:
    """Every module under `web/` that calls `<something>.<attribute>(...)`."""
    found = []
    for path in sorted(WEB.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called = any(isinstance(node.func, ast.Attribute) and node.func.attr == attribute
                     for node in ast.walk(tree) if isinstance(node, ast.Call))
        if called:
            found.append(path.name)
    return found


# --- the ids that are not runs --------------------------------------------------

def test_a_run_nobody_started_is_a_404_saying_so(monkeypatch, tmp_path) -> None:
    """A well-formed id for a run no row carries: found nothing, rather than refused."""
    client, _drafts = planted_client(monkeypatch, tmp_path)

    response = client.get(f"/api/runs/{AN_UNUSED_ID}/key")

    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == NO_SUCH_RUN


@pytest.mark.parametrize("run_id",
                         [BACKSLASH_TRAVERSAL, AN_ID_WITH_A_SPACE, TOO_SHORT, NOT_HEX])
def test_an_id_the_pattern_excludes_is_refused_before_any_path_is_joined(
        monkeypatch, tmp_path, run_id: str) -> None:
    """`RUN_ID` is checked first, so the id never reaches `run_keys` at all."""
    client, _drafts = planted_client(monkeypatch, tmp_path)

    response = client.get(f"/api/runs/{run_id}/key")

    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == NO_SUCH_RUN


def test_an_encoded_traversal_never_reaches_the_guard_because_no_route_matches(
        monkeypatch, tmp_path) -> None:
    """Asserted by the detail, not the status: this is Starlette, not `RUN_ID`.

    A decoded `%2f` is a path separator, and `/api/runs/{run_id}/key` matches one
    segment. Worth pinning as a separate fact, because "the traversal was
    refused" reads as though the guard had run, and a change to the route's path
    -- to `{run_id:path}`, say -- would silently make that the only thing
    standing in front of a filesystem join.
    """
    client, _drafts = planted_client(monkeypatch, tmp_path)

    response = client.get(f"/api/runs/{ENCODED_TRAVERSAL}/key")

    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == NOT_FOUND


# --- and the app name the record carries, which is the value that gets joined ---

def test_an_app_name_the_pattern_excludes_is_refused(monkeypatch, tmp_path) -> None:
    """Defence in depth: the record is server-written, and a hand edit is what this is for."""
    drafts = plant(tmp_path)
    client = client_over(monkeypatch, drafts, app_name=A_TRAVERSING_APP)

    response = client.get(KEYS_ENDPOINT)

    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == NO_SUCH_NAME


def test_a_name_of_dots_alone_stays_inside_the_runs_folder(monkeypatch, tmp_path) -> None:
    """`..` does match `APP_NAME` -- dots are legal in an app name -- and joins to a filename.

    Not a hole, and worth saying why: `key_path` appends the suffix, so the name
    reached is `...ground_truth.json` inside the folder, not its parent.
    """
    drafts = plant(tmp_path)
    client = client_over(monkeypatch, drafts, app_name=A_DOTTED_APP)

    response = client.get(KEYS_ENDPOINT)

    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"].startswith("no drafted key for ..")
    assert sorted(path.name for path in drafts.iterdir()) == [
        f"{APP}{GROUND_TRUTH_SUFFIX}", f"{APP}.manifest.json"]


# --- the folder it can reach, and the one it no longer can ----------------------

def test_no_module_under_web_binds_the_checkouts_drafts_folder() -> None:
    """The defect from the other side: this server cannot name `grading_keys/drafts/`.

    It bound it until 2026-09-19, and the editor was unusable for exactly the
    runs this server produces. A binding coming back is either that bug
    returning or an unauthenticated endpoint reaching the project's own
    measurements, and both should fail here.
    """
    assert modules_binding(DRAFTS_FOLDER) == []


def test_the_writer_and_the_reader_ask_the_same_function_where_a_key_lives() -> None:
    """The cause, not the symptom: two opinions about that path is the whole defect.

    `run_jobs` tells an audit where to draft and `key_scope` serves the result
    back, and before 2026-09-19 only the first went through `run_keys` -- the
    second joined the checkout's drafts folder instead, so the two named
    different places and the editor could never find what the server wrote.
    Going through one function is what makes them agree by construction, and a
    third caller would be a third opinion.
    """
    assert modules_calling(THE_JOIN) == sorted([THE_READER, THE_WRITER])


def test_the_scan_can_see_a_binding_and_a_call_at_all() -> None:
    """Guard: a parser that found nothing would make both claims above about zero."""
    assert modules_binding("HTTPException") != []
    assert modules_calling("register") != []


def test_the_folder_a_run_is_given_is_under_the_runs_tree(monkeypatch, tmp_path) -> None:
    """The positive half: what the route reads really is this run's own directory."""
    drafts = plant(tmp_path)
    client = client_over(monkeypatch, drafts)

    assert read_draft(client)["app"] == APP
    assert drafts == keys_dir(tmp_path)
    assert RUN_ID in drafts.parts


def test_the_folder_these_tests_plant_in_is_the_one_the_real_join_answers(
        monkeypatch, tmp_path) -> None:
    """Otherwise every test in this folder reads a directory no route could name.

    `keys_dir` is the fixture's own spelling of the path and `run_files.run_keys`
    is the server's. Two spellings of one path is exactly the shape that broke
    the editor -- `run_jobs` built one and the store built another -- so the
    fixture is held against the real function rather than trusted to match it.
    """
    drafts = plant(tmp_path)
    client_over(monkeypatch, drafts)

    assert run_files.run_keys(RUN_ID) == drafts


# --- a name that matches and is not a file -------------------------------------

def test_a_directory_named_like_a_key_is_not_readable_as_one(
        monkeypatch, tmp_path) -> None:
    """404, not a traceback out of `read_text`: the same filter `discover_graded_apps` uses."""
    drafts = plant(tmp_path)
    (drafts / f"{A_DIRECTORY_APP}{GROUND_TRUTH_SUFFIX}").mkdir()
    client = client_over(monkeypatch, drafts, app_name=A_DIRECTORY_APP)

    response = client.get(KEYS_ENDPOINT)

    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"].startswith(f"no drafted key for {A_DIRECTORY_APP}")


def test_the_real_draft_beside_it_is_still_readable(monkeypatch, tmp_path) -> None:
    """Non-vacuity: the filter drops the directory and keeps the file."""
    drafts = plant(tmp_path)
    (drafts / f"{A_DIRECTORY_APP}{GROUND_TRUTH_SUFFIX}").mkdir()
    client = client_over(monkeypatch, drafts)

    assert read_draft(client)["app"] == APP

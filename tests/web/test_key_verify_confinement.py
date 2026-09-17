"""Which draft the verify route may touch, and the folder it may never write into.

**This is the feature's whole security argument, on the one route that writes.**
`grading_keys/` holds the answers this tool is scored against; an
unauthenticated endpoint able to write there would let anyone reaching the port
rewrite the project's own measurements. `test_key_routes.py` asserts the folder
for the two routes that list and save, and nothing held it for this one --
which is the route that stamps a field every published figure is qualified by.

**A draft is the least trustworthy input this project has.** It is hand-edited
between being written and being promoted, so it can be absent, named something
nobody drafted, or left half-saved by an interrupted editor. Each is a different
answer: 404 for a name with no draft, 404 for a name the pattern excludes before
any path is joined, and 400 naming the file for one that will not parse.

What the name rules are, and what a second claim does, is
`test_key_verify_refusals.py`.

Nothing here writes to the checkout's own `grading_keys/drafts/` -- the last
three tests are what prove it rather than assert it in a comment.
"""

import json

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import key_draft_store                                        # noqa: E402
from keys import grading_keys                                 # noqa: E402

from .corrupt_fixtures import UNPARSEABLE                     # noqa: E402
from .key_fixtures import (                                   # noqa: E402
    APP, NO_SUCH_DRAFT, REFUSED, planted_client)
from .key_verify_fixtures import CHECKED_BY, claim, claimed   # noqa: E402

# A name nobody drafted a key for, and one the pattern excludes before any path
# is joined -- two 404s that mean different things.
NEVER_DRAFTED = "never-drafted"
A_NAME_WITH_A_SPACE = "demo app"
NO_SUCH_NAME = "no draft has that name"

# What a hand edit leaves behind when a save is interrupted: not JSON.
HALF_SAVED = '{"app": "demo-app", "findings": ['

DRAFT_FILE = f"{APP}.ground_truth.json"


def real_keys_folder() -> dict:
    """Every file at the top level of the checkout's own grading keys folder.

    Read through `grading_keys.KEYS_DIR`, which is what a route that escaped its
    drafts folder would reach. Nothing here redirects it.
    """
    return {path.name: path.read_bytes()
            for path in sorted(grading_keys.KEYS_DIR.iterdir()) if path.is_file()}


# --- a draft that is not there, or not readable --------------------------------

def test_verifying_an_app_with_no_draft_is_a_404_naming_it(monkeypatch, tmp_path) -> None:
    """A well-formed name for a key nobody drafted: found nothing, rather than refused."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    response = claim(client, CHECKED_BY, NEVER_DRAFTED)
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == f"no drafted key for {NEVER_DRAFTED}"


def test_a_name_the_pattern_excludes_is_refused_before_any_path_is_joined(
        monkeypatch, tmp_path) -> None:
    """`APP_NAME` runs first here too, so a name never becomes a path of the caller's choosing."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    response = claim(client, CHECKED_BY, A_NAME_WITH_A_SPACE)
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"] == NO_SUCH_NAME


def test_a_hand_corrupted_draft_is_named_rather_than_crashed_on(
        monkeypatch, tmp_path) -> None:
    """A draft is hand-edited between being written and being promoted, so this happens.

    `key_draft_store.read` answers 400 with the file's name; before it did, an
    interrupted save reached the page as a 500 and a traceback in the log.
    """
    client, drafts = planted_client(monkeypatch, tmp_path)
    (drafts / DRAFT_FILE).write_text(HALF_SAVED, encoding="utf-8")
    response = claim(client, CHECKED_BY)
    assert response.status_code == REFUSED
    assert UNPARSEABLE in response.json()["detail"]


def test_the_corrupted_draft_is_left_as_it_was(monkeypatch, tmp_path) -> None:
    """Refusing it must not overwrite it: the half-saved text is what a human recovers from."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    broken = drafts / DRAFT_FILE
    broken.write_text(HALF_SAVED, encoding="utf-8")
    claim(client, CHECKED_BY)
    assert broken.read_text(encoding="utf-8") == HALF_SAVED


# --- the folder it writes into -------------------------------------------------

def test_the_recorded_check_lands_in_the_drafts_folder_it_was_given(
        monkeypatch, tmp_path) -> None:
    """Where the write goes, asserted on the file rather than on the reply."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    claimed(client, CHECKED_BY)
    written = json.loads((drafts / DRAFT_FILE).read_text(encoding="utf-8"))
    assert written["verified_by"] == CHECKED_BY


def test_a_recorded_check_writes_nothing_into_the_real_keys_folder(
        monkeypatch, tmp_path) -> None:
    """The security argument for the whole feature, and the one route that writes.

    `grading_keys/` is this project's committed evidence and this endpoint has no
    authentication. The comparison is before against after, so it fails on a file
    appearing whether or not one was there to begin with.
    """
    before = real_keys_folder()
    client, _drafts = planted_client(monkeypatch, tmp_path)
    claimed(client, CHECKED_BY)
    assert real_keys_folder() == before


def test_the_folder_the_net_watches_is_the_parent_of_the_one_written_to() -> None:
    """Guard: a net over an unrelated folder would hold however the route behaved.

    The two tests above are only a pair if the folder compared before and after
    is the one a route escaping its drafts folder would land in. *Which* module
    is allowed to join that folder at all -- one, and it is the store -- is
    `test_key_draft_store.py`, asserted there by parsing the imports.
    """
    assert grading_keys.KEYS_DIR.is_dir()
    assert key_draft_store.DRAFTED_KEYS_DIR.parent == grading_keys.KEYS_DIR

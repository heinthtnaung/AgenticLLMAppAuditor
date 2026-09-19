"""Which draft the verify route may touch, and the folder it may never write into.

**This is the feature's whole security argument, on the one route that writes.**
`grading_keys/` holds the answers this tool is scored against; an
unauthenticated endpoint able to write there would let anyone reaching the port
rewrite the project's own measurements. `test_key_routes.py` asserts the folder
for the two routes that list and save, and nothing held it for this one --
which is the route that stamps a field every published figure is qualified by.

**A draft is the least trustworthy input this project has.** It is hand-edited
between being written and being promoted, so it can be absent, belong to a run
that drafted none, or be left half-saved by an interrupted editor. Each is a
different answer: 404 for a run with no draft, 404 for an app name the pattern
excludes before any path is joined, and 400 naming the file for one that will
not parse.

The claim is addressed by run now, so the name in the URL is a run id and the
app comes off that run's record -- see `test_key_draft_store.py` for why, and
for the defect that shape fixed.

What the name rules are, and what a second claim does, is
`test_key_verify_refusals.py`.

Nothing here writes to the checkout's own `grading_keys/drafts/` -- the last
three tests are what prove it rather than assert it in a comment.
"""

import json

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from keys import grading_keys                                 # noqa: E402

from .corrupt_fixtures import UNPARSEABLE                     # noqa: E402
from .key_fixtures import (                                   # noqa: E402
    APP, NO_SUCH_DRAFT, REFUSED, client_over, plant, planted_client)
from .key_verify_fixtures import CHECKED_BY, claim, claimed   # noqa: E402

# An app whose run drafted no key, and one the pattern excludes before any path
# is joined -- two 404s that mean different things. Both reach this route
# through the run's record rather than through the URL.
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

def test_verifying_a_run_with_no_draft_is_a_404_naming_the_app(monkeypatch, tmp_path) -> None:
    """A run that drafted no key: found nothing, rather than refused."""
    client = client_over(monkeypatch, plant(tmp_path), app_name=NEVER_DRAFTED)
    response = claim(client, CHECKED_BY)
    assert response.status_code == NO_SUCH_DRAFT
    assert response.json()["detail"].startswith(f"no drafted key for {NEVER_DRAFTED}")


def test_a_name_the_pattern_excludes_is_refused_before_any_path_is_joined(
        monkeypatch, tmp_path) -> None:
    """`APP_NAME` runs on this route too, so a record's name never becomes a chosen path."""
    client = client_over(monkeypatch, plant(tmp_path), app_name=A_NAME_WITH_A_SPACE)
    response = claim(client, CHECKED_BY)
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


def test_the_folder_the_net_watches_is_the_one_the_route_must_never_reach(
        monkeypatch, tmp_path) -> None:
    """Guard: a net over an unrelated folder would hold however the route behaved.

    The two tests above are only a pair if the folder compared before and after
    is the one this server may not write into. It used to be asserted as a
    *parent* relation -- the route wrote to `grading_keys/drafts/`, one level
    inside the watched folder, so escaping it was a plausible slip. The route
    writes under `artifacts/runs/` now and the two trees are disjoint, which is
    the stronger arrangement and is what this asserts instead: reaching
    `grading_keys/` is no longer a slip, it is a different path entirely.

    *Which* modules may join a key folder at all -- two, the writer and the
    reader, through one function -- is `test_key_draft_store.py`.
    """
    drafts = plant(tmp_path)
    client_over(monkeypatch, drafts)

    assert grading_keys.KEYS_DIR.is_dir()
    assert grading_keys.KEYS_DIR.resolve() not in drafts.resolve().parents

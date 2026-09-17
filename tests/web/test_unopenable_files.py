"""A hand-editable file nobody can open, through both readers that open one.

The third way a hand edit breaks a file, after "not json" and "json of the wrong
shape": the mode is wrong and the read fails. It is the same fault as the other
two -- a guarded read that named a narrower failure than the one it meets -- and
it was in **both** guarded readers this project has, including the one written
to fix the fault class. Measured before the fix:

    draft chmod 000 -> 500   GET /api/keys/{app}
    pin   chmod 000 -> PermissionError, which is not a ValueError, so
                       `_pin_note` did not catch it either -> 500

`OSError` is neither a `ValueError` nor a `json.JSONDecodeError`, which is
exactly why it escaped: `key_draft_store._json_object` caught the parse error
and answered a named 400, and the file one `except` clause away was a traceback
in the log.

**Two modules, one file, on purpose.** `web/key_draft_store.py` and
`src/fetch_repo.py` are read by different routes with different fixtures, and
the interesting fact is that the same omission was in both. Splitting it would
leave two files each describing half a defect. What each refusal *says* -- the
corrupt-text half of the same vocabulary -- stays in `test_key_draft_corruption.py`,
`test_key_manifest_corruption.py` and `test_source_pin_notes.py`.

`locked_file.locked` attempts the read before any test goes on and skips if it
succeeded, so this cannot pass as root by reading a file it claimed was
unreadable. Nothing here writes to the checkout's own `grading_keys/drafts/` or
reads a repository this project does not own.
"""

import errno
import os

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import fetch_repo                                             # noqa: E402
from keys.grading_keys import MANIFEST_SUFFIX                 # noqa: E402
from locked_file import locked                                # noqa: E402

from .corrupt_fixtures import (                               # noqa: E402
    ROUTES, UNPARSEABLE, draft_files, key_file_name, pin_file_name)
from .key_fixtures import REFUSED, key_on_disk, planted_client   # noqa: E402
from .key_verify_fixtures import CHECKED_BY, claim, verified_fields   # noqa: E402
from .source_fixtures import (                                # noqa: E402
    APP, OK, SOURCE_FILE, ask_for_source, client_over, source_window, stage_tree)

# Both hand-edited files of a draft, by name. A person corrects the key, and
# `key_promotion.GRADED_PIN_FIELDS` says a person types the manifest's framework
# and language -- so the mode of either is something a hand can get wrong.
HAND_EDITED_FILES = (key_file_name(), pin_file_name())

# What an untouched draft says about being checked, so "the refusal recorded
# nothing" is an equality and not an absence.
UNCLAIMED = (False, None, None)

# The line the source window is asked for when the subject is the note.
A_LINE = 10

# What the operating system calls a read denied by the mode, asked of the
# operating system rather than spelled: the claim is that the reader's message
# carries the real reason through, not that this machine words it a given way.
DENIED = os.strerror(errno.EACCES)


def locked_draft_file(monkeypatch, tmp_path, file_name: str):
    """A planted draft with one of its two files unopenable, and a client over it."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    locked(draft_files(drafts)[file_name])
    return client, drafts


def client_over_a_locked_pin(monkeypatch, tmp_path):
    """A staged tree whose pin nobody can open, and a client over the run that audited it."""
    stage_tree(tmp_path)
    locked(fetch_repo.manifest_path(tmp_path / "fetched", APP))
    return client_over(monkeypatch, tmp_path)


# --- the drafted key and its manifest, through every route that reads them --------

@pytest.mark.parametrize("file_name", HAND_EDITED_FILES)
@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
def test_a_file_nobody_can_open_is_refused_rather_than_crashed_on(
        monkeypatch, tmp_path, route, file_name: str) -> None:
    """A 400 with a sentence, on all three routes, for both hand-edited files."""
    client, _drafts = locked_draft_file(monkeypatch, tmp_path, file_name)
    response = route(client)
    assert response.status_code == REFUSED, response.text
    assert UNPARSEABLE in response.json()["detail"]


@pytest.mark.parametrize("file_name", HAND_EDITED_FILES)
def test_the_refusal_names_the_file_nobody_could_open(monkeypatch, tmp_path,
                                                      file_name: str) -> None:
    """And names the right one of the two: the other is sitting there perfectly readable."""
    client, _drafts = locked_draft_file(monkeypatch, tmp_path, file_name)
    detail = ROUTES["GET"](client).json()["detail"]
    other = [name for name in HAND_EDITED_FILES if name != file_name][0]
    assert file_name in detail
    assert other not in detail


def test_the_refusal_carries_the_reason_the_open_failed(monkeypatch, tmp_path) -> None:
    """Non-vacuity: "cannot be read as json" alone would not tell a reader to `chmod`."""
    client, _drafts = locked_draft_file(monkeypatch, tmp_path, key_file_name())
    assert DENIED in ROUTES["GET"](client).json()["detail"]


def test_a_refused_verify_records_no_claim_against_an_unopenable_manifest(
        monkeypatch, tmp_path) -> None:
    """The route whose whole job is recording that a human looked must not record it here.

    This is the pairing that made the corrupt-manifest defect worse than a 500:
    both writing routes wrote before they validated, so a failed request left a
    human claim nobody made. The key is readable in this test -- only the
    manifest is locked -- so what it says can be read back.
    """
    client, drafts = locked_draft_file(monkeypatch, tmp_path, pin_file_name())
    assert claim(client, CHECKED_BY).status_code == REFUSED
    assert verified_fields(key_on_disk(drafts)) == UNCLAIMED


# --- and the pin, through the source window --------------------------------------

def test_a_pin_nobody_can_open_lands_in_unchecked(monkeypatch, tmp_path) -> None:
    """The other module, the other route, the same omission: a note, not a 500."""
    note = source_window(client_over_a_locked_pin(monkeypatch, tmp_path),
                         SOURCE_FILE, A_LINE)["unchecked"]
    assert UNPARSEABLE in note
    assert f"{APP}{MANIFEST_SUFFIX}" in note


def test_a_window_over_a_locked_pin_is_still_answered_with_200(monkeypatch,
                                                               tmp_path) -> None:
    """A pin nobody can open is not a file nobody can read: the window still comes back."""
    client = client_over_a_locked_pin(monkeypatch, tmp_path)
    assert ask_for_source(client, SOURCE_FILE, A_LINE).status_code == OK

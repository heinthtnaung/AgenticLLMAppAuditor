"""Handing an attached file back: told, never sniffed, and never rendered.

An attachment is attacker-chosen bytes stored by an endpoint with no
authentication, on a server that serves a page from the same origin. Served
inline, an attached `.html` would run as script in that origin -- the same
reason every artifact download is an attachment, arriving here with one more
count against it: an artifact was at least written by `src/`.

So three headers together, and each is asserted on its own because each fails on
its own:

- `application/octet-stream`, **told** rather than read off the machine's mime
  table and never the type the client declared,
- `X-Content-Type-Options: nosniff`, so a browser may not override what it was
  told,
- `Content-Disposition: attachment`, so a download is the only thing on offer.

The display name that goes in that last header is the one value in this reply
the client chose, and it has enough rules of its own to be a file of its own:
`test_uploads_filename.py`.

The four ways there is nothing to serve are the last section, and the fourth is
the interesting one: the run still lists the attachment and the file is gone
from disk. That is a gap, it is said as one, and it is not a 200 of zero bytes.

The whole file skips without the server packages: with no fastapi there is
nothing serving files.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import uploads                                     # noqa: E402

from .upload_fixtures import (                     # noqa: E402
    CONTENT, NO_SUCH_RUN_ID, RUN_ID, attach, a_run_to_attach_to, files_under)

OK = 200
NOT_FOUND = 404

# The headers a reply must carry, spelled as a client reads them.
DISPOSITION = "content-disposition"
CONTENT_TYPE = "content-type"
NOSNIFF_HEADER = "x-content-type-options"

ATTACHMENT = "attachment"
NOSNIFF = "nosniff"

# What the reply must never be served as: the type the client declared, and the
# type a mime table would guess from a name ending in `.json`.
CLIENT_DECLARED_TYPE = "image/svg+xml"
GUESSED_FROM_THE_NAME = "application/json"

# An upload id that is well formed and belongs to no attachment, and one that is
# not well formed at all. Both are "this run has no such attachment".
NO_SUCH_UPLOAD_ID = "c" * 32
MALFORMED_UPLOAD_ID = "../../../etc/passwd"


def attached(client, **kwargs) -> dict:
    """Post one file and return the attachment record the endpoint answered with."""
    response = attach(client, **kwargs)
    assert response.status_code == 201, response.text
    return response.json()


def served(client, upload_id: str, run_id: str = RUN_ID):
    """Ask for one attached file back."""
    return client.get(f"/api/runs/{run_id}/uploads/{upload_id}")


# --- what comes back ------------------------------------------------------------

def test_an_attached_file_comes_back_byte_for_byte(tmp_path) -> None:
    """Non-vacuity for every header below: there is really a file being served."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    response = served(client, attached(client)["upload_id"])
    assert response.status_code == OK
    assert response.content == CONTENT


def test_the_type_is_told_and_is_not_guessed_from_the_name(tmp_path) -> None:
    """The display name ends in `.json`; a mime table would answer differently."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    response = served(client, attached(client)["upload_id"])
    assert response.headers[CONTENT_TYPE] == uploads.UPLOAD_TYPE
    assert GUESSED_FROM_THE_NAME not in response.headers[CONTENT_TYPE]


def test_the_type_the_client_declared_is_never_served_back(tmp_path) -> None:
    """It was never stored, so there is nothing here to echo -- said as the reply."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    answered = attached(client, headers={"Content-Type": CLIENT_DECLARED_TYPE})
    assert served(client, answered["upload_id"]).headers[CONTENT_TYPE] == uploads.UPLOAD_TYPE


def test_the_browser_is_told_not_to_sniff(tmp_path) -> None:
    """The type is told; this is what stops a browser overriding it by looking at the bytes."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    response = served(client, attached(client)["upload_id"])
    assert response.headers[NOSNIFF_HEADER] == NOSNIFF


def test_every_reply_is_a_download_and_not_a_page(tmp_path) -> None:
    """Attacker-chosen bytes in an origin that serves this page: rendering is the whole risk."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    response = served(client, attached(client)["upload_id"])
    assert response.headers[DISPOSITION].startswith(ATTACHMENT)


# --- the four ways there is nothing to serve ---------------------------------------

def test_a_run_nobody_stored_has_no_attachments(tmp_path) -> None:
    """A well-formed id no row carries: there is no run to look an attachment up on."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    answered = attached(client)
    assert served(client, answered["upload_id"],
                  run_id=NO_SUCH_RUN_ID).status_code == NOT_FOUND


def test_an_upload_this_run_never_had_is_refused(tmp_path) -> None:
    """Looked up on the run's own list, so another run's id is not another run's file."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    attached(client)
    assert served(client, NO_SUCH_UPLOAD_ID).status_code == NOT_FOUND


def test_a_malformed_upload_id_never_reaches_a_path_join(tmp_path) -> None:
    """The reason both ids are checked against the run routes' pattern before use."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    attached(client)
    assert served(client, MALFORMED_UPLOAD_ID).status_code == NOT_FOUND


def test_an_attachment_the_run_lists_and_the_disk_has_lost_is_said_to_be_gone(tmp_path) -> None:
    """A gap, said as one. Not a 200 of zero bytes, and not the same sentence as "no such id"."""
    client, _, root = a_run_to_attach_to(tmp_path)
    answered = attached(client)
    files_under(root)[0].unlink()
    response = served(client, answered["upload_id"])
    assert response.status_code == NOT_FOUND
    assert "gone from disk" in response.json()["detail"]

"""Attaching a file to a run: what lands on disk, and what is only ever metadata.

**The stored filename *is* the server-generated upload id.** That is the
security property this file exists for, and it is not a naming convention:
these are attacker-chosen bytes arriving at an endpoint with no authentication,
so the name a browser sent must never choose a path component. It is kept inside
the record, where it is data a page renders, and the file on disk is 32 hex
characters -- checked against the same pattern the run routes apply to a run id.

Two more things are asserted here because they are easy to get wrong in the
other direction:

- **The client's declared `Content-Type` is never stored.** It is
  attacker-chosen and could only ever be echoed back, which is how a sniffed
  upload renders in this origin. The record's key set is named, so a fourth key
  cannot appear quietly.
- **`sha256` is of the bytes that landed**, so a reader can tell the file on
  disk from the file that was sent.

**They change no finding.** Nothing under `src/` reads this directory and no
check joins on an upload; `test_uploads_boundary.py` asserts that rather than
repeating it here. The caps are `test_uploads_caps.py`, the way a file is served
back is `test_uploads_serving.py`, the display name in its header is
`test_uploads_filename.py`, and *which* directory these land in is
`test_uploads_destination.py` -- it is an argument to `register`, so nothing
here patches anything.

The whole file skips without the server packages: with no fastapi there is no
endpoint to post to.
"""

import hashlib

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from run_routes import RUN_ID                      # noqa: E402

from .upload_fixtures import (                     # noqa: E402
    CONTENT, DISPLAY_NAME, NO_SUCH_RUN_ID, RUN_ID as THE_RUN, attach,
    a_run_to_attach_to, files_under, stored_uploads)

CREATED = 201
REFUSED = 400
NO_SUCH_RUN = 404

# Every key one attachment record carries, named so a test holds the set rather
# than trusting the handler. A declared content type appearing here would be the
# defect the type is refused for.
EXPECTED_UPLOAD_KEYS = {"upload_id", "name", "bytes", "sha256"}

# A client filename that is a path. Kept verbatim as display metadata and used
# for nothing else -- which is the whole claim, so it is the name most of these
# tests attach under.
TRAVERSING_NAME = "../../../etc/passwd"

# The last segment of it, looked for on disk. A file by this name anywhere under
# the upload root would mean the client's name had chosen a path.
TRAVERSAL_TARGET = "passwd"

# What a browser would declare for a file it thought was renderable. Never
# stored, and the reply's own type is told rather than echoed.
CLIENT_DECLARED_TYPE = "image/svg+xml"

# A second file, so "one run holds several" is exercised and the ids are shown
# to differ.
OTHER_CONTENT = b"a second piece of evidence"
OTHER_NAME = "notes.txt"


def attached(client) -> dict:
    """Post one file and return the attachment record the endpoint answered with."""
    response = attach(client)
    assert response.status_code == CREATED, response.text
    return response.json()


# --- what the endpoint answers with --------------------------------------------

def test_an_attachment_is_answered_with_exactly_the_documented_keys(tmp_path) -> None:
    """Named rather than trusted: a fourth key is how a declared type would arrive."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert set(attached(client)) == EXPECTED_UPLOAD_KEYS


def test_the_display_name_is_what_the_client_called_it(tmp_path) -> None:
    """The name is data. It is kept so a reader knows what they attached."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert attached(client)["name"] == DISPLAY_NAME


def test_the_digest_is_of_the_bytes_that_landed(tmp_path) -> None:
    """So a reader can tell the file on disk from the file that was sent."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert attached(client)["sha256"] == hashlib.sha256(CONTENT).hexdigest()
    assert attached(client)["bytes"] == len(CONTENT)


def test_the_upload_id_is_thirty_two_hex_characters(tmp_path) -> None:
    """`uuid4().hex`, and the route checks a request-supplied id against this pattern."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert RUN_ID.match(attached(client)["upload_id"])


def test_two_attachments_do_not_share_an_id(tmp_path) -> None:
    """Non-vacuity for the id above: a constant would satisfy the shape check."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert attached(client)["upload_id"] != attached(client)["upload_id"]


# --- the name never chooses a path ---------------------------------------------

def test_the_file_on_disk_is_named_by_the_server_and_not_by_the_client(tmp_path) -> None:
    """The security property: attacker-chosen bytes never choose a path component."""
    client, _, root = a_run_to_attach_to(tmp_path)
    answered = attach(client, name=TRAVERSING_NAME).json()
    assert [path.name for path in files_under(root)] == [answered["upload_id"]]


def test_only_thirty_two_hex_names_ever_land_on_disk(tmp_path) -> None:
    """Said over everything written, not over the one file this test knows about."""
    client, _, root = a_run_to_attach_to(tmp_path)
    attach(client, name=TRAVERSING_NAME)
    attach(client, content=OTHER_CONTENT, name=OTHER_NAME)
    assert all(RUN_ID.match(path.name) for path in files_under(root))


def test_a_client_filename_that_is_a_path_writes_nothing_where_it_points(tmp_path) -> None:
    """The other direction: nothing called `passwd` appears anywhere the test can see."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    attach(client, name=TRAVERSING_NAME)
    assert [path for path in tmp_path.rglob("*") if path.name == TRAVERSAL_TARGET] == []


def test_the_traversing_name_is_still_kept_as_metadata(tmp_path) -> None:
    """Non-vacuity: a route that dropped the name entirely would pass the two above."""
    client, registry, _ = a_run_to_attach_to(tmp_path)
    attach(client, name=TRAVERSING_NAME)
    assert stored_uploads(registry)[0]["name"] == TRAVERSING_NAME


def test_the_bytes_of_one_attachment_are_the_bytes_that_were_sent(tmp_path) -> None:
    """Non-vacuity for every naming check above: something was really written."""
    client, _, root = a_run_to_attach_to(tmp_path)
    attach(client, name=TRAVERSING_NAME)
    assert files_under(root)[0].read_bytes() == CONTENT


# --- what the client declared is not kept --------------------------------------

def test_the_type_the_client_declared_is_not_stored(tmp_path) -> None:
    """Attacker-chosen, and echoing it back is how a sniffed upload renders in this origin."""
    client, registry, _ = a_run_to_attach_to(tmp_path)
    attach(client, headers={"Content-Type": CLIENT_DECLARED_TYPE})
    held = stored_uploads(registry)[0]
    assert set(held) == EXPECTED_UPLOAD_KEYS
    assert CLIENT_DECLARED_TYPE not in str(held)


# --- the run the file belongs to -----------------------------------------------

def test_the_attachment_lands_on_the_runs_own_record(tmp_path) -> None:
    """Stored with the run rather than in a table of its own, which is why it is a column."""
    client, registry, _ = a_run_to_attach_to(tmp_path)
    answered = attached(client)
    assert stored_uploads(registry) == [answered]


def test_a_second_attachment_is_added_rather_than_replacing_the_first(tmp_path) -> None:
    """The record is frozen, so each attach is a new record one attachment longer."""
    client, registry, _ = a_run_to_attach_to(tmp_path)
    first = attached(client)
    attach(client, content=OTHER_CONTENT, name=OTHER_NAME)
    assert [held["name"] for held in stored_uploads(registry)] == [first["name"], OTHER_NAME]


def test_attaching_a_file_does_not_drop_the_runs_envelope(tmp_path) -> None:
    """A finished run's findings live in that column; saving the record must not clear it."""
    client, registry, _ = a_run_to_attach_to(tmp_path)
    attach(client)
    assert registry.store.get(THE_RUN)[1] is not None


def test_a_run_with_nothing_attached_carries_an_empty_list(tmp_path) -> None:
    """`[]` is a fact the endpoint can always establish, and never a gap."""
    _, registry, _ = a_run_to_attach_to(tmp_path)
    assert stored_uploads(registry) == []


# --- what it refuses before reading a byte --------------------------------------

def test_a_file_with_no_name_is_refused(tmp_path) -> None:
    """A name is display metadata, and an attachment nobody can identify is not evidence."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert attach(client, name="   ").status_code == REFUSED


def test_an_attachment_to_a_run_nobody_stored_is_refused(tmp_path) -> None:
    """A well-formed id no row carries: there is no run for these bytes to belong to."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert attach(client, run_id=NO_SUCH_RUN_ID).status_code == NO_SUCH_RUN


def test_a_malformed_run_id_is_refused_without_reaching_the_store(tmp_path) -> None:
    """"No run has that id" is true of a malformed one too, and it keeps it out of a path join."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert attach(client, run_id="../../etc").status_code == NO_SUCH_RUN


def test_a_refused_attachment_leaves_nothing_on_disk(tmp_path) -> None:
    """Refused before a byte is read, so there is no partial file to clean up later."""
    client, _, root = a_run_to_attach_to(tmp_path)
    attach(client, name="   ")
    attach(client, run_id=NO_SUCH_RUN_ID)
    assert files_under(root) == []

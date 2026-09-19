"""What a run left on disk, listed and bundled: only what is there, never the allowlist.

Two endpoints, one rule. `GET /api/artifacts/{run_id}` lists the files a run
really wrote and `.../artifacts.zip` archives them, and both must report the
directory rather than the sixteen names a run *could* leave. A page that offered
all sixteen links would offer some that answer 404, and an archive built from
the allowlist would either fail or ship empty entries. Absent is a fact about
the run -- a stage that could not run leaves its artifact absent -- and the panel
says it rather than discovering it on a click.

The tree is planted with a deliberate subset, so "lists what is present" cannot
be satisfied by listing everything. The archive's contents are read back with
`zipfile`, by name and by content, because an archive with the right names and
the wrong bytes is the failure a name check would miss.

The whole file skips without the server packages: with no fastapi there is
nothing to list.
"""

import io
import zipfile

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import httpx                                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

from artifacts.names import ALL_NAMES              # noqa: E402

from .download_fixtures import (                   # noqa: E402
    RUN_ID, SOME_NAMES, a_run_holding, contents_of)

DOWNLOAD = "/api/artifacts"
BUNDLE = "artifacts.zip"

# Which arm's files a listing is about. A `--compare-models` run wrote two sets
# into two directories, so a listing that named neither would describe one of
# them under a name that fits both -- and the archive would too.
LOCAL_ARM = "local"

OK = 200

DISPOSITION = "content-disposition"
ATTACHMENT = "attachment"
ZIP_TYPE = "application/zip"

# Three of the sixteen, so a listing that reported the allowlist would be wrong
# by thirteen names rather than by an edge case.
PRESENT = SOME_NAMES
ABSENT = tuple(name for name in ALL_NAMES if name not in PRESENT)

# The keys the listing carries.
LISTING_KEYS = {"run_id", "files", "bundle", "arm"}


def listing(client: TestClient, run_id: str = RUN_ID) -> dict:
    """Ask which of this run's files are on disk."""
    response = client.get(f"{DOWNLOAD}/{run_id}")
    assert response.status_code == OK, response.text
    return response.json()


def archive(client: TestClient, run_id: str = RUN_ID) -> httpx.Response:
    """Ask for every file this run wrote, in one reply."""
    return client.get(f"{DOWNLOAD}/{run_id}/{BUNDLE}")


# --- the listing ---------------------------------------------------------------

def test_the_listing_carries_the_run_its_files_and_the_bundles_name(tmp_path) -> None:
    """The page needs the archive's name too, rather than building the URL itself."""
    client, _, _ = a_run_holding(tmp_path, PRESENT)
    body = listing(client)
    assert set(body) == LISTING_KEYS
    assert (body["run_id"], body["bundle"]) == (RUN_ID, BUNDLE)


def test_the_listing_names_only_the_files_that_are_there(tmp_path) -> None:
    """Not the allowlist: thirteen of the sixteen were never written by this run."""
    client, _, _ = a_run_holding(tmp_path, PRESENT)
    assert [entry["name"] for entry in listing(client)["files"]] == [
        name for name in ALL_NAMES if name in PRESENT]


def test_the_listing_omits_every_file_the_run_did_not_write(tmp_path) -> None:
    """Stated as its own refusal, so the mutation this guards against is named."""
    client, _, _ = a_run_holding(tmp_path, PRESENT)
    listed = {entry["name"] for entry in listing(client)["files"]}
    assert listed.isdisjoint(ABSENT)


def test_the_listing_reports_each_files_real_size(tmp_path) -> None:
    """Read off the file rather than declared, so a truncated artifact is visible."""
    client, _, _ = a_run_holding(tmp_path, PRESENT)
    sizes = {entry["name"]: entry["bytes"] for entry in listing(client)["files"]}
    assert sizes == {name: len(contents_of(name).encode("utf-8")) for name in PRESENT}


def test_a_run_that_wrote_one_file_lists_one_file(tmp_path) -> None:
    """Non-vacuity: the checks above would pass over a listing that named everything."""
    client, _, _ = a_run_holding(tmp_path, (PRESENT[0],))
    assert [entry["name"] for entry in listing(client)["files"]] == [PRESENT[0]]


# --- the archive ---------------------------------------------------------------

def test_the_archive_holds_exactly_the_files_that_are_there(tmp_path) -> None:
    """Built from the directory, not from the allowlist: an absent artifact is not an entry."""
    client, _, _ = a_run_holding(tmp_path, PRESENT)
    with zipfile.ZipFile(io.BytesIO(archive(client).content)) as bundled:
        assert sorted(bundled.namelist()) == sorted(PRESENT)


def test_every_entry_in_the_archive_is_the_file_it_names(tmp_path) -> None:
    """The names being right is not the archive being right; the bytes are read back."""
    client, _, _ = a_run_holding(tmp_path, PRESENT)
    with zipfile.ZipFile(io.BytesIO(archive(client).content)) as bundled:
        held = {name: bundled.read(name).decode("utf-8") for name in bundled.namelist()}
    assert held == {name: contents_of(name) for name in PRESENT}


def test_the_archive_is_a_zip_and_an_attachment(tmp_path) -> None:
    """The same rule as every other download: saved, never rendered in this origin."""
    client, _, _ = a_run_holding(tmp_path, PRESENT)
    response = archive(client)
    assert response.status_code == OK
    assert response.headers["content-type"] == ZIP_TYPE
    assert ATTACHMENT in response.headers[DISPOSITION]


def test_the_archive_is_named_after_the_directory_it_came_from(tmp_path) -> None:
    """Fifty downloads called `artifacts.zip` are fifty files a reader cannot tell apart."""
    client, _, directory = a_run_holding(tmp_path, PRESENT)
    assert (f'filename="{directory.name}-{LOCAL_ARM}-{BUNDLE}"'
            in archive(client).headers[DISPOSITION])


def test_an_archive_of_a_run_that_wrote_nothing_is_empty_rather_than_an_error(tmp_path) -> None:
    """A directory with no artifacts in it is a gap the page can show, not a 500."""
    client, _, _ = a_run_holding(tmp_path, ())
    with zipfile.ZipFile(io.BytesIO(archive(client).content)) as bundled:
        assert bundled.namelist() == []

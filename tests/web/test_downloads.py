"""One named artifact, as a download: which names are served, and how they are served.

**Every reply is an attachment, and that is a security property rather than a
convenience.** `report.html` is rendered from the audited repository's own
strings -- prompt text, file paths, finding titles -- and this server has one
origin with an API that clones anything it is asked to and has no
authentication. Served inline, that HTML would run as script in that origin.
`Content-Disposition: attachment` is what makes a download the only thing on
offer, so it is asserted on every name rather than on a representative one.

**The caller never names a path**, and the guard is doubled: the filename must
be one of the names `artifacts/names.py` owns, and the resolved path must sit
directly under the run's own directory. The second check is unreachable through
the first for an ordinary name, so the test that exercises it plants a
*symlink* called `findings.json` pointing outside the directory -- which is the
only shape that passes the allowlist and should still be refused.

Traversals are spelled percent-encoded, and the difference is the whole test:
httpx normalises `/../secret.txt` before it leaves the client, so a test written
that way would pass with the guard deleted.

The whole file skips without the server packages: with no fastapi there is
nothing serving files.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import httpx                                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

from artifacts.names import ALL_NAMES              # noqa: E402

from .download_fixtures import (                   # noqa: E402
    RUN_ID, SOME_NAMES, a_run_holding, contents_of)

DOWNLOAD = "/api/artifacts"

OK = 200
NOT_DOWNLOADABLE = 404

# The header that makes a reply a saved file rather than a rendered page.
DISPOSITION = "content-disposition"
ATTACHMENT = "attachment"

# The one name whose inline rendering would execute the audited repository's own
# strings in this server's origin. Named, so the reason is in the test.
RENDERED_FROM_THE_AUDITED_APP = "report.html"

# What each suffix must be served as, pinned here rather than imported: the
# point of the check is that the type is *told* by `downloads.py` and not read
# off the machine, and a check that imported that table would agree with itself.
EXPECTED_TYPES = {"findings.json": "application/json", "report.md": "text/markdown",
                  "report.html": "text/html"}

# A name no run writes, and a plausible one: the audited repository's own
# manifest. Planted inside the run's directory by the test that uses it, so the
# allowlist is the only guard that can refuse it.
NOT_AN_ARTIFACT = "requirements.txt"

# A file beside the run's directory, standing in for everything on this machine
# a URL must not reach. Written outside the tree the fixture plants.
OUTSIDE_NAME = "secret.txt"
OUTSIDE_TEXT = "not inside the run's directory, and not the endpoint's to serve"

# The three spellings a client will really transmit: the climb, an absolute
# path, and a doubly-encoded climb.
ESCAPING_NAMES = ("%2e%2e%2f" + OUTSIDE_NAME, "%2fetc%2fpasswd",
                  "%252e%252e%252f" + OUTSIDE_NAME)


def one_file(client: TestClient, name: str, run_id: str = RUN_ID) -> httpx.Response:
    """Ask for one named artifact of one run."""
    return client.get(f"{DOWNLOAD}/{run_id}/{name}")


# --- every name a run writes ---------------------------------------------------

@pytest.mark.parametrize("name", ALL_NAMES)
def test_every_file_a_run_writes_can_be_downloaded(tmp_path, name) -> None:
    """The allowlist is `ALL_NAMES`, so all sixteen are asked for rather than a sample."""
    client, _, _ = a_run_holding(tmp_path, (name,))
    response = one_file(client, name)
    assert response.status_code == OK
    assert response.text == contents_of(name)


@pytest.mark.parametrize("name", ALL_NAMES)
def test_every_download_is_an_attachment(tmp_path, name) -> None:
    """The security property: inline HTML would run the audited app's strings here."""
    client, _, _ = a_run_holding(tmp_path, (name,))
    assert ATTACHMENT in one_file(client, name).headers[DISPOSITION]


@pytest.mark.parametrize("name", ALL_NAMES)
def test_every_download_names_the_file_it_is(tmp_path, name) -> None:
    """A browser saves what the header says, so the header says the artifact's own name."""
    client, _, _ = a_run_holding(tmp_path, (name,))
    assert f'filename="{name}"' in one_file(client, name).headers[DISPOSITION]


@pytest.mark.parametrize("name", SOME_NAMES)
def test_the_content_type_is_told_rather_than_guessed(tmp_path, name) -> None:
    """`mimetypes` varies by machine, and a wrong type on a download is a renamed file."""
    client, _, _ = a_run_holding(tmp_path, (name,))
    assert EXPECTED_TYPES[name] in one_file(client, name).headers["content-type"]


def test_the_html_report_is_typed_as_html_and_still_an_attachment(tmp_path) -> None:
    """The pair that matters: the type is honest and the disposition is what protects."""
    client, _, _ = a_run_holding(tmp_path, (RENDERED_FROM_THE_AUDITED_APP,))
    response = one_file(client, RENDERED_FROM_THE_AUDITED_APP)
    assert "text/html" in response.headers["content-type"]
    assert ATTACHMENT in response.headers[DISPOSITION]


# --- a name the run did not write ----------------------------------------------

def test_a_name_no_run_writes_is_refused_even_when_the_file_is_there(tmp_path) -> None:
    """The allowlist, and nothing else, is what refuses this one.

    The file is *planted in the run's own directory* first, so `is_file()` is
    true and the containment check is satisfied. Asked for a name that simply
    was not written, every guard refuses for a different reason and the test
    would pass with the allowlist deleted -- measured, by deleting it.
    """
    client, _, directory = a_run_holding(tmp_path, SOME_NAMES)
    (directory / NOT_AN_ARTIFACT).write_text("langchain==0.2.0\n", encoding="utf-8")
    response = one_file(client, NOT_AN_ARTIFACT)
    assert response.status_code == NOT_DOWNLOADABLE
    assert response.json()["detail"] == f"{NOT_AN_ARTIFACT!r} is not one of the files a run writes"


def test_an_allowlisted_name_the_run_did_not_write_is_refused(tmp_path) -> None:
    """Absent is a fact about the run: a stage that could not run leaves no file."""
    client, _, _ = a_run_holding(tmp_path, (SOME_NAMES[0],))
    response = one_file(client, SOME_NAMES[1])
    assert response.status_code == NOT_DOWNLOADABLE
    assert "rather than empty" in response.json()["detail"]


# --- the climb out of the run's directory --------------------------------------

@pytest.mark.parametrize("escaping", ESCAPING_NAMES)
def test_a_path_that_climbs_out_of_the_run_is_refused(tmp_path, escaping) -> None:
    """Sent encoded, so the handler really receives the climb rather than a normalised path."""
    (tmp_path / OUTSIDE_NAME).write_text(OUTSIDE_TEXT, encoding="utf-8")
    client, _, _ = a_run_holding(tmp_path, SOME_NAMES)
    response = one_file(client, escaping)
    assert response.status_code == NOT_DOWNLOADABLE
    assert OUTSIDE_TEXT not in response.text


def test_the_file_the_climb_asked_for_was_really_there(tmp_path) -> None:
    """Non-vacuity: the refusals above are about the guard, not about a missing file."""
    (tmp_path / OUTSIDE_NAME).write_text(OUTSIDE_TEXT, encoding="utf-8")
    a_run_holding(tmp_path, SOME_NAMES)
    assert (tmp_path / OUTSIDE_NAME).read_text(encoding="utf-8") == OUTSIDE_TEXT


def test_an_allowlisted_name_that_is_a_link_out_of_the_directory_is_refused(tmp_path) -> None:
    """The containment check, which the allowlist cannot reach: a symlink passes the name test."""
    outside = tmp_path / OUTSIDE_NAME
    outside.write_text(OUTSIDE_TEXT, encoding="utf-8")
    client, _, directory = a_run_holding(tmp_path, (SOME_NAMES[1],))
    (directory / SOME_NAMES[0]).symlink_to(outside)
    response = one_file(client, SOME_NAMES[0])
    assert response.status_code == NOT_DOWNLOADABLE
    assert OUTSIDE_TEXT not in response.text

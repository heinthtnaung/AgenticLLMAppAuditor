"""Where the bytes go is one argument, and nothing else can move them.

`register(app, store, upload_dir)` resolves the directory once and closes it
over both routes. It used to be a module constant that both routes read, and the
difference is not tidiness:

- **A module constant is a second thing a caller has to remember.** The store was
  already an argument, so redirecting a test's run history and redirecting its
  attachments were two different moves -- and a test that made only the first
  wrote attacker-shaped bytes into the checkout. It stayed out today by luck:
  `tests/web/__init__.py` happens to rebind `STORE_DIR` before `uploads` is first
  imported, so the constant computed from it landed in a temporary directory.
  Luck is not a guard, and a rebound constant is not something a test can be
  asked to prove anything about.
- **Two routes reading one constant agreed by construction; two closures do
  not.** `attach` writes and `one_upload` reads, and a change that moved one and
  not the other would store a file the same server could not find. So the pair is
  driven end to end here, against a directory neither of them defaults to.

Every assertion below is **before and after**, never "the default does not
exist": this folder shares one temporary store directory across its whole
module, so a test that asserted absence would depend on which test ran first.
What is asserted is that a redirected application adds nothing there, which is
true whatever ran before it.

The whole file skips without the server packages: with no fastapi there is
nothing to register.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from pathlib import Path                           # noqa: E402

import uploads                                     # noqa: E402

from .upload_fixtures import (                     # noqa: E402
    CONTENT, RUN_ID, a_run_to_attach_to, attach, files_under)

CREATED = 201
OK = 200

# Two directories neither route defaults to, so "the argument decided" has
# something to be wrong about. The second is for the pair of applications that
# must not see each other's files.
ELSEWHERE = "somewhere-else"
A_SECOND_PLACE = "a-second-place"

# What one attach leaves behind: the run's own directory, holding one file.
ONE_FILE = 1


def default_contents() -> list[Path]:
    """Everything under the module's default directory right now, or nothing."""
    return files_under(uploads.DEFAULT_UPLOAD_DIR)


def serve(client, upload_id: str, run_id: str = RUN_ID):
    """Ask for one attached file back through the same application that took it."""
    return client.get(f"/api/runs/{run_id}/uploads/{upload_id}")


# --- the argument is what decides ------------------------------------------------

def test_an_attachment_lands_in_the_directory_registration_named(tmp_path) -> None:
    """The plain claim: hand in a directory and the bytes are in it."""
    named = tmp_path / ELSEWHERE
    client, _, _ = a_run_to_attach_to(tmp_path, named)
    answered = attach(client).json()
    assert [path.name for path in files_under(named)] == [answered["upload_id"]]


def test_a_redirected_application_writes_nothing_where_it_would_have(tmp_path) -> None:
    """The hazard, said as a measurement: one argument is now the only thing to move.

    A test that forgot used to write into the checkout. There is nothing left to
    forget -- the directory is not optional in any caller that passes one -- and
    this is what says so rather than the docstring above saying it.
    """
    before = default_contents()
    client, _, _ = a_run_to_attach_to(tmp_path, tmp_path / ELSEWHERE)
    assert attach(client).status_code == CREATED
    assert default_contents() == before


def test_the_default_is_used_when_registration_names_nothing(tmp_path) -> None:
    """Non-vacuity for the test above: the default is real, and would have been used.

    Without this, "nothing landed in the default" would be satisfied by a
    default that no code path can reach at all.
    """
    before = default_contents()
    client, _, _ = a_run_to_attach_to(tmp_path, uploads.DEFAULT_UPLOAD_DIR)
    answered = attach(client).json()
    added = [path for path in default_contents() if path not in before]
    assert [path.name for path in added] == [answered["upload_id"]]


# --- both routes were told the same thing ------------------------------------------

def test_the_route_that_serves_reads_where_the_route_that_writes_wrote(tmp_path) -> None:
    """Two closures rather than one constant, so the pair no longer agrees by construction."""
    client, _, named = a_run_to_attach_to(tmp_path, tmp_path / ELSEWHERE)
    answered = attach(client).json()
    served = serve(client, answered["upload_id"])
    assert served.status_code == OK
    assert served.content == CONTENT
    assert files_under(named)[0].read_bytes() == CONTENT


def test_neither_route_falls_back_to_the_default_halfway(tmp_path) -> None:
    """The failure a single moved closure would produce: stored, and then not findable."""
    before = default_contents()
    client, _, _ = a_run_to_attach_to(tmp_path, tmp_path / ELSEWHERE)
    answered = attach(client).json()
    assert serve(client, answered["upload_id"]).status_code == OK
    assert default_contents() == before


def test_two_applications_over_two_directories_hold_their_own_files(tmp_path) -> None:
    """Impossible to state while the directory was a module constant: there was only one.

    Each application has its own store as well, so this is the pair of arguments
    moving together -- which is the whole reason the second one became an
    argument.
    """
    first, _, one = a_run_to_attach_to(tmp_path / "first", tmp_path / ELSEWHERE)
    second, _, other = a_run_to_attach_to(tmp_path / "second", tmp_path / A_SECOND_PLACE)
    attach(first)
    attach(second)
    assert len(files_under(one)) == len(files_under(other)) == ONE_FILE
    assert files_under(one) != files_under(other)


def test_a_run_of_one_application_is_not_a_run_of_the_other(tmp_path) -> None:
    """Non-vacuity for the isolation above: the two really are separate servers."""
    first, _, _ = a_run_to_attach_to(tmp_path / "first", tmp_path / ELSEWHERE)
    second, _, _ = a_run_to_attach_to(tmp_path / "second", tmp_path / A_SECOND_PLACE)
    answered = attach(first).json()
    assert serve(first, answered["upload_id"]).status_code == OK
    assert serve(second, answered["upload_id"]).status_code != OK


# --- and the default is a default --------------------------------------------------

def test_the_module_publishes_a_default_and_not_a_destination() -> None:
    """The rename carries the meaning: nothing reads this except `register`'s fallback."""
    assert not hasattr(uploads, "UPLOAD_DIR")
    assert isinstance(uploads.DEFAULT_UPLOAD_DIR, Path)


def test_registration_is_where_the_directory_is_resolved() -> None:
    """A caller may hand one in, and the parameter is optional so `api.py` need not."""
    assert "upload_dir" in uploads.register.__annotations__

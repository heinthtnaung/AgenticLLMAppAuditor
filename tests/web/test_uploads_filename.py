"""The display name in `Content-Disposition`: the one client string that reaches a header.

Split from `test_uploads_serving.py`, which is about *how* a file comes back --
the type, the sniffing, the attachment, the four ways there is nothing to serve.
This is about the one value in that reply which the client chose. Three kinds of
character are removed from it, and they are not there for the same reason:

- **Quotes** would close the header's quoted string early and **control
  characters** would start a header of their own. Both are exercised in one
  name, and both are the header staying well-formed. This is the half that is a
  vulnerability.
- **Path separators** are none of that. A recipient discards path information,
  so `filename="../../../etc/passwd"` was never a traversal and the file on disk
  was never named by the client -- `test_uploads_attach.py` holds that. They are
  removed because a filename that still *reads* like a path, in the one header
  that carries one, is worth not sending.

**The fallback is what the second one turned up.** `"///"` is not a blank name,
so the attach route accepts it; once the separators are gone there is nothing
left, and the header used to carry `filename=""`. It says `attachment` now,
which is a name a person can act on.

Every expectation here is a pinned literal rather than a call to the rule: what
the header carries is the subject, so deriving it would be the rule agreeing with
itself. Two tests are the non-vacuity pair that keeps the stripping apart from
throwing the name away.

**The length cap is applied twice, and the last test has to bypass the endpoint
to reach the second one.** `attach` stores `name[:MAX_UPLOAD_NAME_LENGTH]`, so a
name posted over the cap is already short by the time the header is built -- and
a test through the endpoint alone would pass with the cap in `_safe` deleted.
The second one is there for a writer that did not go through the route, exactly
as the store's `CHECK` constraints are there for a writer that did not go
through `RunRecord`, so the test bypasses the route in the same way and for the
same reason: a second line of defence cannot be tested through the first.

The whole file skips without the server packages: with no fastapi there is
nothing serving files.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import uploads                                     # noqa: E402

from dataclasses import replace                    # noqa: E402

from .upload_fixtures import (                     # noqa: E402
    DISPLAY_NAME, RUN_ID, a_run_to_attach_to, attach, stored_uploads)

CREATED = 201
DISPOSITION = "content-disposition"

# A name carrying both things that would break the header: a quote, which would
# close the quoted string early, and a CRLF, which would start a header.
INJECTING_NAME = 'he said "hi"\r\nX-Injected: yes'
INJECTED_HEADER = "x-injected"
RECOGNISABLE_PART = "he said"

# A name that is a path, and what is left of it once the separators are gone.
TRAVERSING_NAME = "../../../etc/passwd"
STRIPPED_TRAVERSAL = "......etcpasswd"

# The part of a path a reader actually recognises, so "separators removed" is
# told apart from "name thrown away".
TRAVERSAL_TAIL = "passwd"

# The other separator, which a name from a Windows client really carries.
WINDOWS_NAME = r"C:\Users\me\evidence.txt"
STRIPPED_WINDOWS = "C:Usersmeevidence.txt"

# A name that is nothing but separators. Not blank, so it is accepted -- and
# empty once they are removed, which used to be served as `filename=""`.
ONLY_SEPARATORS = "///"
FALLBACK_NAME = "attachment"

# What no offered filename may contain. Looked for in the filename alone: the
# header's own `attachment; ` shares a word with the fallback above, so a test
# over the whole header would be reading the wrong thing.
SEPARATORS = ("/", "\\")

# A name longer than the cap, to show the stored one is cut rather than refused
# -- a display string is not worth refusing evidence over.
OVERLONG_NAME = "n" * 500


def attached(client, name: str) -> dict:
    """Post one file under a given name and return the record the endpoint answered with."""
    response = attach(client, name=name)
    assert response.status_code == CREATED, response.text
    return response.json()


def disposition_for(client, name: str) -> str:
    """The whole `Content-Disposition` header a file attached under one name comes back with."""
    answered = attached(client, name)
    return client.get(
        f"/api/runs/{RUN_ID}/uploads/{answered['upload_id']}").headers[DISPOSITION]


def filename_offered(client, name: str) -> str:
    """Just the filename that header offers, without the disposition type in front of it."""
    return disposition_for(client, name).split('filename="', 1)[1].rstrip('"')


# --- the header stays well-formed --------------------------------------------------

def test_a_name_carrying_a_quote_and_a_newline_injects_neither(tmp_path) -> None:
    """A quote would close the header's string early; a CRLF would start a header."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    answered = attached(client, INJECTING_NAME)
    response = client.get(f"/api/runs/{RUN_ID}/uploads/{answered['upload_id']}")
    assert INJECTED_HEADER not in response.headers
    assert '"hi"' not in response.headers[DISPOSITION]
    assert "\n" not in response.headers[DISPOSITION]


def test_that_name_is_still_recognisable_afterwards(tmp_path) -> None:
    """Non-vacuity: a header that dropped the name entirely would pass the test above."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert RECOGNISABLE_PART in disposition_for(client, INJECTING_NAME)


# --- and it does not read like a path ------------------------------------------------

def test_a_name_that_is_a_path_is_offered_without_its_separators(tmp_path) -> None:
    """A recipient discards path information anyway; a filename that reads like one is not sent."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert filename_offered(client, TRAVERSING_NAME) == STRIPPED_TRAVERSAL


def test_a_backslash_is_a_separator_too(tmp_path) -> None:
    """The other spelling, which a name from a Windows client really carries."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert filename_offered(client, WINDOWS_NAME) == STRIPPED_WINDOWS


def test_no_offered_filename_carries_a_separator(tmp_path) -> None:
    """Said as the rule rather than as two examples of it."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    for name in (TRAVERSING_NAME, WINDOWS_NAME, ONLY_SEPARATORS):
        offered = filename_offered(client, name)
        assert not any(separator in offered for separator in SEPARATORS), name


# --- and it is never empty -------------------------------------------------------------

def test_a_name_that_is_only_separators_falls_back_to_a_usable_one(tmp_path) -> None:
    """It is not a blank name, so it is accepted -- and `filename=""` is not a name."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert filename_offered(client, ONLY_SEPARATORS) == FALLBACK_NAME


def test_stripping_a_path_is_not_the_same_as_falling_back(tmp_path) -> None:
    """The non-vacuity pair: an emptied name would have no separators in it either.

    Without this, "no separators" and "never empty" would both be satisfied by a
    rule that answered `attachment` for every name it was given.
    """
    assert TRAVERSAL_TAIL in STRIPPED_TRAVERSAL
    assert STRIPPED_TRAVERSAL != FALLBACK_NAME


# --- and it is the name that was given -------------------------------------------------

def test_an_ordinary_name_is_offered_exactly_as_it_was_given(tmp_path) -> None:
    """The name is display metadata, and this is the one place it reaches a header.

    The non-vacuity guard for every rule above as well: what comes out is what
    went in, so each is about those characters and not about names in general.
    """
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert filename_offered(client, DISPLAY_NAME) == DISPLAY_NAME


def test_an_overlong_name_is_cut_rather_than_refused(tmp_path) -> None:
    """A display string is not worth refusing evidence over, so it is bounded instead."""
    client, _, _ = a_run_to_attach_to(tmp_path)
    assert len(attached(client, OVERLONG_NAME)["name"]) == uploads.MAX_UPLOAD_NAME_LENGTH


def test_a_record_holding_an_overlong_name_is_still_offered_a_bounded_one(tmp_path) -> None:
    """The second cap, reached by storing the record the way the route never would.

    The route truncates on the way in, so through it this name is already short
    and the cap in `_safe` is unreachable. It is the second line of defence for
    a writer that did not go through the route -- and a second line of defence
    cannot be tested through the first, which is why the row is written here
    directly.
    """
    client, registry, _ = a_run_to_attach_to(tmp_path)
    answered = attached(client, DISPLAY_NAME)
    record, envelope = registry.store.get(RUN_ID)
    registry.store.save(replace(record, uploads=[
        {**answered, "name": OVERLONG_NAME}]), envelope)
    offered = client.get(
        f"/api/runs/{RUN_ID}/uploads/{answered['upload_id']}").headers[DISPOSITION]
    assert len(offered.split('filename="', 1)[1].rstrip('"')) == uploads.MAX_UPLOAD_NAME_LENGTH


def test_that_record_really_carried_the_overlong_name(tmp_path) -> None:
    """Non-vacuity: a store that refused the row would make the bound above trivial."""
    client, registry, _ = a_run_to_attach_to(tmp_path)
    answered = attached(client, DISPLAY_NAME)
    record, envelope = registry.store.get(RUN_ID)
    registry.store.save(replace(record, uploads=[
        {**answered, "name": OVERLONG_NAME}]), envelope)
    assert stored_uploads(registry)[0]["name"] == OVERLONG_NAME

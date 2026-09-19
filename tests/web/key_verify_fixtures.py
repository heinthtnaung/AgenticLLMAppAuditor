"""Driving `POST /api/keys/{app}/verify`, and the names its two tests share.

Split from `key_fixtures.py` rather than added to it: that file is already at
the length rule 18 asks about, and everything here is about one route it knows
nothing of. The draft, the tree its anchors quote and the client all still come
from there, so the two files describe one drafted key.

**Nothing here writes to `grading_keys/drafts/`.** The redirection is
`key_fixtures.client_over`, which rebinds `key_routes.DRAFTED_KEYS_DIR` -- and
it has to be that name, not `key_drafting`'s copy, for the reason that file
states. A test that got it wrong would record a verification claim on a real
draft in the checkout.

The clock is a seam here. `key_verify_route` calls `run_record.today` by name,
so a test can point that at a fixed date and assert the stamp came from the
server's clock rather than from the request -- which is the one property of
`verified_date` that matters.
"""

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import key_verify_route

from .key_fixtures import KEYS_ENDPOINT, OK

# An ordinary name, held to the same rules as the auditor of a run: this server
# has no authentication, so it is a claim about who checked the key.
CHECKED_BY = "Quokka Reviewer"

# The same name as a browser text field leaves it. Spaces only, and deliberately
# not a tab: `auditor_refusals` tests `isprintable()` *before* stripping, so a
# tab-padded name is a control character and is refused -- which is the rule the
# auditor name is already held to and is asserted as a refusal, not worked
# around here.
PADDED_CHECKED_BY = f"  {CHECKED_BY}  "

# A second person, so "already verified" is refused by the first name and not by
# any name at all.
SECOND_CHECKER = "Someone Else Entirely"

# A fixed date for the server's clock. Deliberately not today: a stamp read off
# the body would have to be *this* to pass, and a real clock never answers it.
FIXED_DATE = "2026-03-04"

# What a client would send to backdate a claim, and what it must not become.
BACKDATED = "2019-01-01"


def verify_path(endpoint: str = KEYS_ENDPOINT) -> str:
    """Where a claim that a human checked one draft is posted.

    Under the run, beside the two routes that read and correct it: a claim is
    about the key one run drafted, and the app it names is read off that run.
    """
    return f"{endpoint}/verify"


def claim(client: TestClient, verified_by: str, endpoint: str = KEYS_ENDPOINT,
          **extra_body) -> httpx.Response:
    """Post one verification claim, whatever the answer -- the refusals are a subject too.

    `extra_body` is how a client that sends more than the route asks for is
    driven: a `verified_date` in the body is the case the server's own stamp
    exists to defeat.
    """
    return client.post(verify_path(endpoint),
                       json={"verified_by": verified_by, **extra_body})


def claimed(client: TestClient, verified_by: str = CHECKED_BY,
            endpoint: str = KEYS_ENDPOINT, **extra_body) -> dict:
    """Post one claim and insist it was accepted, returning the reply body."""
    response = claim(client, verified_by, endpoint, **extra_body)
    assert response.status_code == OK, response.text
    return response.json()


def freeze_clock(monkeypatch: pytest.MonkeyPatch, when: str = FIXED_DATE) -> None:
    """Point the route's clock at a fixed date, so the stamp has a known value.

    `key_verify_route` binds `today` with `from run_record import today`, so
    this is the name it actually calls. Patching `run_record.today` would leave
    the route reading its own reference and the test asserting nothing.
    """
    monkeypatch.setattr(key_verify_route, "today", lambda: when)


def verified_fields(key: dict) -> tuple:
    """The three fields a recorded check writes, as one tuple to compare."""
    return key["verified"], key["verified_by"], key["verified_date"]


def drafts_listing(drafts: Path) -> list[str]:
    """Every file in the drafts folder, so a route that wrote a fourth is caught."""
    return sorted(path.name for path in drafts.iterdir())

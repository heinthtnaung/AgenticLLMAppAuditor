"""Every claim the verify route turns down: the name on it, and a second one.

`verified_by` is free text on an endpoint with **no authentication**, so it is a
claim about who checked a key and not proof that they did. It is held to exactly
the rules an auditor's name is held to, by calling `run_record.auditor_refusals`
-- one spelling, reused. The route wraps that list in its own opening sentence,
because `auditor_refusals` says "an audit records who asked for it" and this is
not an audit; the *rules* are not restated, and the tests below assert that by
comparing what came back against what the function itself says.

**A second claim is refused rather than overwriting the first.** Withdrawing a
recorded check is a hand edit of the file, deliberately: a route that let one
name replace another would make the field say who claimed it last rather than
who checked it.

Which draft the route may touch at all, and which folder it may write into, is
`test_key_verify_confinement.py`. Two files because they are two claims: this
one is about the name on the claim, that one about where the claim can land.

Nothing here writes to the checkout's own `grading_keys/drafts/`.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from run_record import MAX_AUDITOR_LENGTH, auditor_refusals   # noqa: E402

from .key_fixtures import (                                   # noqa: E402
    APP, REFUSED, key_on_disk, planted_client)
from .key_verify_fixtures import (                            # noqa: E402
    CHECKED_BY, SECOND_CHECKER, claim, claimed, verify_path)

# The opening the route puts in front of `auditor_refusals`' own sentences. Its
# subject is a check, not an audit, which is why it is not the function's wording.
REFUSAL_OPENING = "a recorded check names who made it: "

# The four names the shared rules refuse, one per reason. The blank and the
# whitespace-only one meet the same `.strip()`.
BLANK_NAME = ""
WHITESPACE_NAME = "   \t "
OVER_LONG_NAME = "a" * (MAX_AUDITOR_LENGTH + 1)
CONTROL_CHARACTER_NAME = "Quokka\nReviewer"
REFUSED_NAMES = (BLANK_NAME, WHITESPACE_NAME, OVER_LONG_NAME, CONTROL_CHARACTER_NAME)


# --- the name is a claim, held to the auditor's rules --------------------------

def test_an_ordinary_name_is_accepted(monkeypatch, tmp_path) -> None:
    """Non-vacuity for every refusal below: the rules are about the name, not the route."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    assert claimed(client, CHECKED_BY)["key"]["verified_by"] == CHECKED_BY


@pytest.mark.parametrize("name", REFUSED_NAMES)
def test_a_name_the_shared_rules_refuse_is_a_four_hundred(
        monkeypatch, tmp_path, name: str) -> None:
    """Each reason, not one of them: a rule applied in name only is not applied."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    assert claim(client, name).status_code == REFUSED


@pytest.mark.parametrize("name", REFUSED_NAMES)
def test_the_refusal_is_the_shared_rules_own_sentence(
        monkeypatch, tmp_path, name: str) -> None:
    """The join, asserted rather than described: no second copy of what "printable" means.

    The route frames the list -- its subject is a check and not an audit -- but
    the sentences inside it are `auditor_refusals`' own. Written twice, the two
    had already grown two different ideas of what a name may contain.
    """
    client, _drafts = planted_client(monkeypatch, tmp_path)
    detail = claim(client, name).json()["detail"]
    assert detail == REFUSAL_OPENING + "; ".join(auditor_refusals(name))


def test_a_name_at_the_cap_is_accepted(monkeypatch, tmp_path) -> None:
    """The boundary: the rule is about the length, not about a name being long."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    at_the_cap = "a" * MAX_AUDITOR_LENGTH
    assert claimed(client, at_the_cap)["key"]["verified_by"] == at_the_cap


def test_a_body_with_no_name_field_at_all_is_refused(monkeypatch, tmp_path) -> None:
    """`verified_by` defaults to empty, so an old page posting `{}` is refused, not accepted."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    response = client.post(verify_path(), json={})
    assert response.status_code == REFUSED
    assert response.json()["detail"].startswith(REFUSAL_OPENING)


@pytest.mark.parametrize("name", REFUSED_NAMES)
def test_a_refused_name_records_nothing(monkeypatch, tmp_path, name: str) -> None:
    """A refusal that had already written would be worse than no rule at all."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    claim(client, name)
    assert key_on_disk(drafts)["verified"] is False


# --- one check per draft -------------------------------------------------------

def test_a_second_claim_is_refused(monkeypatch, tmp_path) -> None:
    """The field says who checked the key, not who claimed it most recently."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    claimed(client, CHECKED_BY)
    assert claim(client, SECOND_CHECKER).status_code == REFUSED


def test_the_second_claim_is_refused_by_naming_the_first(monkeypatch, tmp_path) -> None:
    """Whoever is refused needs to know who to go and ask, so the message names them."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    claimed(client, CHECKED_BY)
    detail = claim(client, SECOND_CHECKER).json()["detail"]
    assert CHECKED_BY in detail
    assert APP in detail


def test_the_second_claim_leaves_the_first_exactly_as_it_was(
        monkeypatch, tmp_path) -> None:
    """The refusal's point: a name that replaced another silently would be the defect."""
    client, drafts = planted_client(monkeypatch, tmp_path)
    claimed(client, CHECKED_BY)
    after_first = key_on_disk(drafts)
    claim(client, SECOND_CHECKER)
    assert key_on_disk(drafts) == after_first
    assert key_on_disk(drafts)["verified_by"] == CHECKED_BY


def test_a_second_claim_under_a_bad_name_is_still_refused(monkeypatch, tmp_path) -> None:
    """Both guards on one request: the name is checked first, so that is the sentence."""
    client, _drafts = planted_client(monkeypatch, tmp_path)
    claimed(client, CHECKED_BY)
    detail = claim(client, BLANK_NAME).json()["detail"]
    assert detail.startswith(REFUSAL_OPENING)

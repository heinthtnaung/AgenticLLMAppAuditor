"""What the wrapper answers when the audit will not run, now that it answers first.

`main.EXPECTED_FAILURES` is the tool's own list of conditions a person can fix
-- an unreachable URL, a name a grading key owns, a tree the fetcher refuses --
and the command line already prints each one as a sentence. A traceback would
throw that sentence away and replace it with "Internal Server Error", so every
member of that tuple is exercised here, read out of `main` rather than
transcribed: a sixth class added there is covered the moment it lands.

**The claim survives the endpoint becoming a job; its location moved.** A tool
refusal is raised *after* the 202, so it is no longer a 4xx at all: it lands as
`status: failed` with the same sentence in `error`. What must still be true is
that the sentence reaches the page and that a refusal is told apart from a
defect -- the first by `error`, the second by the class name the message carries.
The `400` that remains is the request rules only, checked before any row is
written, and the last three tests are those.

`main.run` is replaced throughout this file. What is under test is the
wrapper's translation of an outcome, and a real audit would only make the five
error classes harder to produce. The audit itself is driven end to end in
`test_api_audit.py`.

The other refusal, a second audit while one is running, is
`test_api_single_run_lock.py`; the registry's own half of it is
`test_run_slot.py`.

The whole file skips without the server packages installed: with no fastapi
there is no endpoint to refuse anything.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

import main                                        # noqa: E402
from run_record import FAILED, FINISHED            # noqa: E402
from run_routes import REFUSED                     # noqa: E402

from .api_stubs import audit_and_poll, client_over, post_an_audit   # noqa: E402
from .audit_stub import (                          # noqa: E402
    URL, UNEXPECTED_ERROR, repositories, stub_the_audit, wait_for_the_worker)

# What the request rules answer with, read off the module that owns them rather
# than re-spelled: `run_routes.py` states its own contract, and a test that
# copied the number would keep passing while the two disagreed. The literal is
# pinned once below, so importing it is not the constant agreeing with itself.
BAD_REQUEST = 400

# The answer none of these may give, and nobody's constant.
SERVER_ERROR = 500

# The message the tool writes, which the failed run must carry rather than replace.
TOOL_MESSAGE = "fetched/demo-app holds another repository; remove it to fetch this one"

# A body the request rules refuse before any audit is considered.
PATH_NOT_A_LINK = "/home/someone/private-repo"


@pytest.mark.parametrize("failure", main.EXPECTED_FAILURES)
def test_an_expected_failure_becomes_a_failed_run_and_not_a_server_error(
        monkeypatch, tmp_path, failure) -> None:
    """Every class the tool names as fixable comes back as a run that failed, never a 500."""
    stub_the_audit(monkeypatch, tmp_path, error=failure(TOOL_MESSAGE))
    client, _ = client_over(tmp_path)
    assert audit_and_poll(client)["status"] == FAILED


@pytest.mark.parametrize("failure", main.EXPECTED_FAILURES)
def test_an_expected_failure_carries_the_tools_own_message(
        monkeypatch, tmp_path, failure) -> None:
    """The sentence the CLI would have printed reaches the page, not "Internal Server Error"."""
    stub_the_audit(monkeypatch, tmp_path, error=failure(TOOL_MESSAGE))
    client, _ = client_over(tmp_path)
    assert audit_and_poll(client)["error"] == TOOL_MESSAGE


@pytest.mark.parametrize("failure", main.EXPECTED_FAILURES)
def test_the_request_that_refused_is_still_accepted_and_answered(
        monkeypatch, tmp_path, failure) -> None:
    """The protocol: a tool refusal is not an HTTP status any more, so the POST succeeds."""
    stub_the_audit(monkeypatch, tmp_path, error=failure(TOOL_MESSAGE))
    client, registry = client_over(tmp_path)
    assert post_an_audit(client).status_code < SERVER_ERROR
    # Waited for, always: the worker looks `main.run` up when it calls it, so a
    # thread still running when the stub is undone would start a real audit --
    # and a real audit of this URL would try to clone it.
    wait_for_the_worker(registry)


def test_the_list_of_expected_failures_is_the_tools_own_and_is_not_empty() -> None:
    """Guard: an emptied tuple would make all three sweeps above pass having run nothing."""
    assert len(main.EXPECTED_FAILURES) >= 5
    assert ValueError in main.EXPECTED_FAILURES


def test_a_failure_the_tool_does_not_expect_is_not_disguised_as_a_refusal(
        monkeypatch, tmp_path) -> None:
    """A defect must stay a defect: the failed run names the class rather than only a message."""
    stub_the_audit(monkeypatch, tmp_path, error=UNEXPECTED_ERROR("a bug, not a refusal"))
    client, _ = client_over(tmp_path)
    record = audit_and_poll(client)
    assert record["status"] == FAILED
    assert record["error"].startswith(f"{UNEXPECTED_ERROR.__name__}: ")


def test_an_audit_the_tool_does_not_refuse_finishes(monkeypatch, tmp_path) -> None:
    """Non-vacuity: the failures above are the stub refusing, not the wrapper failing."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    assert audit_and_poll(client)["status"] == FINISHED


# --- the request rules, which are still an HTTP status ------------------------

def test_the_refusal_answer_is_the_status_code_it_claims() -> None:
    """Pins the constant imported above, so every assertion using it means something."""
    assert REFUSED == BAD_REQUEST


def test_a_request_the_rules_refuse_never_reaches_the_audit(monkeypatch, tmp_path) -> None:
    """A filesystem path is refused before anything runs, so nothing is cloned or read."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    response = post_an_audit(client, PATH_NOT_A_LINK)
    assert response.status_code == REFUSED
    assert parsed == []
    assert registry.store.count() == 0


def test_a_refused_request_says_which_rule_refused_it(monkeypatch, tmp_path) -> None:
    """The reply carries the refusal `AuditRequest` wrote, so the page can show it."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    assert "https" in post_an_audit(client, PATH_NOT_A_LINK).json()["detail"]


def test_an_accepted_request_reaches_the_audit_with_the_url_it_named(monkeypatch,
                                                                     tmp_path) -> None:
    """Non-vacuity: the same post that is refused above runs when the rules allow it."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    audit_and_poll(client)
    assert repositories(parsed) == [URL]

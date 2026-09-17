"""The 409: what the endpoint answers while an audit is in flight, and after one ends.

The wrapper runs one audit at a time because two would race between the
"already fetched?" check and the clone, and would overwrite each other's
`artifacts/<app>/` mid-write. **Where that is decided moved**: it used to be a
module-level `api._running` lock held across the whole request, and it is now
`Registry.active_run_id`, a field set and cleared under a short-lived guard.
The 409 is unchanged, so this file is unchanged in what it claims and changed in
how it reaches it -- the run in flight is a real background run, held open by an
event, rather than a lock this test acquired by hand.

The registry's own half -- the slot being released on every path out, including
the store write that used to wedge it -- is `test_run_slot.py`. This file is
only what the endpoint answers, because a page shows a person a status code.

The whole file skips without the server packages installed: with no fastapi
there is no endpoint to refuse a second run.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from run_routes import ALREADY_RUNNING             # noqa: E402

from .api_stubs import ACCEPTED, audit_and_poll, client_over, post_an_audit   # noqa: E402
from .audit_stub import (                          # noqa: E402
    UNEXPECTED_ERROR, hold_the_audit, stub_the_audit, wait_for_the_worker)

# Read off the module that owns it rather than re-spelled: `run_routes.py`
# states its own contract, and a test that copied the number would keep passing
# while the two disagreed. The literal is pinned once below.
CONFLICT = 409

# The message a refused run carries, so the refusal path is a real refusal.
TOOL_MESSAGE = "fetched/demo-app holds another repository; remove it to fetch this one"


def test_the_conflict_answer_is_the_status_code_it_claims() -> None:
    """Pins the constant imported above, so every assertion using it means something."""
    assert ALREADY_RUNNING == CONFLICT


def test_a_second_audit_while_one_is_running_is_refused(monkeypatch, tmp_path) -> None:
    """One audit at a time, with a real run in flight rather than a lock taken by hand."""
    let_it_finish = hold_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    try:
        assert post_an_audit(client).status_code == ACCEPTED
        assert post_an_audit(client).status_code == ALREADY_RUNNING
    finally:
        let_it_finish.set()
        wait_for_the_worker(registry)


def test_the_refusal_of_a_second_audit_explains_itself(monkeypatch, tmp_path) -> None:
    """A 409 with no reason reads as a bug; this one says why it runs one at a time."""
    let_it_finish = hold_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    try:
        post_an_audit(client)
        assert "already running" in post_an_audit(client).json()["detail"]
    finally:
        let_it_finish.set()
        wait_for_the_worker(registry)


def test_the_refused_second_audit_leaves_no_row_behind(monkeypatch, tmp_path) -> None:
    """A run that was never accepted is not a run: the history must not show it."""
    let_it_finish = hold_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    try:
        post_an_audit(client)
        post_an_audit(client)
        assert registry.store.count() == 1
    finally:
        let_it_finish.set()
        wait_for_the_worker(registry)


def test_two_audits_one_after_the_other_both_run(monkeypatch, tmp_path) -> None:
    """The wrapper is single-file, not single-use, which is what makes the 409 a queue's job."""
    stub_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    audit_and_poll(client)
    audit_and_poll(client)
    assert registry.store.count() == 2


def test_an_audit_after_a_refused_run_is_not_refused_as_a_second_run(monkeypatch,
                                                                    tmp_path) -> None:
    """A failed run must not wedge the endpoint shut, which is what the `finally` is for."""
    stub_the_audit(monkeypatch, tmp_path, error=ValueError(TOOL_MESSAGE))
    client, registry = client_over(tmp_path)
    audit_and_poll(client)
    stub_the_audit(monkeypatch, tmp_path)
    assert post_an_audit(client).status_code == ACCEPTED
    # Waited for, always: the worker looks `main.run` up when it calls it, so a
    # thread still running when the stub is undone would start a real audit --
    # and a real audit of this URL would try to clone it.
    wait_for_the_worker(registry)


def test_an_audit_after_an_unexpected_failure_is_not_refused_as_a_second_run(
        monkeypatch, tmp_path) -> None:
    """Said as the user meets it: the next request is answered, not told one is running.

    The case a refusal cannot cover. A `ValueError` is translated on its way out
    of the worker; a `KeyError` is caught by the one broad `except` there is, and
    that is the shape that used to leave the guard held -- turning one bug into a
    server that answers 409 to everything until it is restarted.
    """
    stub_the_audit(monkeypatch, tmp_path, error=UNEXPECTED_ERROR("a bug, not a refusal"))
    client, registry = client_over(tmp_path)
    audit_and_poll(client)
    assert registry.active_run_id() is None
    stub_the_audit(monkeypatch, tmp_path)
    response = post_an_audit(client)
    assert response.status_code != ALREADY_RUNNING
    assert response.status_code == ACCEPTED
    wait_for_the_worker(registry)

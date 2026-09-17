"""The whole of the wedged-row fault, driven through the endpoint that was reachable.

Two layers each hold half of this and are tested apart -- the request rule in
`test_audit_request_option_values.py`, the worker's catch in
`test_run_jobs_worker_escape.py`. Neither of them is the sentence that matters,
which is about the server as a whole:

    an unauthenticated POST /api/audit could leave a run row saying `running`
    for ever, and `history_store._reconcile` only runs when the store is opened

So this file drives the real route over a real store, and **the assertion is
that no row exists at all** -- checked rather than inferred from the 400, since
a 400 answered *after* a row was written would be exactly as bad. `model: "-x"`
made `parse_args` print usage and call `sys.exit` in the worker thread;
`SystemExit` is a `BaseException`, so the thread died, the `finally` freed the
slot, and the row it had already written was never rewritten.

The last two tests are the consequence a user would have seen: the wrapper runs
one audit at a time, so a wedged row's run is the run that never ends -- and the
next legal request must still be accepted and still finish.

Skips whole without the server packages: with no fastapi there is no endpoint to
refuse anything. `main.run` is replaced throughout, so nothing here clones or
audits; the refused requests never reach it at all, which is asserted.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from audit_request import PASS_THROUGH_VALUES                # noqa: E402
from run_record import FINISHED, RUNNING                     # noqa: E402
from run_routes import REFUSED                               # noqa: E402

from .api_stubs import audit_and_poll, client_over, post_an_audit   # noqa: E402
from .audit_stub import URL, repositories, stub_the_audit    # noqa: E402

# The value that wedged a row, and a legal name for the same box.
OPTION_SHAPED = "-x"
A_PULLED_MODEL = "qwen2.5-coder:7b-instruct"

# What each value-carrying option must be posted with to be an otherwise legal
# request: a local model only counts if something would consult one, and a
# hosted model only under comparison. Keyed by the module's own map, so a third
# option added there arrives here with no entry and raises rather than passing.
LEGAL_BESIDE = {"model": {"semantic_probe": True},
                "cloud_model": {"compare_models": True}}
VALUE_FIELDS = tuple(PASS_THROUGH_VALUES)

# No row at all, which is the state a wedged `running` row is measured against.
NO_RUNS = 0
ONE_RUN = 1


def post_naming(client, field: str, value: str):
    """Post one audit whose value-carrying option holds `value`, whatever the answer."""
    return post_an_audit(client, **{field: value}, **LEGAL_BESIDE[field])


# --- the request that used to wedge a row ---------------------------------------

@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_the_endpoint_refuses_a_value_that_reads_as_an_option(monkeypatch, tmp_path,
                                                              field: str) -> None:
    """Both pass-through fields, over HTTP: a 400 before anything is accepted."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _registry = client_over(tmp_path)
    assert post_naming(client, field, OPTION_SHAPED).status_code == REFUSED


@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_that_request_leaves_no_run_row_behind_at_all(monkeypatch, tmp_path,
                                                      field: str) -> None:
    """The claim this file exists for, stated as the row that is not there.

    A refusal answered after the row was written would still leave `running`
    behind for ever, so the store is asked rather than the status code.
    """
    stub_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    post_naming(client, field, OPTION_SHAPED)
    assert registry.store.count() == NO_RUNS


@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_that_request_never_reaches_the_audit(monkeypatch, tmp_path,
                                              field: str) -> None:
    """Nothing was cloned, parsed or run: the rules answered before any of it."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    client, _registry = client_over(tmp_path)
    post_naming(client, field, OPTION_SHAPED)
    assert repositories(parsed) == []


@pytest.mark.parametrize("field", VALUE_FIELDS)
def test_the_reply_names_the_field_the_caller_has_to_fix(monkeypatch, tmp_path,
                                                         field: str) -> None:
    """The page shows `detail`, so a refusal that named neither box is a dead end."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _registry = client_over(tmp_path)
    assert field in post_naming(client, field, OPTION_SHAPED).json()["detail"]


# --- and the wrapper that must not be left holding anything ----------------------

def test_a_legal_model_name_through_the_same_endpoint_finishes(monkeypatch,
                                                               tmp_path) -> None:
    """Non-vacuity: the refusals above are the value, not the endpoint refusing everything."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    client, _registry = client_over(tmp_path)
    record = audit_and_poll(client, model=A_PULLED_MODEL, semantic_probe=True)
    assert record["status"] == FINISHED
    assert repositories(parsed) == [URL]


def test_a_refused_request_does_not_wedge_the_audit_after_it(monkeypatch,
                                                             tmp_path) -> None:
    """The consequence a user would have met: one audit at a time, and one row stuck.

    A run that never reaches a terminal status is the run in flight for ever, so
    the test that the fault is gone is that the *next* audit is accepted, runs,
    and leaves exactly one row -- not `running`.
    """
    stub_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    post_naming(client, "model", OPTION_SHAPED)
    record = audit_and_poll(client, model=A_PULLED_MODEL, semantic_probe=True)
    assert record["status"] != RUNNING
    assert registry.store.count() == ONE_RUN

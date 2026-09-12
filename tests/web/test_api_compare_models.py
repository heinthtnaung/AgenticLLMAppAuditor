"""Ticking "compare models" in a browser: the answer that used to be a 500.

`compare_run.run` returned `0` while `main.run` is annotated `-> dict`, so the
wrapper's `produced["app"]` raised and the page was told "Internal Server
Error". The order of events is what earns this its own file. By the time that
500 was rendered the run had finished, and finishing on this path means the
audited repository's own source -- prompt text, file paths, line numbers,
finding titles, code snippets -- had already been sent to a third party. A
failure placed after the irreversible part reports nothing a user can act on.

**The claim survives the endpoint becoming a job; its shape moved.** That
subscript now raises inside the worker, so the defect would land as
`status: failed` carrying `TypeError` rather than as a 500 -- still after the
upload, and still nothing a user can act on. So what is asserted is that the run
*finished*, with a result and no error, which is false in exactly the same cases
the old status check was.

Three tests hold the chain, one file each, and none of them is enough alone:
`tests/compare/test_compare_arms.py` runs the real thing and asserts what
`compare_run.run` returns, `tests/compare/test_compare_run_result.py` asserts
`main.run` hands that back unchanged, and this file asserts the wrapper turns it
into a finished run carrying the documented envelope.

Nothing here calls a model, opens a socket or clones anything: `main.run` is
replaced by the recorder in `audit_stub.py`, which answers with the shape the
real one answers with -- the LOCAL arm's result, because the hosted arm is the
comparison and is printed rather than returned. That is also why the flag is
asserted on the parsed command line rather than inferred: a stub that ran an
ordinary audit would pass every status check below while the checkbox did
nothing.

The whole file skips without the server packages: with no fastapi there is
no endpoint to post to.
"""

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from fastapi.testclient import TestClient          # noqa: E402

from run_record import FINISHED                    # noqa: E402
from run_routes import REFUSED                     # noqa: E402

from .api_stubs import audit_and_poll, client_over, post_an_audit   # noqa: E402
from .audit_stub import (                          # noqa: E402
    APP, RUN_SECONDS, artifacts_dir_for, stub_the_audit)

# The hosted model the page names, spelled the way OpenRouter spells one.
CLOUD_MODEL = "vendor/some-hosted-model"

# The seven keys the result carries, documents included: absent, they come back
# as None rather than as missing keys.
EXPECTED_RESULT_KEYS = {"schema_version", "app", "artifacts_dir", "seconds",
                        "advisories_read", "findings", "surfaces"}


def compare_through_the_endpoint(client: TestClient, cloud_model: str = "") -> dict:
    """Post one audit with model comparison ticked, and poll it to a finish."""
    return audit_and_poll(client, compare_models=True, cloud_model=cloud_model)


def test_a_comparison_finishes_rather_than_failing(monkeypatch, tmp_path) -> None:
    """The bug, stated as the run's own status: this used to be a 500 after the upload."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    record = compare_through_the_endpoint(client)
    assert record["status"] == FINISHED
    assert record["error"] is None


def test_a_comparison_answers_the_documented_envelope(monkeypatch, tmp_path) -> None:
    """The same seven keys an ordinary audit answers with: one path, one shape."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    assert set(compare_through_the_endpoint(client)["result"]) == EXPECTED_RESULT_KEYS


def test_the_reply_names_the_local_arms_artifacts_directory(monkeypatch, tmp_path) -> None:
    """`produced["artifacts"]` is the subscript that raised; the page gets the local arm."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    result = compare_through_the_endpoint(client)["result"]
    assert result["app"] == APP
    assert result["artifacts_dir"] == str(artifacts_dir_for(tmp_path))
    assert result["seconds"] == RUN_SECONDS


def test_the_checkbox_reaches_the_command_line(monkeypatch, tmp_path) -> None:
    """Non-vacuity for every status above: the run really was asked to compare."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    compare_through_the_endpoint(client)
    assert [args.compare_models for args in parsed] == [True]


def test_an_ordinary_audit_does_not_compare_models(monkeypatch, tmp_path) -> None:
    """The other half of that: an unticked box sends nothing to a third party."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    audit_and_poll(client)
    assert [args.compare_models for args in parsed] == [False]


def test_the_named_cloud_model_reaches_the_command_line(monkeypatch, tmp_path) -> None:
    """A model named in the browser is the model the run is told to use, not a default."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    compare_through_the_endpoint(client, CLOUD_MODEL)
    assert [args.cloud_model for args in parsed] == [CLOUD_MODEL]


def test_a_cloud_model_without_the_flag_is_refused_before_anything_runs(monkeypatch,
                                                                        tmp_path) -> None:
    """A named model with comparison off means two things; neither runs, and no row is written."""
    parsed = stub_the_audit(monkeypatch, tmp_path)
    client, registry = client_over(tmp_path)
    response = post_an_audit(client, cloud_model=CLOUD_MODEL)
    assert response.status_code == REFUSED
    assert parsed == []
    assert registry.store.count() == 0

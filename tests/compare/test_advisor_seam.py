"""`remediation.json` names the model that actually answered, not the one in `src/`.

The seam is `outputs.build_remediation(..., advisor)`, which reaches
`advise.advise_all(..., ask)`. Without it the cloud arm of `--compare-models`
would call a hosted model and then write `model_client.MODEL` into an artifact
sitting under `artifacts/cloud_auditor/` -- a false provenance record, and the
one defect the whole seam exists to prevent.

Every `ask` here is a plain function this file writes. No client is touched and
no server is involved, so what is asserted is the seam and not a model's mood.
The knowledge base is stubbed for the same reason it is everywhere else: an
index this machine happens to have built would otherwise change the answers.
"""

import json

import model_client
import outputs
from artifacts.findings_document import MODEL_UNAVAILABLE, MODEL_USED
from artifacts.remediation import UNAVAILABLE, WRITTEN
from cli_helpers import STUB_ADVICE, stub_knowledge, stub_model
from findings_fixtures import build_document, static_finding
from parsing.languages import PYTHON

# A hosted model's name and decode settings, deliberately unlike the local
# client's, so a test cannot pass by the two happening to agree.
CLOUD_MODEL = "vendor/some-hosted-model"
CLOUD_SETTINGS = {"temperature": 0, "max_tokens": 4000}

# What the hosted model answers: prose and one generic snippet, so the accepted
# path is exercised and the guidance can be traced back to this arm.
CLOUD_ADVICE = ("Treat the fetched value as data and put every tool it can reach behind "
                "an approval step.\n\n```python\nchecked = approve(value)\n```")


def advisor(ask, identifier: str = CLOUD_MODEL, digest: str | None = None) -> dict:
    """The block `audit_run` hands `build_remediation`: a call, a name, and its settings."""
    return {"ask": ask, "identifier": identifier, "settings": CLOUD_SETTINGS,
            "digest": digest}


def cloud_ask(_prompt: str) -> str:
    """A hosted client's reply, in the same shape `model_client.ask` returns."""
    return CLOUD_ADVICE


def refusing_ask(_prompt: str) -> str:
    """A hosted client that cannot be reached, failing the way every client fails."""
    raise RuntimeError("cannot reach the hosted model (stubbed)")


def advised(monkeypatch, ask=cloud_ask, given=advisor) -> dict:
    """Build the remediation artifact for one finding and return it parsed."""
    stub_knowledge(monkeypatch)
    document = build_document([static_finding()])
    return json.loads(outputs.build_remediation(
        document, PYTHON, (), given(ask) if given else None))


# --- the advisor is the model recorded ----------------------------------------

def test_the_hosted_model_that_answered_is_the_one_recorded(monkeypatch) -> None:
    """The whole seam: the arm's own artifact names the arm's own model."""
    stub_model(monkeypatch)
    assert advised(monkeypatch)["model_run"]["model_identifier"] == CLOUD_MODEL


def test_the_local_models_name_is_nowhere_in_the_hosted_arms_artifact(monkeypatch) -> None:
    """The defect being prevented, stated as its own assertion rather than inferred."""
    stub_model(monkeypatch)
    assert advised(monkeypatch)["model_run"]["model_identifier"] != model_client.MODEL


def test_the_advisors_own_decode_settings_are_recorded(monkeypatch) -> None:
    """A hosted model takes no seed, so the settings must travel with the identifier."""
    stub_model(monkeypatch)
    assert advised(monkeypatch)["model_run"]["model_settings"] == CLOUD_SETTINGS


def test_a_hosted_model_records_no_digest(monkeypatch) -> None:
    """OpenRouter names a model but not its weights, so a null field is the honest record."""
    stub_model(monkeypatch)
    assert advised(monkeypatch)["model_run"]["model_digest"] is None


def test_the_advice_written_is_the_advisors_own_answer(monkeypatch) -> None:
    """Guard: the identifier could be right on an artifact the local model actually wrote."""
    stub_model(monkeypatch)
    entry = advised(monkeypatch)["advice"][0]
    assert entry["status"] == WRITTEN
    assert entry["guidance"].startswith("Treat the fetched value as data")


def test_the_local_client_is_never_asked_when_an_advisor_is_given(monkeypatch) -> None:
    """The sharpest form of the seam: the local client is made to fail, and nothing notices."""
    monkeypatch.setattr(model_client, "ask", refusing_ask)
    monkeypatch.setattr(model_client, "model_digest", refusing_ask)
    assert advised(monkeypatch)["model_run"]["status"] == MODEL_USED


# --- with no advisor, nothing changes -----------------------------------------

def test_an_ordinary_audit_still_records_the_local_model(monkeypatch) -> None:
    """The off position: no advisor means the local client answers and records itself."""
    stub_model(monkeypatch)
    document = advised(monkeypatch, given=None)
    assert document["model_run"]["model_identifier"] == model_client.MODEL
    assert document["model_run"]["model_settings"] == model_client.DECODE_SETTINGS


def test_an_ordinary_audits_advice_is_the_local_clients_answer(monkeypatch) -> None:
    """Guard: the identifier above must belong to the model whose words were written."""
    stub_model(monkeypatch)
    entry = advised(monkeypatch, given=None)["advice"][0]
    assert entry["guidance"] == STUB_ADVICE.split("\n\n")[0]


# --- an advisor that answered nothing -----------------------------------------

def test_an_advisor_that_could_not_be_reached_is_not_recorded_as_used(monkeypatch) -> None:
    """A run where every entry is `unavailable` must not claim a model was used.

    Left failing deliberately. `outputs._advice_with_provenance` records
    `MODEL_USED` for an advisor without ever checking that one answered, while
    `advise.advise_one` swallows the `RuntimeError` per finding -- so
    `--semantic-probe` against a stopped Ollama now writes
    `remediation.json` saying `used` beside `findings.json` saying
    `unavailable`, for the same run. Without an advisor the same audit records
    `unavailable`, which is what it did before the seam landed.
    """
    stub_model(monkeypatch)
    document = advised(monkeypatch, ask=refusing_ask)
    assert [entry["status"] for entry in document["advice"]] == [UNAVAILABLE]
    assert document["model_run"]["status"] == MODEL_UNAVAILABLE

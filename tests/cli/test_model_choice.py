"""Which pulled model a run uses, from `--model` down to the call the client makes.

`model_client.ask` takes a model again. The parameter existed once for the
AI-formatted report, went when that feature did, and is back for a different
reason: the artifact records **which model answered**, so the caller has to be
able to say. `audit_run.local_model(wanted, name)` is where a name becomes a
bound call -- it resolves `name or MODEL`, asks `model_digest` for *that* model,
and binds `ask` with `functools.partial`.

So there are three things to hold apart, and a test for each: what
`local_model` records, what the bound call actually sends, and what a run
started from the command line writes into `findings.json`. A block naming the
chosen model while the call went to the configured one would satisfy the first
alone, and that is precisely the defect the parameter exists to prevent -- a
recorded identifier the answer did not come from is worse than none.

No server is involved. The client's three calls are replaced by recorders that
answer from a dict, so nothing here reaches Ollama and nothing depends on which
models this machine has pulled.
"""

from pathlib import Path

import pytest

import audit_run
import model_client
from cli_helpers import EMPTY_SCAN, read_artifact, run_cli, stub_knowledge, stub_syft
from outputs import FINDINGS_NAME
from semantic_probe_fixtures import APP_NAME, write_app

# A model this machine need not have: nothing is pulled, listed or connected to.
# It must differ from the configured one, or every assertion below would pass on
# a run that ignored the name entirely.
CHOSEN_MODEL = "a-second-model:7b-instruct"

# One digest per model, so "the digest of the model that was named" is
# distinguishable from "a digest". Bare hex, the way Ollama reports one.
CHOSEN_DIGEST = "11" * 32
CONFIGURED_DIGEST = "22" * 32
DIGESTS = {CHOSEN_MODEL: CHOSEN_DIGEST, model_client.MODEL: CONFIGURED_DIGEST}

# What a stubbed model answers. Its content never matters here; only which model
# was asked for it does.
REPLY = "Treat the value as data rather than as instruction."

PROBE_FLAG = "--semantic-probe"
MODEL_OPTION = "--model"

# The planner, the probe and one piece of advice. A run that asked nothing would
# satisfy the "every call went to the named model" check with an empty set.
LEAST_MODEL_CALLS = 3

# The web wrapper sends "" for "the configured one", so an empty name is a real
# input to this function and not a malformed one.
NO_NAME_AT_ALL = ""


class Recorder:
    """Stands in for the whole client, answering fixed replies and keeping every model asked for."""

    def __init__(self) -> None:
        """Start with nothing asked."""
        self.asked_with: list[str | None] = []
        self.digests_for: list[str] = []

    # Named `answer` and `digest_of` rather than `ask` and `model_digest`:
    # `cli_helpers.run_cli` decides whether a test has already replaced the
    # client by reading `model_client.ask.__name__`, and a method called `ask`
    # would be mistaken for the real one and stubbed over.
    def answer(self, prompt: str, model: str | None = None) -> str:
        """Answer one prompt, recording which model the caller named."""
        self.asked_with.append(model)
        return REPLY

    def digest_of(self, model: str = model_client.MODEL) -> str | None:
        """Answer the digest recorded for that model, recording which was asked about."""
        self.digests_for.append(model)
        return DIGESTS.get(model)


def recording_client(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    """Replace the client's two calls with recorders, so no socket and no server is needed."""
    recorder = Recorder()
    monkeypatch.setattr(model_client, "ask", recorder.answer)
    monkeypatch.setattr(model_client, "model_digest", recorder.digest_of)
    return recorder


def audit_with(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
               *flags: str) -> tuple[dict, Recorder]:
    """Run the CLI over the probe app with the given flags, and return what it wrote."""
    recorder = recording_client(monkeypatch)
    stub_syft(monkeypatch, EMPTY_SCAN)
    stub_knowledge(monkeypatch)
    assert run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts",
                   flags=flags) == 0
    return read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME), recorder


# --- what `local_model` resolves ----------------------------------------------

def test_a_run_that_names_no_model_records_the_configured_one(monkeypatch) -> None:
    """The default, and the non-vacuity partner for every test below: `name or MODEL`."""
    recording_client(monkeypatch)
    model = audit_run.local_model(True)
    assert model["identifier"] == model_client.MODEL
    assert model["digest"] == CONFIGURED_DIGEST


def test_a_run_that_names_a_model_records_that_one(monkeypatch) -> None:
    """The identifier is the name the caller gave, not the one the environment holds."""
    recording_client(monkeypatch)
    model = audit_run.local_model(True, CHOSEN_MODEL)
    assert model["identifier"] == CHOSEN_MODEL
    assert model["identifier"] != model_client.MODEL


def test_the_digest_is_asked_of_the_named_model_and_not_the_configured_one(
        monkeypatch) -> None:
    """A digest is what makes a mutable tag reproducible, so it must be *that* model's."""
    recorder = recording_client(monkeypatch)
    model = audit_run.local_model(True, CHOSEN_MODEL)
    assert recorder.digests_for == [CHOSEN_MODEL]
    assert model["digest"] == CHOSEN_DIGEST


def test_an_empty_name_is_the_configured_model_rather_than_a_model_called_nothing(
        monkeypatch) -> None:
    """`AuditRequest.model` is "" when the page named none, and "" is not a model."""
    recorder = recording_client(monkeypatch)
    model = audit_run.local_model(True, NO_NAME_AT_ALL)
    assert model["identifier"] == model_client.MODEL
    assert recorder.digests_for == [model_client.MODEL]


def test_no_model_is_resolved_at_all_when_the_probe_was_not_asked_for(monkeypatch) -> None:
    """A name cannot switch a model on: `wanted` is still what decides, and it is first."""
    recorder = recording_client(monkeypatch)
    assert audit_run.local_model(False, CHOSEN_MODEL) is None
    assert recorder.digests_for == []


# --- what the bound call sends ------------------------------------------------

def test_the_call_handed_to_the_checks_names_the_chosen_model(monkeypatch) -> None:
    """The half a recorded identifier cannot prove: the answer came from that model."""
    recorder = recording_client(monkeypatch)
    model = audit_run.local_model(True, CHOSEN_MODEL)
    assert model["ask"]("any prompt at all") == REPLY
    assert recorder.asked_with == [CHOSEN_MODEL]


def test_the_call_names_the_configured_model_when_nothing_was_chosen(monkeypatch) -> None:
    """Guard on the test above: an unbound call would record `None` and default silently."""
    recorder = recording_client(monkeypatch)
    model = audit_run.local_model(True)
    model["ask"]("any prompt at all")
    assert recorder.asked_with == [model_client.MODEL]


# --- and what a whole run writes ----------------------------------------------

def test_the_named_model_is_what_the_findings_artifact_records(monkeypatch, tmp_path) -> None:
    """End to end through argparse: `--model` is what a reader types, so it is driven that way."""
    document, _recorder = audit_with(monkeypatch, tmp_path, PROBE_FLAG,
                                     MODEL_OPTION, CHOSEN_MODEL)
    assert document["model_run"]["model_identifier"] == CHOSEN_MODEL
    assert document["model_run"]["model_digest"] == CHOSEN_DIGEST


def test_the_same_run_without_the_option_records_the_configured_model(
        monkeypatch, tmp_path) -> None:
    """Guard: the test above would pass on a run that recorded whatever it was handed."""
    document, _recorder = audit_with(monkeypatch, tmp_path, PROBE_FLAG)
    assert document["model_run"]["model_identifier"] == model_client.MODEL
    assert document["model_run"]["model_digest"] == CONFIGURED_DIGEST


def test_every_model_call_a_named_run_makes_goes_to_the_named_model(
        monkeypatch, tmp_path) -> None:
    """Not just the recorded one: the planner, the probe and the advice share one bound call.

    Asserted as the whole set of models asked, so a fourth call site that
    reached the client directly -- and so used the configured model while the
    artifact named this one -- fails here rather than in a run nobody compares.
    """
    _document, recorder = audit_with(monkeypatch, tmp_path, PROBE_FLAG,
                                     MODEL_OPTION, CHOSEN_MODEL)
    assert set(recorder.asked_with) == {CHOSEN_MODEL}
    assert len(recorder.asked_with) >= LEAST_MODEL_CALLS

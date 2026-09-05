"""`--semantic-probe` through the real command line, and `main.probe_inputs`.

`probe_inputs` is the single point where a socket enters an audit: it is the one
place `model_client.ask` is handed to a check, and the check itself is barred
from importing the client at all (`tests/parsing/test_offline_containment.py`).
Everything the probe does with a model is reachable only through this function,
so an unguarded call inside it takes the whole audit down with it -- which is
what happened: `model_digest()` raises `RuntimeError` when Ollama is down, and
an audit run with `--semantic-probe` against a stopped server wrote **no
artifacts at all**. Every degradation the probe carefully records was
unreachable from the command line.

So the first test here is the one that matters: server down, flag on, artifacts
still written. The rest pin the two branches of `probe_inputs` and the flag's
effect on `findings.json`.

No server is involved. `stub_model_unavailable` makes every client call raise
the way an unreachable one does, and `stub_model` answers a fixed string, so
these run offline like the rest of the suite.
"""

from pathlib import Path

import main
import model_client
from artifacts.findings_document import MODEL_UNAVAILABLE, MODEL_USED
from checks.semantic_probe import CHECK_NAME as PROBE_CHECK
from cli_helpers import (
    EMPTY_SCAN,
    STUB_MODEL_DIGEST,
    read_artifact,
    run_cli,
    stub_model,
    stub_model_unavailable,
    stub_syft,
)
from outputs import FINDINGS_NAME, REMEDIATION_NAME, SURFACES_NAME
from semantic_probe_fixtures import APP_NAME, PROMPT_LINE, PROMPT_SURFACE_ID, write_app

PROBE_FLAG = ("--semantic-probe",)

# A verdict, so the probe has something to conclude from. It is also what the
# advice call answers, since one stub stands in for one client.
VULNERABLE_REPLY = "VULNERABLE\nThe {question} value lands inside the instructions."


def audit(monkeypatch, tmp_path: Path, flags: tuple[str, ...] = PROBE_FLAG,
          advice: str | None = None) -> dict:
    """Run the CLI over the probe app and return the findings artifact it wrote."""
    stub_syft(monkeypatch, EMPTY_SCAN)
    assert run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts",
                   advice=advice, flags=flags) == 0
    return read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME)


def probe_findings(document: dict) -> list[dict]:
    """The findings the semantic probe contributed to that document."""
    return [f for f in document["findings"] if f["rule_id"] == PROBE_CHECK]


# --- the server is down -------------------------------------------------------

def test_the_audit_still_writes_its_artifacts_when_the_probe_can_reach_no_server(
        monkeypatch, tmp_path) -> None:
    """The whole point: a missing server degrades one check, it does not lose the audit."""
    stub_model_unavailable(monkeypatch)
    stub_syft(monkeypatch, EMPTY_SCAN)
    assert run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts",
                   flags=PROBE_FLAG) == 0
    written = tmp_path / "artifacts" / APP_NAME
    assert [name for name in (SURFACES_NAME, FINDINGS_NAME, REMEDIATION_NAME)
            if not (written / name).is_file()] == []


def test_that_audit_records_the_refused_probe_rather_than_a_model_it_never_reached(
        monkeypatch, tmp_path) -> None:
    """Guard: the artifacts above could be written by a run that never probed at all."""
    stub_model_unavailable(monkeypatch)
    stub_syft(monkeypatch, EMPTY_SCAN)
    assert run_cli(monkeypatch, write_app(tmp_path), tmp_path / "artifacts",
                   flags=PROBE_FLAG) == 0
    document = read_artifact(tmp_path / "artifacts", APP_NAME, FINDINGS_NAME)
    assert [p["subject_id"] for p in document["probes"]] == [PROMPT_SURFACE_ID]
    assert document["model_run"]["status"] == MODEL_UNAVAILABLE
    assert PROBE_CHECK not in document["coverage"]["checks_run"]


# --- probe_inputs, both branches ---------------------------------------------

def test_probe_inputs_hands_back_nothing_when_the_probe_was_not_asked_for() -> None:
    """The default. Two Nones are what make a default audit byte-identical to an old one."""
    assert main.probe_inputs(False) == (None, None)


def test_probe_inputs_hands_over_the_client_call_and_what_it_will_be_decoded_with(
        monkeypatch) -> None:
    """The provenance block is built here, from the client, not written by hand beside it."""
    stub_model(monkeypatch)
    ask, provenance = main.probe_inputs(True)
    assert ask is model_client.ask
    assert provenance == {
        "identifier": model_client.MODEL,
        "settings": model_client.DECODE_SETTINGS,
        "digest": STUB_MODEL_DIGEST,
    }


def test_probe_inputs_records_no_digest_when_the_digest_call_is_refused(monkeypatch) -> None:
    """A digest is a provenance nicety; the audit is not, so its absence is not fatal.

    `model_digest` raises `RuntimeError` with the server down. Unguarded, that
    escaped `run()` before a single artifact was written.
    """
    stub_model_unavailable(monkeypatch)
    ask, provenance = main.probe_inputs(True)
    assert ask is model_client.ask
    assert provenance["digest"] is None
    assert provenance["identifier"] == model_client.MODEL


# --- the flag's effect on findings.json ---------------------------------------

def test_the_flag_puts_the_models_verdict_in_the_findings_artifact(
        monkeypatch, tmp_path) -> None:
    """End to end through argparse: the flag is what turns the probe on for a real run."""
    document = audit(monkeypatch, tmp_path, advice=VULNERABLE_REPLY)
    assert [(f["file"], f["line"]) for f in probe_findings(document)] == [
        ("agent.py", PROMPT_LINE)]
    assert document["model_run"]["status"] == MODEL_USED
    assert document["model_run"]["model_digest"] == STUB_MODEL_DIGEST
    assert PROBE_CHECK in document["coverage"]["checks_run"]


def test_an_audit_run_without_the_flag_asks_the_model_nothing_about_a_template(
        monkeypatch, tmp_path) -> None:
    """Guard: without this the test above would pass on a probe that always ran."""
    document = audit(monkeypatch, tmp_path, flags=(), advice=VULNERABLE_REPLY)
    assert document["probes"] == []
    assert probe_findings(document) == []
    assert PROBE_CHECK not in document["coverage"]["checks_run"]

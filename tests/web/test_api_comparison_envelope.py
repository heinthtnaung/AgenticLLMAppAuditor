"""What `comparison` holds in the envelope, once a second arm really ran.

`test_api_compare_models.py` is about the run *finishing* -- the 500 that used to
be answered after the audited source had already gone to a third party. This
file is about the key that finishing now produces, and it exists because the
hosted arm was audited, published, scored and then thrown away: `compare_run.run`
returned the local arm alone, so the web UI could run a comparison and never show
one.

Four claims, and none of them follows from the others:

- **`system` is the one key the enclosing envelope does not carry.** It sits
  where the envelope carries `schema_version`, because one constant repeated
  inside one reply is a disagreement waiting to be handled -- so the comparison
  does *not* repeat the version, and a test below says so.
- **Both names come from `evaluation.document`**, never a word invented in
  `run_jobs.py` or in JavaScript. It is the same join `GET /api/stages` has to
  `progress.STAGES`, asserted the same way: against the constant, with the
  literal pinned once beside it so the comparison is not the constant agreeing
  with itself. `compared_with` is the second of them and it is here because the
  page had already invented the first: `ComparisonCard.jsx` labelled the local
  arm with a hardcoded `"agentic_auditor"` -- inventing in JavaScript the exact
  word `_comparison` refuses to invent in Python. The arm carries the name now
  and the page spells neither; `test_jsx_envelope_fields.py` holds that half.
- **The comparison is the hosted arm's own documents**, read from the hosted
  arm's own directory. The two arms are planted with different counts here, so
  an envelope that rendered the local arm twice fails rather than looks right.
- **`null` means one arm ran.** It has never meant that a second arm found
  nothing, which is the distinction this whole project is about.

`main.run` is replaced throughout by the recorder in `audit_stub.py`. The
comparison the real one performs is `tests/compare/test_compare_arms_result.py`,
over an app written into `tmp_path`; what is under test here is the wrapper's
translation of that result into an envelope. Nothing here calls a model, opens a
socket or clones anything.

The whole file skips without the server packages: with no fastapi there is no
endpoint to post to.
"""

import json

import pytest

pytest.importorskip("fastapi", reason="the web extra is not installed, so there is no endpoint")
pytest.importorskip("httpx", reason="fastapi's TestClient needs httpx to drive the endpoint")

from pathlib import Path                           # noqa: E402

from evaluation.document import (                  # noqa: E402
    AGENTIC_AUDITOR, CLOUD_AUDITOR, SCORED_SYSTEMS)
from outputs import FINDINGS_NAME, SURFACES_NAME   # noqa: E402

from .api_stubs import audit_and_poll, client_over   # noqa: E402
from .audit_stub import (                          # noqa: E402
    APP, CLOUD_APP, CLOUD_RUN_SECONDS, RUN_SECONDS, artifacts_dir_for,
    cloud_artifacts_dir_for, stub_the_audit)

# The name the hosted arm is reported under, pinned as a literal beside the
# constant it must equal. Imported alone it would agree with itself, and the
# word is one a page could otherwise invent for itself.
EXPECTED_CLOUD_SYSTEM = "cloud_auditor"

# The local arm's name, pinned the same way and for the same reason. This is the
# word `ComparisonCard.jsx` used to hardcode.
EXPECTED_LOCAL_SYSTEM = "agentic_auditor"

# What one arm of the comparison carries: the six keys an envelope already
# carries about an audit, plus **both** names -- the system that produced them
# and the system it is compared with, so the page spells neither.
EXPECTED_COMPARISON_KEYS = {"system", "compared_with", "app", "artifacts_dir",
                            "seconds", "advisories_read", "findings", "surfaces"}

# Deliberately absent from the comparison: the envelope already carries it once,
# and a second copy inside one reply is two numbers that can disagree.
NOT_IN_THE_COMPARISON = "schema_version"

# Different on the two arms, so an envelope that showed the local arm twice is a
# failure rather than a plausible-looking pass.
LOCAL_FINDING_COUNT = 3
CLOUD_FINDING_COUNT = 8
LOCAL_SURFACE_COUNT = 5
CLOUD_SURFACE_COUNT = 6

# The document versions the planted artifacts declare. Any value would round
# trip; these are the ones the real serialisers write.
FINDINGS_SCHEMA_VERSION = 7
SURFACES_SCHEMA_VERSION = 3


def plant_documents(directory: Path, findings: int, surfaces: int) -> None:
    """Write the two artifacts an arm's half of the envelope is read from."""
    directory.mkdir(parents=True)
    (directory / FINDINGS_NAME).write_text(
        json.dumps({"schema_version": FINDINGS_SCHEMA_VERSION,
                    "finding_count": findings, "findings": []}), encoding="utf-8")
    (directory / SURFACES_NAME).write_text(
        json.dumps({"schema_version": SURFACES_SCHEMA_VERSION,
                    "surface_count": surfaces, "surfaces": []}), encoding="utf-8")


def plant_both_arms(tmp_path: Path) -> None:
    """Write each arm's documents into its own directory, with counts that differ."""
    plant_documents(artifacts_dir_for(tmp_path), LOCAL_FINDING_COUNT, LOCAL_SURFACE_COUNT)
    plant_documents(cloud_artifacts_dir_for(tmp_path), CLOUD_FINDING_COUNT,
                    CLOUD_SURFACE_COUNT)


def compared_envelope(monkeypatch, tmp_path: Path) -> dict:
    """Post one audit with model comparison ticked and answer with its envelope."""
    stub_the_audit(monkeypatch, tmp_path, compares=True)
    client, _ = client_over(tmp_path)
    record = audit_and_poll(client, compare_models=True)
    assert record["status"] == "finished", record["error"]
    return record["result"]


# --- the key the comparison produces -------------------------------------------

def test_a_two_arm_run_carries_a_comparison(monkeypatch, tmp_path) -> None:
    """The bug: the hosted arm was audited and published and then nothing returned it."""
    assert compared_envelope(monkeypatch, tmp_path)["comparison"] is not None


def test_the_comparison_holds_exactly_the_documented_keys(monkeypatch, tmp_path) -> None:
    """Six keys about an audit, and the two system names it is described by."""
    comparison = compared_envelope(monkeypatch, tmp_path)["comparison"]
    assert set(comparison) == EXPECTED_COMPARISON_KEYS


def test_the_comparison_does_not_repeat_the_schema_version(monkeypatch, tmp_path) -> None:
    """One constant repeated inside one reply is a disagreement waiting to be handled."""
    envelope = compared_envelope(monkeypatch, tmp_path)
    assert NOT_IN_THE_COMPARISON not in envelope["comparison"]
    assert NOT_IN_THE_COMPARISON in envelope


# --- where the name comes from --------------------------------------------------

def test_the_comparison_names_the_system_that_produced_it(monkeypatch, tmp_path) -> None:
    """The same join `GET /api/stages` has to `progress.STAGES`: the constant, not a word."""
    comparison = compared_envelope(monkeypatch, tmp_path)["comparison"]
    assert comparison["system"] == CLOUD_AUDITOR


def test_the_comparison_names_the_system_it_is_compared_with(monkeypatch, tmp_path) -> None:
    """The local arm's own name, carried rather than left for a page to invent.

    It was invented: the card labelled the left-hand arm with a hardcoded
    `"agentic_auditor"`, in a language nothing binds to `evaluation.document`.
    """
    comparison = compared_envelope(monkeypatch, tmp_path)["comparison"]
    assert comparison["compared_with"] == AGENTIC_AUDITOR


def test_the_two_arms_are_named_apart(monkeypatch, tmp_path) -> None:
    """Non-vacuity: one constant standing for both would satisfy each check on its own."""
    comparison = compared_envelope(monkeypatch, tmp_path)["comparison"]
    assert comparison["system"] != comparison["compared_with"]


def test_both_system_names_are_the_ones_the_scorer_knows() -> None:
    """Pins the constants above, so the assertions are not imports agreeing with themselves."""
    assert (CLOUD_AUDITOR, AGENTIC_AUDITOR) == (EXPECTED_CLOUD_SYSTEM,
                                                EXPECTED_LOCAL_SYSTEM)
    assert {CLOUD_AUDITOR, AGENTIC_AUDITOR} <= set(SCORED_SYSTEMS)


def test_the_stub_never_spelled_either_system_name(monkeypatch, tmp_path) -> None:
    """Non-vacuity: the words have to have come from `run_jobs`, not from this file's fake."""
    envelope = compared_envelope(monkeypatch, tmp_path)
    comparison = envelope["comparison"]
    for name in (CLOUD_AUDITOR, AGENTIC_AUDITOR):
        assert name not in comparison["artifacts_dir"]
        assert name not in comparison["app"]
        assert name not in envelope["artifacts_dir"]


# --- whose facts the comparison reports -----------------------------------------

def test_the_comparison_reports_the_hosted_arms_own_facts(monkeypatch, tmp_path) -> None:
    """Its app, its directory, its duration -- never a second view of the local arm's."""
    envelope = compared_envelope(monkeypatch, tmp_path)
    comparison = envelope["comparison"]
    assert comparison["app"] == CLOUD_APP != envelope["app"]
    assert comparison["artifacts_dir"] == str(cloud_artifacts_dir_for(tmp_path))
    assert comparison["seconds"] == CLOUD_RUN_SECONDS != envelope["seconds"]


def test_the_two_arms_report_their_own_documents(monkeypatch, tmp_path) -> None:
    """Planted with different counts, so an envelope showing one arm twice fails here."""
    plant_both_arms(tmp_path)
    envelope = compared_envelope(monkeypatch, tmp_path)
    assert envelope["findings"]["finding_count"] == LOCAL_FINDING_COUNT
    assert envelope["comparison"]["findings"]["finding_count"] == CLOUD_FINDING_COUNT


def test_each_arms_surfaces_document_is_its_own(monkeypatch, tmp_path) -> None:
    """The second document, so neither arm is right by the other's accident."""
    plant_both_arms(tmp_path)
    envelope = compared_envelope(monkeypatch, tmp_path)
    assert envelope["surfaces"]["surface_count"] == LOCAL_SURFACE_COUNT
    assert envelope["comparison"]["surfaces"]["surface_count"] == CLOUD_SURFACE_COUNT


def test_an_arm_that_wrote_no_documents_reports_null_rather_than_empty_ones(
        monkeypatch, tmp_path) -> None:
    """`null` is not an empty document: no artifact was written, which is a gap."""
    comparison = compared_envelope(monkeypatch, tmp_path)["comparison"]
    assert comparison["findings"] is None
    assert comparison["surfaces"] is None


# --- and the other direction ----------------------------------------------------

def test_a_single_arm_audit_carries_a_null_comparison(monkeypatch, tmp_path) -> None:
    """One arm ran. That is a different fact from a second arm that found nothing."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    assert audit_and_poll(client)["result"]["comparison"] is None


def test_the_single_arm_envelope_still_reports_the_local_arm(monkeypatch,
                                                             tmp_path) -> None:
    """Non-vacuity for the null above: the run really produced an envelope to be null in."""
    stub_the_audit(monkeypatch, tmp_path)
    client, _ = client_over(tmp_path)
    envelope = audit_and_poll(client)["result"]
    assert envelope["app"] == APP
    assert envelope["seconds"] == RUN_SECONDS

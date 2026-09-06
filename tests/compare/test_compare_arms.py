"""`--compare-models` writes two arms into two directories, and scores each as itself.

The two arms differ by model and by nothing else, so their artifacts must be
told apart by where they land: `artifacts/agentic_auditor/<app>` for the local
model, `artifacts/cloud_auditor/<app>` for the hosted one. If they shared a
directory the second arm would overwrite the first and the comparison would be
one audit reported twice.

Every test here drives the whole run. The claims about where the two arms
default to, which need no run at all, are `test_compare_arm_directories.py`.

The run is driven under `monkeypatch.chdir(tmp_path)`, so the two relative
artifact constants resolve inside the temporary tree and the real `artifacts/`
is never written to. `key_drafting.DRAFTED_KEYS_DIR` is absolute, under
`grading_keys/`, so chdir cannot move it: it is redirected too, and one test
below says where the draft landed rather than leaving it to be inferred.

Both clients and the knowledge base are replaced by plain functions;
`pipeline.publish` is replaced too, because exporting HTML and PDF needs a
renderer this suite does not require and is `tests/cli/test_export_reports*.py`'s
subject, not this one.
"""

import json
from pathlib import Path

import cloud_client
import compare_run
import fetch_repo
import key_drafting
import main
import model_client
import pipeline
from cli_helpers import stub_knowledge
from evaluation.document import AGENTIC_AUDITOR, CLOUD_AUDITOR
from evaluation.harness import EVALUATION_NAME
from grading_keys import GROUND_TRUTH_SUFFIX, discover_graded_apps, key_path
from mixed_app_fixtures import APP_NAME, PYTHON_FILE, write_mixed_app
from outputs import FINDINGS_NAME, REMEDIATION_NAME
from shipped_key_fixtures import SHIPPED_APPS

CLOUD_MODEL = "vendor/some-hosted-model"
COMMIT = "d" * 40
UPSTREAM_URL = "https://example.invalid/owner/mixed-app"
COMMIT_DATE = "2026-01-01T00:00:00Z"

# One key entry, answered by the tool call the mixed app really carries, so the
# drafted key is scorable rather than empty.
TOOL_LINE = 7
DRAFTED_ENTRY = {"id": "K-01", "file": PYTHON_FILE, "line": TOOL_LINE, "owasp_id": "LLM06",
                 "llm_surface": "TOOL_CALL", "surface_name": "ShellTool",
                 "component": None, "detection": "static",
                 "title": "A shell tool", "description": "why"}

# The sentence in the drafting prompt that tells the stub which question it is
# being asked. `key_drafting.PROMPT` opens with it.
DRAFTING_MARKER = "drafting a security grading key"

ADVICE = "Treat it as data and gate the tool.\n\n```python\nchecked = approve(value)\n```"

# Six JSON documents plus the two rendered reports -- the count `audit_run.audit`
# prints for an app with no bill of materials.
ARTIFACTS_PER_ARM = 8


def local_ask(prompt: str, model: str | None = None) -> str:
    """The local client's reply: the drafted key when asked for one, advice otherwise."""
    if DRAFTING_MARKER in prompt:
        return json.dumps([DRAFTED_ENTRY])
    return ADVICE


def cloud_ask(_prompt: str, _model: str | None = None) -> str:
    """The hosted client's reply. It is never asked to draft: only the local arm drafts."""
    return ADVICE


def drafts_dir(tmp_path: Path) -> Path:
    """Where a drafted key goes in a test: a tmp_path stand-in for grading_keys/drafts/."""
    return tmp_path / "grading_keys" / "drafts"


def stage(monkeypatch, tmp_path: Path) -> Path:
    """Write the app, pin it, replace both clients, and run inside the temporary tree."""
    repo = write_mixed_app(tmp_path)
    monkeypatch.setattr(key_drafting, "DRAFTED_KEYS_DIR", drafts_dir(tmp_path))
    fetch_repo.write_manifest(
        tmp_path, fetch_repo.manifest(APP_NAME, UPSTREAM_URL, COMMIT, COMMIT_DATE))
    stub_knowledge(monkeypatch)
    monkeypatch.setattr(model_client, "ask", local_ask)
    monkeypatch.setattr(model_client, "model_digest", lambda model=None: "0" * 64)
    monkeypatch.setattr(cloud_client, "ask", cloud_ask)
    monkeypatch.setattr(pipeline, "publish", lambda *args, **kwargs: None)
    monkeypatch.chdir(tmp_path)
    return repo


def compare(monkeypatch, tmp_path: Path) -> int:
    """Run `--compare-models` end to end over the written app."""
    repo = stage(monkeypatch, tmp_path)
    return compare_run.run(str(repo), main.DEFAULT_ARTIFACTS_DIR, CLOUD_MODEL)


def arm(tmp_path: Path, system: str) -> Path:
    """Where one arm's per-app artifacts landed."""
    return tmp_path / "artifacts" / system / APP_NAME


def read(path: Path) -> dict:
    """Read one written artifact."""
    return json.loads(path.read_text(encoding="utf-8"))


# --- the two directories ------------------------------------------------------

def test_both_arms_write_their_own_artifacts(monkeypatch, tmp_path) -> None:
    """Two audits, two directories: the first arm is still there when the second finishes."""
    assert compare(monkeypatch, tmp_path) == 0
    for system in (AGENTIC_AUDITOR, CLOUD_AUDITOR):
        assert (arm(tmp_path, system) / FINDINGS_NAME).is_file(), system


def test_each_arm_wrote_a_whole_audits_worth_of_artifacts(monkeypatch, tmp_path) -> None:
    """Guard: an arm that wrote one file would satisfy the test above having half run."""
    compare(monkeypatch, tmp_path)
    for system in (AGENTIC_AUDITOR, CLOUD_AUDITOR):
        written = [path.name for path in arm(tmp_path, system).iterdir()]
        assert len(written) == ARTIFACTS_PER_ARM, system


def test_neither_arm_overwrote_the_others_provenance(monkeypatch, tmp_path) -> None:
    """The point of the split: each `remediation.json` names the model that produced it."""
    compare(monkeypatch, tmp_path)
    named = {system: read(arm(tmp_path, system) / REMEDIATION_NAME)["model_run"][
        "model_identifier"] for system in (AGENTIC_AUDITOR, CLOUD_AUDITOR)}
    assert named == {AGENTIC_AUDITOR: model_client.MODEL, CLOUD_AUDITOR: CLOUD_MODEL}


def test_the_hosted_arm_is_not_written_beside_the_local_one(monkeypatch, tmp_path) -> None:
    """A cloud arm under the auditor's own name would be scored as the auditor's work."""
    compare(monkeypatch, tmp_path)
    assert sorted(path.name for path in (tmp_path / "artifacts").iterdir()) == [
        AGENTIC_AUDITOR, CLOUD_AUDITOR]


def test_the_drafted_key_landed_in_the_folder_nothing_discovers(monkeypatch,
                                                                tmp_path) -> None:
    """The draft is written where it was pointed, and the repository's own keys are untouched."""
    compare(monkeypatch, tmp_path)
    assert key_path(APP_NAME, GROUND_TRUTH_SUFFIX, drafts_dir(tmp_path)).is_file()
    assert discover_graded_apps() == SHIPPED_APPS


# --- both arms are scored, each as itself -------------------------------------

def test_each_arm_gets_its_own_evaluation(monkeypatch, tmp_path) -> None:
    """One evaluation per system per run, beside that system's per-app artifacts."""
    compare(monkeypatch, tmp_path)
    for system in (AGENTIC_AUDITOR, CLOUD_AUDITOR):
        assert (tmp_path / "artifacts" / system / EVALUATION_NAME).is_file(), system


def test_each_evaluation_records_the_system_it_scored(monkeypatch, tmp_path) -> None:
    """Guard: two files could both hold the same arm's score without this."""
    compare(monkeypatch, tmp_path)
    scored = [read(tmp_path / "artifacts" / system / EVALUATION_NAME)["system"]
              for system in (AGENTIC_AUDITOR, CLOUD_AUDITOR)]
    assert scored == [AGENTIC_AUDITOR, CLOUD_AUDITOR]


def test_both_arms_are_scored_against_the_one_drafted_key(monkeypatch, tmp_path) -> None:
    """A comparison needs one answer key; each arm's score names the same entry count."""
    compare(monkeypatch, tmp_path)
    counts = [read(tmp_path / "artifacts" / system / EVALUATION_NAME)["apps"][0][
        "key_finding_count"] for system in (AGENTIC_AUDITOR, CLOUD_AUDITOR)]
    assert counts == [1, 1]


def test_the_drafted_key_marks_both_scores_as_circular(monkeypatch, tmp_path) -> None:
    """The key was written by one of the systems being scored, and both scores say so."""
    compare(monkeypatch, tmp_path)
    for system in (AGENTIC_AUDITOR, CLOUD_AUDITOR):
        said = read(tmp_path / "artifacts" / system / EVALUATION_NAME)["apps"][0][
            "qualifications"]
        assert "key_drafted_by_scored_system" in said, system
        assert "key_ai_drafted" in said, system


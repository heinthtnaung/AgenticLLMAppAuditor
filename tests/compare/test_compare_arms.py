"""`--compare-models` writes two arms into two directories, and scores each as itself.

The two arms differ by model and by nothing else, so their artifacts must be
told apart by where they land: `artifacts/agentic_auditor/<app>` for the local
model, `artifacts/cloud_auditor/<app>` for the hosted one. If they shared a
directory the second arm would overwrite the first and the comparison would be
one audit reported twice.

Every test here drives the whole run, staged by `compare_arms_fixtures`, which
says what is replaced and why. The claims about where the two arms default to,
which need no run at all, are `test_compare_arm_directories.py`. What the run
*returns* is `test_compare_arms_result.py`: that was here until this file grew
past the size rule, and it is a different subject -- where the artifacts went
against what the caller is handed.
"""

from compare_arms_fixtures import CLOUD_MODEL, arm, compare, drafts_dir, read
from evaluation.document import AGENTIC_AUDITOR, CLOUD_AUDITOR
from evaluation.harness import EVALUATION_NAME
from keys.grading_keys import GROUND_TRUTH_SUFFIX, discover_graded_apps, key_path
from mixed_app_fixtures import APP_NAME
from outputs import FINDINGS_NAME, REMEDIATION_NAME

import model_client

# Six JSON documents plus the two rendered reports -- the count `audit_run.audit`
# prints for an app with no bill of materials.
ARTIFACTS_PER_ARM = 8


# --- the two directories ------------------------------------------------------

def test_both_arms_write_their_own_artifacts(monkeypatch, tmp_path) -> None:
    """Two audits, two directories: the first arm is still there when the second finishes."""
    compare(monkeypatch, tmp_path)
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
    """The draft is written where it was pointed, and the repository's own keys are untouched.

    Discovery is compared before against after rather than to a list of what
    ships: `grading_keys/` holds no key today, and a draft landing there has to
    fail this whether it holds one or not.
    """
    before = discover_graded_apps()
    compare(monkeypatch, tmp_path)
    assert key_path(APP_NAME, GROUND_TRUTH_SUFFIX, drafts_dir(tmp_path)).is_file()
    assert discover_graded_apps() == before
    assert APP_NAME not in discover_graded_apps()


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

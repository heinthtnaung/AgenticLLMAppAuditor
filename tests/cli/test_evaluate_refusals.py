"""What the evaluation entry point refuses to score, and what it tells the reader.

Two absences look alike from a distance and need different instructions. An app
that was never audited needs the producing system run over it; an app that was
never downloaded has no source to run anything over, and "run the auditor first"
would send its reader in circles. Neither may be swallowed into a partial
document -- a missing findings.json scored as "nothing found" reads as a
perfect-precision run over an app nobody looked at.
"""

import evaluate
from corpus_paths import DOWNLOAD_HINT
from evaluate_helpers import OTHER_SYSTEM, run_evaluate, stage_artifacts, stage_corpus
from evaluation.document import AGENTIC_AUDITOR
from evaluation_fixtures import APP


def test_a_missing_artifact_exits_one(tmp_path, monkeypatch) -> None:
    """A partial run must fail rather than produce a complete-looking score."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = stage_artifacts(tmp_path, AGENTIC_AUDITOR)
    assert run_evaluate(monkeypatch, artifacts_dir, OTHER_SYSTEM) == 1


def test_a_missing_artifact_names_the_system_that_should_have_produced_it(
        tmp_path, monkeypatch, capsys) -> None:
    """"Run the auditor first" is the wrong instruction when a baseline is being scored."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = stage_artifacts(tmp_path, AGENTIC_AUDITOR)
    run_evaluate(monkeypatch, artifacts_dir, OTHER_SYSTEM)
    assert f"Run {OTHER_SYSTEM} over this app first" in capsys.readouterr().err


def test_a_fixture_that_was_never_downloaded_exits_one(tmp_path, monkeypatch) -> None:
    """No source on disk to audit is still a refusal, not an app scored as zero."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = stage_artifacts(tmp_path)
    monkeypatch.setattr(evaluate, "app_is_present", lambda app: False)
    assert run_evaluate(monkeypatch, artifacts_dir) == 1


def test_a_fixture_that_was_never_downloaded_says_where_to_get_it(
        tmp_path, monkeypatch, capsys) -> None:
    """It names the app and carries the one download hint `corpus_paths` owns."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = stage_artifacts(tmp_path)
    monkeypatch.setattr(evaluate, "app_is_present", lambda app: False)
    run_evaluate(monkeypatch, artifacts_dir)
    error = capsys.readouterr().err
    assert APP in error and DOWNLOAD_HINT in error


def test_not_downloaded_is_told_apart_from_not_audited(tmp_path, monkeypatch, capsys) -> None:
    """The two refusals need different instructions, so neither message may carry the other."""
    stage_corpus(tmp_path, monkeypatch)
    artifacts_dir = stage_artifacts(tmp_path)
    monkeypatch.setattr(evaluate, "app_is_present", lambda app: False)
    run_evaluate(monkeypatch, artifacts_dir)
    assert "over this app first" not in capsys.readouterr().err

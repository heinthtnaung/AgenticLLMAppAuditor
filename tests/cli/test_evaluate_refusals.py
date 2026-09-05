"""What the evaluation entry point refuses to score, and what it tells the reader.

Two absences look alike from a distance and need different answers. An app with
a grading key but no artifacts was never audited, and needs the producing system
run over it -- that is a **hard** error, because a missing findings.json scored
as "nothing found" reads as a perfect-precision run over an app nobody looked
at. No grading key at all is a different fact: this project ships none, so
zero keys is normal, and the run says there is nothing to score rather than
writing an evaluation over no apps.

A third refusal is about a file that is present and misshapen: a key whose
entry is short a field, or an artifact short one the scorer reads. Both used to
raise a bare `KeyError` from inside `scorer.py`, and `KeyError` is not one of
`evaluate.py`'s `EXPECTED_FAILURES` -- so the project's own evaluation command
answered a typo with a traceback. The shapes themselves are checked in
`tests/evaluation/`; what is asserted here is the end of that path, which is
the exit code and the single line on stderr.

The keys directory is written by `evaluate_helpers` under `tmp_path` and passed
in with `--keys-dir`; nothing here reads the real `grading_keys/`.
"""

from evaluate_helpers import (
    ARTIFACTS_DIR_NAME,
    OTHER_SYSTEM,
    run_evaluate,
    stage_artifacts,
    stage_empty_keys,
    stage_keys,
)
from evaluation.document import AGENTIC_AUDITOR
from evaluation.harness import EVALUATION_NAME
from evaluation_fixtures import APP, findings_document, grading_key, key_entry
from grading_keys import GROUND_TRUTH_SUFFIX

# The staged key's filename, which the refusal has to spell for a reader.
KEY_FILE_NAME = f"{APP}{GROUND_TRUTH_SUFFIX}"


def key_with_a_malformed_entry() -> dict:
    """A key whose one finding entry is short a field the scorer reads."""
    entry = key_entry()
    del entry["owasp_id"]
    return grading_key([entry])


def findings_with_no_probes() -> dict:
    """A findings document short of the field `scorer.py` reads at line 133."""
    document = findings_document()
    del document["probes"]
    return document


def test_a_missing_artifact_exits_one(tmp_path, monkeypatch) -> None:
    """A partial run must fail rather than produce a complete-looking score."""
    keys_dir = stage_keys(tmp_path)
    artifacts_dir = stage_artifacts(tmp_path, AGENTIC_AUDITOR)
    assert run_evaluate(monkeypatch, artifacts_dir, OTHER_SYSTEM, keys_dir) == 1


def test_a_missing_artifact_names_the_system_that_should_have_produced_it(
        tmp_path, monkeypatch, capsys) -> None:
    """"Run the auditor first" is the wrong instruction when a baseline is being scored."""
    keys_dir = stage_keys(tmp_path)
    artifacts_dir = stage_artifacts(tmp_path, AGENTIC_AUDITOR)
    run_evaluate(monkeypatch, artifacts_dir, OTHER_SYSTEM, keys_dir)
    assert f"Run {OTHER_SYSTEM} over this app first" in capsys.readouterr().err


def test_a_key_with_no_artifacts_at_all_is_a_hard_error(tmp_path, monkeypatch) -> None:
    """The regression that matters: an unaudited graded app must not be quietly skipped."""
    keys_dir = stage_keys(tmp_path)
    assert run_evaluate(monkeypatch, tmp_path / ARTIFACTS_DIR_NAME,
                        keys_dir=keys_dir) == 1


def test_a_key_with_no_artifacts_names_the_app_and_the_file(
        tmp_path, monkeypatch, capsys) -> None:
    """`evaluation.json` has no field for who was skipped, so the refusal must say who."""
    keys_dir = stage_keys(tmp_path)
    run_evaluate(monkeypatch, tmp_path / ARTIFACTS_DIR_NAME, keys_dir=keys_dir)
    error = capsys.readouterr().err
    assert f"{APP}'s findings" in error and "findings.json" in error


def test_a_key_with_no_artifacts_writes_no_evaluation(tmp_path, monkeypatch) -> None:
    """Every app is scored or nothing is written; a one-app pool would read as complete."""
    keys_dir = stage_keys(tmp_path)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    run_evaluate(monkeypatch, artifacts_dir, keys_dir=keys_dir)
    assert not (artifacts_dir / AGENTIC_AUDITOR / EVALUATION_NAME).exists()


def test_no_grading_key_at_all_exits_one(tmp_path, monkeypatch) -> None:
    """Zero keys is normal -- this project ships none -- but it is not a score."""
    empty = stage_empty_keys(tmp_path)
    assert run_evaluate(monkeypatch, stage_artifacts(tmp_path), keys_dir=empty) == 1


def test_no_grading_key_says_there_was_nothing_to_score(
        tmp_path, monkeypatch, capsys) -> None:
    """It reads as a fact about the checkout, not as a fault in it."""
    empty = stage_empty_keys(tmp_path)
    run_evaluate(monkeypatch, stage_artifacts(tmp_path), keys_dir=empty)
    assert "no grading key found, so there is nothing to score" in capsys.readouterr().err


def test_a_missing_keys_directory_exits_one_too(tmp_path, monkeypatch) -> None:
    """A checkout with no keys folder at all reaches the same refusal, not a traceback."""
    absent = tmp_path / "no-such-keys"
    assert run_evaluate(monkeypatch, stage_artifacts(tmp_path), keys_dir=absent) == 1


def test_no_grading_key_writes_no_evaluation(tmp_path, monkeypatch) -> None:
    """An evaluation over no apps would ship as "scored, nothing to report"."""
    empty = stage_empty_keys(tmp_path)
    artifacts_dir = stage_artifacts(tmp_path)
    run_evaluate(monkeypatch, artifacts_dir, keys_dir=empty)
    assert not (artifacts_dir / AGENTIC_AUDITOR / EVALUATION_NAME).exists()


def test_not_scorable_is_told_apart_from_not_audited(tmp_path, monkeypatch, capsys) -> None:
    """The two refusals need different answers, so neither message may carry the other."""
    empty = stage_empty_keys(tmp_path)
    run_evaluate(monkeypatch, stage_artifacts(tmp_path), keys_dir=empty)
    assert "over this app first" not in capsys.readouterr().err


def test_a_key_with_a_malformed_entry_exits_one(tmp_path, monkeypatch) -> None:
    """The point of the shape check: a hand-edited key fails as a refusal, not a traceback."""
    keys_dir = stage_keys(tmp_path, key=key_with_a_malformed_entry())
    assert run_evaluate(monkeypatch, stage_artifacts(tmp_path), keys_dir=keys_dir) == 1


def test_a_malformed_entry_is_reported_as_one_error_line(
        tmp_path, monkeypatch, capsys) -> None:
    """`error: ...` on stderr, which is exactly what an escaping `KeyError` was not."""
    keys_dir = stage_keys(tmp_path, key=key_with_a_malformed_entry())
    run_evaluate(monkeypatch, stage_artifacts(tmp_path), keys_dir=keys_dir)
    assert capsys.readouterr().err.startswith("error: ")


def test_a_malformed_entry_names_the_key_file_and_the_entry(
        tmp_path, monkeypatch, capsys) -> None:
    """The reader has to open one file and find one entry in it, so both are named."""
    keys_dir = stage_keys(tmp_path, key=key_with_a_malformed_entry())
    run_evaluate(monkeypatch, stage_artifacts(tmp_path), keys_dir=keys_dir)
    error = capsys.readouterr().err
    assert KEY_FILE_NAME in error and "findings[0] is missing owasp_id" in error


def test_a_malformed_entry_writes_no_evaluation(tmp_path, monkeypatch) -> None:
    """Nothing was scored, so nothing is written: a partial score is the worst outcome."""
    keys_dir = stage_keys(tmp_path, key=key_with_a_malformed_entry())
    artifacts_dir = stage_artifacts(tmp_path)
    run_evaluate(monkeypatch, artifacts_dir, keys_dir=keys_dir)
    assert not (artifacts_dir / AGENTIC_AUDITOR / EVALUATION_NAME).exists()


def test_an_artifact_short_of_a_field_the_scorer_reads_exits_one(
        tmp_path, monkeypatch) -> None:
    """The other half of the same escape: a findings.json with no `probes` at all."""
    keys_dir = stage_keys(tmp_path)
    artifacts_dir = stage_artifacts(tmp_path, findings=findings_with_no_probes())
    assert run_evaluate(monkeypatch, artifacts_dir, keys_dir=keys_dir) == 1


def test_an_artifact_short_of_a_field_names_the_file_and_the_field(
        tmp_path, monkeypatch, capsys) -> None:
    """Named, because every app and every scored system writes a file of that name."""
    keys_dir = stage_keys(tmp_path)
    artifacts_dir = stage_artifacts(tmp_path, findings=findings_with_no_probes())
    run_evaluate(monkeypatch, artifacts_dir, keys_dir=keys_dir)
    assert f"{APP}/findings.json is missing probes" in capsys.readouterr().err

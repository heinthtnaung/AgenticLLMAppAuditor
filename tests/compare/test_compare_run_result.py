"""`main.run` under `--compare-models` answers with what the comparison produced.

Every other path through `main.run` returns the audit's result -- app name,
artifacts directory, wall clock, whether advisories were read -- and `main`
turns that into an exit code. The comparison branch is a different function
entirely, so it is the one path where the promise could quietly stop being
true. It did: `compare_run.run` returned `0`, and the first caller that was not
a command line -- `web/api.py`, which reads `produced["app"]` -- answered the
browser with a 500. Raised, on this path, only after both audits had finished
and the audited repository's source had already gone to a third party.

This file is the middle link of three. `test_compare_arms.py` runs the real
comparison and asserts the shape it returns; this asserts `main.run` hands that
back unchanged and takes the branch only when the flag is set;
`tests/web/test_api_compare_models.py` asserts the wrapper turns it into a 200.
Each is cheap on its own and none of the three is sufficient alone.

Nothing here calls a model, clones anything or opens a socket: both branches
are replaced at the seam `main.run` calls them through, and any attempt to
start a process fails the test.
"""

from pathlib import Path

import pytest

import compare_run
import main
import pipeline
from cli_helpers import forbid_subprocesses
from reporting import progress

APP = "demo-app"
URL = "https://example.invalid/owner/demo-app"
CLOUD_MODEL = "vendor/some-hosted-model"

# The local arm's result, in the shape `audit_run.audit` returns and every
# caller of `main.run` reads. The wrapper subscripts all four.
LOCAL_RESULT_KEYS = ("app", "artifacts", "seconds", "advisories_read")
RUN_SECONDS = 9.75


def local_arm_result(artifacts_dir: Path) -> dict:
    """What the comparison's local arm hands back, by the keys the callers read."""
    return {"app": APP, "artifacts": artifacts_dir / APP,
            "seconds": RUN_SECONDS, "advisories_read": False}


def stub_the_comparison(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Replace the two-arm run with a recorder that answers as the local arm does."""
    calls: list[tuple] = []

    def fake_compare(repo_path: str, artifacts_dir: Path, cloud_model: str | None) -> dict:
        """Record what the command line asked for, and audit nothing at all."""
        calls.append((repo_path, artifacts_dir, cloud_model))
        return local_arm_result(artifacts_dir)

    monkeypatch.setattr(compare_run, "run", fake_compare)
    return calls


def stub_the_ordinary_audit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[Path]:
    """Replace the single-arm path at its own seams, so neither branch reaches a tool."""
    audited: list[Path] = []

    def fake_audit(app_dir: Path, artifacts_dir: Path, model: dict | None,
                   on_stage: progress.StageListener | None = None) -> dict:
        """Record the tree the ordinary path would have audited, and audit nothing."""
        audited.append(app_dir)
        return local_arm_result(artifacts_dir)

    # Both doubles spell the progress listener `main.run` threads down rather
    # than swallowing it with `*args`: the subject here is which branch ran, and
    # a double that accepted any arity would keep passing after a real caller
    # stopped matching the real signature. What the listener *receives* is
    # `tests/reporting/test_progress_stage.py`'s subject, not this file's.
    monkeypatch.setattr(pipeline, "resolve_repo",
                        lambda argument, on_stage=None: tmp_path)
    monkeypatch.setattr(main.audit_run, "report_pin_gap", lambda app_dir: None)
    monkeypatch.setattr(main.audit_run, "audit", fake_audit)
    return audited


def compare_through_the_command_line(monkeypatch: pytest.MonkeyPatch,
                                     tmp_path: Path) -> dict:
    """Parse `--compare-models` the way any caller would, and run it with both arms stubbed."""
    forbid_subprocesses(monkeypatch)
    stub_the_comparison(monkeypatch)
    stub_the_ordinary_audit(monkeypatch, tmp_path)
    return main.run(main.build_parser().parse_args(
        [URL, "--compare-models", "--cloud-model", CLOUD_MODEL]))


def test_the_comparison_branch_returns_a_result_and_not_an_exit_code(
        monkeypatch, tmp_path) -> None:
    """The bug in one line: an `int` here is a `TypeError` in the first caller that reads it."""
    produced = compare_through_the_command_line(monkeypatch, tmp_path)
    assert isinstance(produced, dict)


def test_the_result_carries_every_key_a_caller_reads(monkeypatch, tmp_path) -> None:
    """Named one by one, because `web/api.py` subscripts each of the four directly."""
    produced = compare_through_the_command_line(monkeypatch, tmp_path)
    for key in LOCAL_RESULT_KEYS:
        assert key in produced, key


def test_the_result_is_the_one_the_comparison_returned(monkeypatch, tmp_path) -> None:
    """Handed back unchanged: `main.run` adds nothing to this path and drops nothing."""
    produced = compare_through_the_command_line(monkeypatch, tmp_path)
    assert produced == local_arm_result(main.DEFAULT_ARTIFACTS_DIR)


def test_the_flag_carries_the_repository_and_the_hosted_model_across(
        monkeypatch, tmp_path) -> None:
    """Non-vacuity: the comparison really ran, over what the command line named."""
    forbid_subprocesses(monkeypatch)
    calls = stub_the_comparison(monkeypatch)
    stub_the_ordinary_audit(monkeypatch, tmp_path)
    main.run(main.build_parser().parse_args(
        [URL, "--compare-models", "--cloud-model", CLOUD_MODEL]))
    assert calls == [(URL, main.DEFAULT_ARTIFACTS_DIR, CLOUD_MODEL)]


def test_the_comparison_runs_instead_of_the_ordinary_audit(monkeypatch, tmp_path) -> None:
    """Two audits and a score, not a variation on one: the single-arm path is not walked."""
    forbid_subprocesses(monkeypatch)
    stub_the_comparison(monkeypatch)
    audited = stub_the_ordinary_audit(monkeypatch, tmp_path)
    main.run(main.build_parser().parse_args([URL, "--compare-models"]))
    assert audited == []


def test_an_audit_without_the_flag_never_reaches_the_comparison(monkeypatch,
                                                                tmp_path) -> None:
    """The other direction, and the one that matters: an unticked box uploads nothing."""
    forbid_subprocesses(monkeypatch)
    calls = stub_the_comparison(monkeypatch)
    audited = stub_the_ordinary_audit(monkeypatch, tmp_path)
    main.run(main.build_parser().parse_args([str(tmp_path)]))
    assert calls == []
    assert audited == [tmp_path]

"""What `run_baseline.py` writes, where it writes it, and what it refuses.

A baseline writes exactly the two files the scorer opens, into its own system
directory, so `evaluate.py` scores it unmodified and no system can overwrite
another's output. It takes a repository path the way `main.py` does, and the
artifact directory takes the tree's own name -- which is the key a grading key
is joined on, so an unsafe name is refused before it becomes a directory.

The repository is written into `tmp_path` by `write_tiny_app`, and Baseline B's
generator is answered from recorded output, so the test needs no Syft and no
tree on disk beforehand.
"""

import json
import sys
from pathlib import Path

import pytest

import evaluate
import run_baseline
from baseline_fixtures import EMPTY_SYFT_DOCUMENT, stub_syft, write_tiny_app
from evaluate_helpers import ARTIFACTS_DIR_NAME
from evaluation.document import SCORED_SYSTEMS

# A value outside the two baselines, shaped like the directory it would become.
UNKNOWN_SYSTEM = "../etc"

# The audited tree's directory name, which becomes the artifact directory name.
APP = "tiny-app"

# What the five rules match in `write_tiny_app`'s one file.
TINY_APP_FINDINGS = 5

# A directory name SAFE_NAME refuses: a leading dot is not a plain segment.
UNSAFE_APP = ".hidden"


def stage_repo(tmp_path: Path, name: str = APP) -> Path:
    """Write the tiny application under a chosen directory name and return its path."""
    repo = tmp_path / name
    repo.mkdir()
    write_tiny_app(repo)
    return repo


def run_cli(monkeypatch: pytest.MonkeyPatch, system: str, repo_path: Path,
            artifacts_dir: Path) -> int:
    """Run the entry point through argparse, the way a shell would."""
    monkeypatch.setattr(sys, "argv", [
        "run_baseline.py", system, str(repo_path), "--artifacts-dir", str(artifacts_dir)])
    return run_baseline.main()


def test_it_writes_both_artifacts_under_the_system_and_app_directories(
        tmp_path, monkeypatch) -> None:
    """`artifacts/<system>/<app>/` is what lets three systems be scored side by side."""
    repo = stage_repo(tmp_path)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    assert run_cli(monkeypatch, run_baseline.STATIC_RULES, repo, artifacts_dir) == 0
    written = artifacts_dir / run_baseline.STATIC_RULES / APP
    assert (written / run_baseline.FINDINGS_NAME).is_file()
    assert (written / run_baseline.SURFACES_NAME).is_file()


def test_the_artifact_directory_takes_the_audited_trees_own_name(tmp_path, monkeypatch) -> None:
    """That name is the only join key a grading key is looked up by, so it is asserted."""
    repo = stage_repo(tmp_path, "renamed-app")
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    assert run_cli(monkeypatch, run_baseline.STATIC_RULES, repo, artifacts_dir) == 0
    assert [path.name for path in (artifacts_dir / run_baseline.STATIC_RULES).iterdir()] \
        == ["renamed-app"]


def test_the_findings_it_writes_are_the_ones_the_rules_matched(tmp_path, monkeypatch) -> None:
    """The file is the artifact the scorer reads, so its contents are asserted, not its name."""
    repo = stage_repo(tmp_path)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    run_cli(monkeypatch, run_baseline.STATIC_RULES, repo, artifacts_dir)
    document = json.loads((artifacts_dir / run_baseline.STATIC_RULES / APP /
                           run_baseline.FINDINGS_NAME).read_text(encoding="utf-8"))
    assert document["finding_count"] == TINY_APP_FINDINGS


def test_the_two_files_it_writes_agree_with_each_other(tmp_path, monkeypatch) -> None:
    """Surfaces derived from the findings, so the pair can never contradict itself."""
    repo = stage_repo(tmp_path)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    run_cli(monkeypatch, run_baseline.STATIC_RULES, repo, artifacts_dir)
    written = artifacts_dir / run_baseline.STATIC_RULES / APP
    findings = json.loads((written / run_baseline.FINDINGS_NAME).read_text(encoding="utf-8"))
    surfaces = json.loads((written / run_baseline.SURFACES_NAME).read_text(encoding="utf-8"))
    assert ({s["id"] for s in surfaces["surfaces"]}
            == {f["surface_id"] for f in findings["findings"]})


def test_the_sbom_baseline_writes_an_empty_surfaces_file(tmp_path, monkeypatch) -> None:
    """It has no surface model, and the file must exist anyway: the scorer opens it."""
    repo = stage_repo(tmp_path)
    stub_syft(monkeypatch, EMPTY_SYFT_DOCUMENT)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    assert run_cli(monkeypatch, run_baseline.SBOM_ONLY, repo, artifacts_dir) == 0
    surfaces = json.loads((artifacts_dir / run_baseline.SBOM_ONLY / APP /
                           run_baseline.SURFACES_NAME).read_text(encoding="utf-8"))
    assert surfaces["surfaces"] == []


def test_running_one_baseline_leaves_the_others_output_alone(tmp_path, monkeypatch) -> None:
    """Two systems, two directories: the reason the system segment exists at all."""
    repo = stage_repo(tmp_path)
    stub_syft(monkeypatch, EMPTY_SYFT_DOCUMENT)
    artifacts_dir = tmp_path / ARTIFACTS_DIR_NAME
    run_cli(monkeypatch, run_baseline.STATIC_RULES, repo, artifacts_dir)
    run_cli(monkeypatch, run_baseline.SBOM_ONLY, repo, artifacts_dir)
    for system in run_baseline.BASELINES:
        assert (artifacts_dir / system / APP / run_baseline.FINDINGS_NAME).is_file()


def test_a_system_outside_the_two_baselines_is_rejected(tmp_path, monkeypatch) -> None:
    """The value becomes a directory name, so argparse rejects it before a path is built."""
    with pytest.raises(SystemExit) as raised:
        run_cli(monkeypatch, UNKNOWN_SYSTEM, stage_repo(tmp_path),
                tmp_path / ARTIFACTS_DIR_NAME)
    assert raised.value.code == 2


def test_the_rejected_system_is_never_created_as_a_directory(tmp_path, monkeypatch) -> None:
    """An unvalidated string would land in the filesystem, so nothing may be written first."""
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, UNKNOWN_SYSTEM, stage_repo(tmp_path),
                tmp_path / ARTIFACTS_DIR_NAME)
    assert not (tmp_path / ARTIFACTS_DIR_NAME).exists()


def test_a_repository_path_that_is_not_a_directory_exits_one(tmp_path, monkeypatch) -> None:
    """No source on disk is a refusal, not an app run over nothing and reported as clean."""
    assert run_cli(monkeypatch, run_baseline.STATIC_RULES, tmp_path / "absent",
                   tmp_path / ARTIFACTS_DIR_NAME) == 1


def test_the_refusal_names_the_path_it_could_not_read(tmp_path, monkeypatch, capsys) -> None:
    """One line naming the directory, rather than a traceback."""
    missing = tmp_path / "absent"
    run_cli(monkeypatch, run_baseline.STATIC_RULES, missing, tmp_path / ARTIFACTS_DIR_NAME)
    assert f"cannot read {missing}: not a directory" in capsys.readouterr().err


def test_nothing_is_written_when_the_repository_is_missing(tmp_path, monkeypatch) -> None:
    """A partial run would be scored as a complete one, so it must write no artifact at all."""
    run_cli(monkeypatch, run_baseline.STATIC_RULES, tmp_path / "absent",
            tmp_path / ARTIFACTS_DIR_NAME)
    assert not (tmp_path / ARTIFACTS_DIR_NAME).exists()


def test_a_tree_whose_name_is_not_a_plain_segment_is_refused(tmp_path, monkeypatch) -> None:
    """The name becomes a directory and a join key, so a dotted one must not reach either."""
    repo = stage_repo(tmp_path, UNSAFE_APP)
    assert run_cli(monkeypatch, run_baseline.STATIC_RULES, repo,
                   tmp_path / ARTIFACTS_DIR_NAME) == 1


def test_the_unsafe_name_refusal_says_what_it_derived(tmp_path, monkeypatch, capsys) -> None:
    """It quotes the name it rejected, so the fix is to rename the tree, not to guess."""
    repo = stage_repo(tmp_path, UNSAFE_APP)
    run_cli(monkeypatch, run_baseline.STATIC_RULES, repo, tmp_path / ARTIFACTS_DIR_NAME)
    assert f"got {UNSAFE_APP!r}" in capsys.readouterr().err


def test_nothing_is_written_when_the_name_is_refused(tmp_path, monkeypatch) -> None:
    """The refusal comes before the directory is made, or the guard would be decorative."""
    repo = stage_repo(tmp_path, UNSAFE_APP)
    run_cli(monkeypatch, run_baseline.STATIC_RULES, repo, tmp_path / ARTIFACTS_DIR_NAME)
    assert not (tmp_path / ARTIFACTS_DIR_NAME).exists()


def test_the_filesystem_root_has_no_name_to_derive() -> None:
    """`/` resolves to an empty name, which is the other way the derivation can fail."""
    with pytest.raises(ValueError, match="not a single plain path segment"):
        run_baseline.app_name(Path("/"))


def test_a_plain_directory_name_is_accepted(tmp_path) -> None:
    """Guard: the two refusals above mean nothing if every name were refused."""
    assert run_baseline.app_name(stage_repo(tmp_path)) == APP


@pytest.mark.parametrize("system", run_baseline.BASELINES)
def test_every_baseline_is_a_system_the_scorer_knows(system: str) -> None:
    """A baseline the harness cannot name could be run but never scored."""
    assert system in SCORED_SYSTEMS


@pytest.mark.parametrize("system", run_baseline.BASELINES)
def test_every_baseline_is_accepted_by_the_parser(system: str) -> None:
    """The vocabulary is `BASELINES` itself, so adding one needs no edit here."""
    assert run_baseline.build_parser().parse_args([system, "."]).system == system


def test_the_default_artifacts_directory_is_the_one_the_scorer_reads() -> None:
    """`run_baseline` writes `<dir>/<system>/<app>/`, which is where `evaluate` looks."""
    assert run_baseline.DEFAULT_ARTIFACTS_DIR == evaluate.DEFAULT_ARTIFACTS_DIR

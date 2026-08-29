"""What each baseline opens during a real run, watched rather than argued from source.

`test_baseline_isolation.py` reads the modules; this file runs them over a
repository that has the auditor's six artifacts planted inside it and records
every file opened. A baseline that quietly grew a fallback to `sbom.json` would
pass a source check that only looks for a literal path built at runtime.

Baseline B in particular must call Syft itself: the auditor's `sbom.json`
carries `build_sbom`'s `declared` and `version_source` judgements, which are
this project's own work and off-limits here.
"""

import builtins
from pathlib import Path

import pytest

from baseline_fixtures import (
    EMPTY_SYFT_DOCUMENT,
    TINY_APP_FILE,
    stub_syft,
    write_tiny_app,
)
from baselines import sbom_only, static_rules
from deps import syft_runner
from test_baseline_isolation import PROJECT_ARTIFACTS

# Where the auditor writes its artifacts, staged as a decoy inside the scanned tree.
AUDITOR_ARTIFACTS_DIR = "artifacts/agentic_auditor/app"
DECOY_CONTENT = '{"surfaces": [{"file": "planted.py", "line": 1}]}'

GENERATOR_FAILURE = "syft is not installed"


def record_opened_files(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record every path opened while a baseline runs, so a real read cannot hide."""
    opened: list[Path] = []
    real_read_text, real_open = Path.read_text, builtins.open

    def read_text(self: Path, *args, **kwargs) -> str:
        opened.append(Path(self))
        return real_read_text(self, *args, **kwargs)

    def opener(file, *args, **kwargs):
        opened.append(Path(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(builtins, "open", opener)
    return opened


def stage_decoy_artifacts(root: Path) -> None:
    """Write the auditor's artifacts inside the scanned tree, for a baseline to ignore."""
    directory = root / AUDITOR_ARTIFACTS_DIR
    directory.mkdir(parents=True)
    for artifact in PROJECT_ARTIFACTS:
        (directory / artifact).write_text(DECOY_CONTENT, encoding="utf-8")


def opened_artifacts(opened: list[Path]) -> list[str]:
    """Return the names of any project artifact that was opened."""
    return sorted(path.name for path in opened if path.name in PROJECT_ARTIFACTS)


def test_the_recorder_sees_the_files_a_baseline_really_reads(monkeypatch, tmp_path: Path) -> None:
    """Guard: the tests below say nothing if the recorder caught no read at all."""
    write_tiny_app(tmp_path)
    opened = record_opened_files(monkeypatch)
    static_rules.scan_repo(str(tmp_path))
    assert TINY_APP_FILE in {path.name for path in opened}


def test_baseline_a_opens_no_artifact_even_when_one_sits_in_the_tree(
        monkeypatch, tmp_path: Path) -> None:
    """A real run over a repository holding all six: it reads source text and nothing else."""
    write_tiny_app(tmp_path)
    stage_decoy_artifacts(tmp_path)
    opened = record_opened_files(monkeypatch)
    assert static_rules.scan_repo(str(tmp_path))
    assert opened_artifacts(opened) == []


def test_baseline_b_opens_no_artifact_and_asks_the_generator_instead(
        monkeypatch, tmp_path: Path) -> None:
    """The decoy SBOM is right there; the components still come from Syft."""
    stage_decoy_artifacts(tmp_path)
    asked = stub_syft(monkeypatch, EMPTY_SYFT_DOCUMENT)
    opened = record_opened_files(monkeypatch)
    sbom_only.scan_repo(str(tmp_path))
    assert asked == [tmp_path]
    assert opened_artifacts(opened) == []


def test_baseline_b_calls_the_generator_it_is_a_baseline_for() -> None:
    """The module talks to Syft itself rather than to anything this project wrote."""
    assert sbom_only.syft_runner is syft_runner


def test_baseline_b_has_no_fallback_to_a_file_when_the_generator_fails(
        monkeypatch, tmp_path: Path) -> None:
    """With Syft refusing, there is no bill of materials -- not one read off disk."""
    stage_decoy_artifacts(tmp_path)

    def fail(_app_dir: Path) -> dict:
        raise RuntimeError(GENERATOR_FAILURE)

    monkeypatch.setattr(sbom_only.syft_runner, "scan", fail)
    with pytest.raises(RuntimeError, match=GENERATOR_FAILURE):
        sbom_only.scan_repo(str(tmp_path))

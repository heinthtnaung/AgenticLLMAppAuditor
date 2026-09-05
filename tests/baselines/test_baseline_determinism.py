"""Both baselines write byte-identical artifacts across two runs.

The same guarantee every other artifact in this project makes: a diff must mean
the result changed, never that the tool was run twice. Baseline B is the
interesting case -- it shells out to Syft, whose document carries a fresh UUID
and a fresh timestamp on every run. It reads `type`, `name` and `version` and
nothing else, so neither reaches the artifact; that is proved here against two
real Syft scans rather than argued from the source.

**The tree is written by the test.** It used to be the pinned corpus, which was
removed; so the inputs were chosen by the same author as the code, and what
that gives up is real -- no oversized file, no non-UTF-8 source, no unforeseen
code shape, and no walk wide enough for file ordering to matter much. What
survives is the contract itself: two runs, one set of bytes.
"""

from pathlib import Path

import pytest

from baseline_fixtures import (
    QUIET_FILE,
    QUIET_SOURCE,
    require_syft,
    write_tiny_app,
)
from deps import syft_runner
from run_baseline import SBOM_ONLY, STATIC_RULES, build_documents

# The two fields Syft varies from run to run, neither of which this baseline reads.
SERIAL_NUMBER = "serialNumber"
TIMESTAMP = "timestamp"

# A manifest Syft really reads, so Baseline B has components to report rather
# than an empty document that would be identical for uninteresting reasons.
REQUIREMENTS = "requirements.txt"
REQUIREMENTS_SOURCE = "langchain==0.3.25\nopenai==1.78.0\n"
DECLARED_COMPONENTS = 2

# What Baseline A's rules match in the tiny app: one finding per rule.
TINY_APP_FINDINGS = 5


def write_repo(tmp_path: Path) -> Path:
    """Write a repository with several files to walk and a manifest Syft can read."""
    repo = tmp_path / "determinism-app"
    repo.mkdir()
    write_tiny_app(repo)
    (repo / QUIET_FILE).write_text(QUIET_SOURCE, encoding="utf-8")
    (repo / REQUIREMENTS).write_text(REQUIREMENTS_SOURCE, encoding="utf-8")
    return repo


def built_twice(system: str, repo: Path) -> tuple[tuple[str, str], tuple[str, str]]:
    """Build one baseline's artifacts twice over the same tree."""
    return build_documents(system, str(repo)), build_documents(system, str(repo))


def test_baseline_a_reports_something_to_be_deterministic_about(tmp_path) -> None:
    """Guard: identical bytes prove nothing if the artifact is empty both times."""
    findings, _ = build_documents(STATIC_RULES, str(write_repo(tmp_path)))
    assert f'"finding_count": {TINY_APP_FINDINGS}' in findings


def test_baseline_a_writes_the_same_bytes_twice(tmp_path) -> None:
    """Text matching is deterministic, and the artifact must not depend on walk order."""
    first, second = built_twice(STATIC_RULES, write_repo(tmp_path))
    assert first == second


def test_baseline_b_reports_something_to_be_deterministic_about(tmp_path) -> None:
    """Guard: the manifest below really is read, so the identical bytes are not empty ones."""
    require_syft()
    findings, _ = build_documents(SBOM_ONLY, str(write_repo(tmp_path)))
    assert f'"finding_count": {DECLARED_COMPONENTS}' in findings


def test_baseline_b_writes_the_same_bytes_twice(tmp_path) -> None:
    """Two real Syft runs, two identical artifacts: nothing volatile survives the read."""
    require_syft()
    first, second = built_twice(SBOM_ONLY, write_repo(tmp_path))
    assert first == second


def test_two_real_syft_runs_do_differ_from_each_other(tmp_path) -> None:
    """Guard: without this the test above could pass on output that never varies.

    The UUID is fresh every run. The timestamp is only asserted to be present:
    it has one-second resolution, so two back-to-back scans can honestly share
    it, and a test demanding otherwise would fail on a fast machine.
    """
    require_syft()
    repo = write_repo(tmp_path)
    first, second = syft_runner.scan(repo), syft_runner.scan(repo)
    assert first[SERIAL_NUMBER] != second[SERIAL_NUMBER]
    assert first["metadata"][TIMESTAMP] and second["metadata"][TIMESTAMP]


def test_neither_the_uuid_nor_the_timestamp_reaches_the_artifact(tmp_path) -> None:
    """The two volatile fields are absent from the findings text, not merely equal across runs."""
    require_syft()
    repo = write_repo(tmp_path)
    document = syft_runner.scan(repo)
    findings, _ = build_documents(SBOM_ONLY, str(repo))
    assert document[SERIAL_NUMBER] not in findings
    assert document["metadata"][TIMESTAMP] not in findings


def test_the_absolute_scan_path_never_reaches_the_artifact(tmp_path) -> None:
    """A tmp_path-derived tree makes this visible: the artifact must not carry where it ran."""
    require_syft()
    repo = write_repo(tmp_path)
    findings, surfaces = build_documents(SBOM_ONLY, str(repo))
    assert str(repo) not in findings and str(repo) not in surfaces


@pytest.mark.parametrize("system", (STATIC_RULES, SBOM_ONLY))
def test_a_second_tree_at_a_different_path_gives_the_same_bytes(system, tmp_path) -> None:
    """The artifact depends on the source, not on where the source happens to sit."""
    require_syft()
    here, there = tmp_path / "here", tmp_path / "there"
    here.mkdir()
    there.mkdir()
    assert build_documents(system, str(write_repo(here))) == \
        build_documents(system, str(write_repo(there)))

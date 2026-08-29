"""Both baselines write byte-identical artifacts across two runs, per app.

The same guarantee every other artifact in this project makes: a diff must mean
the result changed, never that the tool was run twice. Baseline B is the
interesting case -- it shells out to Syft, whose document carries a fresh UUID
and a fresh timestamp on every run. It reads `type`, `name` and `version` and
nothing else, so neither reaches the artifact; that is proved here against two
real scans rather than argued from the source.
"""

import pytest

from baseline_fixtures import require_syft
from conftest import CORPUS_APPS, app_path, require_corpus
from dependency_fixtures import SUPPORT_AGENT
from deps import syft_runner
from run_baseline import SBOM_ONLY, STATIC_RULES, build_documents

# The two fields Syft varies from run to run, neither of which this baseline reads.
SERIAL_NUMBER = "serialNumber"
TIMESTAMP = "timestamp"


def built_twice(system: str, app: str) -> tuple[tuple[str, str], tuple[str, str]]:
    """Build one baseline's artifacts twice over the same app."""
    repo_path = str(app_path(app))
    return build_documents(system, repo_path), build_documents(system, repo_path)


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_baseline_a_writes_the_same_bytes_twice(app: str) -> None:
    """Text matching is deterministic, and the artifact must not depend on walk order."""
    require_corpus(app)
    first, second = built_twice(STATIC_RULES, app)
    assert first == second


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_baseline_b_writes_the_same_bytes_twice(app: str) -> None:
    """Two real Syft runs, two identical artifacts: nothing volatile survives the read."""
    require_corpus(app)
    require_syft()
    first, second = built_twice(SBOM_ONLY, app)
    assert first == second


def test_two_real_syft_runs_do_differ_from_each_other() -> None:
    """Guard: without this the test above could pass on output that never varies.

    The UUID is fresh every run. The timestamp is only asserted to be present:
    it has one-second resolution, so two back-to-back scans can honestly share
    it, and a test demanding otherwise would fail on a fast machine.
    """
    require_corpus(SUPPORT_AGENT)
    require_syft()
    directory = app_path(SUPPORT_AGENT)
    first, second = syft_runner.scan(directory), syft_runner.scan(directory)
    assert first[SERIAL_NUMBER] != second[SERIAL_NUMBER]
    assert first["metadata"][TIMESTAMP] and second["metadata"][TIMESTAMP]


def test_neither_the_uuid_nor_the_timestamp_reaches_the_artifact() -> None:
    """The two volatile fields are absent from the findings text, not merely equal across runs."""
    require_corpus(SUPPORT_AGENT)
    require_syft()
    document = syft_runner.scan(app_path(SUPPORT_AGENT))
    findings, _ = build_documents(SBOM_ONLY, str(app_path(SUPPORT_AGENT)))
    assert document[SERIAL_NUMBER] not in findings
    assert document["metadata"][TIMESTAMP] not in findings

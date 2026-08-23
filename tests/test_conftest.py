"""Demo-app discovery: the suite finds its grading fixtures on disk, or refuses to run."""

from pathlib import Path

import pytest
from conftest import CORPUS_DIR, DEMO_APPS, GROUND_TRUTH_NAME, discover_demo_apps

# The two deliberately vulnerable demo apps that must be present under corpus/.
EXPECTED_DEMO_APPS = ("vuln-app-1-support-agent", "vuln-app-2-broken-integration")


def make_app(corpus_dir: Path, name: str) -> Path:
    """Create a fake corpus app directory holding an empty ground_truth.json."""
    app_dir = corpus_dir / name
    app_dir.mkdir(parents=True)
    (app_dir / GROUND_TRUTH_NAME).write_text("{}", encoding="utf-8")
    return app_dir


def test_finds_both_real_demo_apps() -> None:
    """Against the real corpus, discovery returns exactly the two demo apps."""
    assert discover_demo_apps() == EXPECTED_DEMO_APPS


def test_demo_apps_constant_is_the_discovered_set() -> None:
    """The DEMO_APPS the whole suite parametrises over is what discovery found."""
    assert DEMO_APPS == discover_demo_apps(CORPUS_DIR)


def test_result_is_a_tuple() -> None:
    """The result is an immutable tuple, so no test can mutate the shared fixture list."""
    assert isinstance(discover_demo_apps(), tuple)


def test_result_is_sorted(tmp_path: Path) -> None:
    """Names come back sorted, so test ids are stable whatever order the disk gives."""
    for name in ("zebra-app", "alpha-app", "middle-app"):
        make_app(tmp_path, name)
    assert discover_demo_apps(tmp_path) == ("alpha-app", "middle-app", "zebra-app")


def test_finds_every_app_in_a_fabricated_corpus(tmp_path: Path) -> None:
    """Three apps are all discovered, proving a new app needs no edit to conftest."""
    for name in ("app-one", "app-two", "app-three"):
        make_app(tmp_path, name)
    assert len(discover_demo_apps(tmp_path)) == 3


def test_directory_without_ground_truth_is_ignored(tmp_path: Path) -> None:
    """A folder with no ground_truth.json is not a grading fixture and is skipped."""
    make_app(tmp_path, "real-app")
    (tmp_path / "not-an-app").mkdir()
    assert discover_demo_apps(tmp_path) == ("real-app",)


def test_empty_corpus_raises_runtime_error(tmp_path: Path) -> None:
    """An empty corpus stops the suite instead of letting it pass while testing nothing."""
    with pytest.raises(RuntimeError) as error:
        discover_demo_apps(tmp_path)
    assert GROUND_TRUTH_NAME in str(error.value)


def test_empty_corpus_error_names_the_directory_searched(tmp_path: Path) -> None:
    """The failure says where it looked, so a wrong path is obvious from the message."""
    with pytest.raises(RuntimeError) as error:
        discover_demo_apps(tmp_path)
    assert str(tmp_path) in str(error.value)


def test_missing_corpus_directory_raises_runtime_error(tmp_path: Path) -> None:
    """A corpus path that does not exist fails the same clear way as an empty one."""
    with pytest.raises(RuntimeError):
        discover_demo_apps(tmp_path / "no-such-corpus")

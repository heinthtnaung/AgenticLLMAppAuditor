"""Corpus discovery: the suite finds its grading fixtures on disk, or refuses to run."""

from pathlib import Path

import pytest
from conftest import (
    CORPUS_APPS,
    CORPUS_DIR,
    EVIDENCE_DIR,
    GROUND_TRUTH_SUFFIX,
    MANIFEST_SUFFIX,
    app_is_present,
    discover_corpus_apps,
)

# The fixtures that must be present under corpus/, in discovery order. One
# carries planted vulnerabilities and measures recall; the other two are clean
# upstream starters, which are what can measure false positives -- one
# TypeScript, one Python, because the taint trace only reads Python and a
# false-positive number from a language it cannot parse says little.
EXPECTED_CORPUS_APPS = (
    "oss-app-langgraphjs-starter",
    "oss-app-react-agent",
    "vuln-app-1-support-agent",
)


def make_app(corpus_dir: Path, name: str) -> Path:
    """Create a fake fixture: audited code, plus its evidence kept apart from it."""
    app_dir = corpus_dir / name
    app_dir.mkdir(parents=True)
    evidence = corpus_dir / "evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / f"{name}{GROUND_TRUTH_SUFFIX}").write_text("{}", encoding="utf-8")
    (evidence / f"{name}{MANIFEST_SUFFIX}").write_text("{}", encoding="utf-8")
    return app_dir


def test_finds_every_real_corpus_app() -> None:
    """Against the real corpus, discovery returns exactly the audited fixtures."""
    assert discover_corpus_apps() == EXPECTED_CORPUS_APPS


def test_corpus_apps_constant_is_the_discovered_set() -> None:
    """The CORPUS_APPS the whole suite parametrises over is what discovery found."""
    assert CORPUS_APPS == discover_corpus_apps(CORPUS_DIR)


def test_result_is_a_tuple() -> None:
    """The result is an immutable tuple, so no test can mutate the shared fixture list."""
    assert isinstance(discover_corpus_apps(), tuple)


def test_result_is_sorted(tmp_path: Path) -> None:
    """Names come back sorted, so test ids are stable whatever order the disk gives."""
    for name in ("zebra-app", "alpha-app", "middle-app"):
        make_app(tmp_path, name)
    assert discover_corpus_apps(tmp_path) == ("alpha-app", "middle-app", "zebra-app")


def test_finds_every_app_in_a_fabricated_corpus(tmp_path: Path) -> None:
    """Three apps are all discovered, proving a new app needs no edit to conftest."""
    for name in ("app-one", "app-two", "app-three"):
        make_app(tmp_path, name)
    assert len(discover_corpus_apps(tmp_path)) == 3


def test_directory_without_ground_truth_is_ignored(tmp_path: Path) -> None:
    """A folder with no ground_truth.json is not a grading fixture and is skipped."""
    make_app(tmp_path, "real-app")
    (tmp_path / "not-an-app").mkdir()
    assert discover_corpus_apps(tmp_path) == ("real-app",)


def test_empty_corpus_raises_runtime_error(tmp_path: Path) -> None:
    """An empty corpus stops the suite instead of letting it pass while testing nothing."""
    with pytest.raises(RuntimeError) as error:
        discover_corpus_apps(tmp_path)
    assert GROUND_TRUTH_SUFFIX in str(error.value)


def test_empty_corpus_error_names_the_directory_searched(tmp_path: Path) -> None:
    """The failure says where it looked, so a wrong path is obvious from the message."""
    with pytest.raises(RuntimeError) as error:
        discover_corpus_apps(tmp_path)
    assert str(tmp_path) in str(error.value)


def test_missing_corpus_directory_raises_runtime_error(tmp_path: Path) -> None:
    """A corpus path that does not exist fails the same clear way as an empty one."""
    with pytest.raises(RuntimeError):
        discover_corpus_apps(tmp_path / "no-such-corpus")


def test_downloaded_repo_is_not_mistaken_for_a_fixture(tmp_path: Path) -> None:
    """A downloaded repo keeps its manifest outside itself, so it can never be graded.

    Discovery never looks inside an app directory, so a repository cannot enrol
    itself by shipping a file of the right name.
    """
    make_app(tmp_path, "real-app")
    downloaded = tmp_path / "someones-repo"
    downloaded.mkdir()
    (downloaded / "ground_truth.json").write_text("{}", encoding="utf-8")
    assert discover_corpus_apps(tmp_path) == ("real-app",)


EVIDENCE_FILE_NAMES = ("ground_truth.json", "MANIFEST.json", "manifest.json", "extracted_baseline.json")


def test_no_evidence_file_hides_inside_an_audited_app() -> None:
    """corpus/<app>/ is a pristine upstream copy, so none of our files may live there.

    If one did, a stale reader joining CORPUS_DIR / app / "ground_truth.json"
    would read it and grade against upstream's file with no error at all -- the
    one way this layout can fail quietly.
    """
    strays = [
        path
        for app in CORPUS_APPS
        for name in EVIDENCE_FILE_NAMES
        if (path := CORPUS_DIR / app / name).exists()
    ]
    assert strays == [], f"evidence must live in {EVIDENCE_DIR}, found: {strays}"


def test_a_fixture_is_known_before_its_code_is_downloaded(tmp_path: Path) -> None:
    """App source is not committed, so a known fixture may legitimately have no code yet."""
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    for suffix in (GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX):
        (evidence / f"not-downloaded{suffix}").write_text("{}", encoding="utf-8")
    assert discover_corpus_apps(tmp_path) == ("not-downloaded",)
    assert app_is_present("not-downloaded", tmp_path) is False


def test_grading_key_without_a_manifest_is_rejected(tmp_path: Path) -> None:
    """An unpinned fixture is refused: its line numbers would mean nothing."""
    (tmp_path / "unpinned").mkdir()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / f"unpinned{GROUND_TRUTH_SUFFIX}").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unpinned"):
        discover_corpus_apps(tmp_path)


def test_an_app_named_evidence_is_rejected(tmp_path: Path) -> None:
    """corpus/evidence holds evidence, so no audited app may claim that name."""
    make_app(tmp_path, "evidence")
    with pytest.raises(RuntimeError, match="reserved"):
        discover_corpus_apps(tmp_path)

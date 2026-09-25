"""Guards on the refusals: a run that cannot be trusted does not start."""

import json

import pytest

from cli.preflight import CannotRun, refuse_unrunnable
from deps import syft_runner, trivy_runner
from deps.trivy_database import DatedDatabase

BUILT_AT = "2026-09-22T02:00:05Z"


def written_cache(tmp_path, metadata: str):
    """Lay out a Trivy cache whose database metadata holds exactly the given text."""
    cache = tmp_path / "trivy-cache"
    (cache / "db").mkdir(parents=True)
    (cache / "db" / "metadata.json").write_text(metadata, encoding="utf-8")
    return cache


@pytest.fixture
def cache(tmp_path):
    """Lay out a Trivy cache holding a database, the way Trivy writes one."""
    return written_cache(tmp_path, json.dumps({"UpdatedAt": BUILT_AT}))


@pytest.fixture
def scanners_installed(monkeypatch):
    """Say both scanners are here, so a test can be about something else."""
    monkeypatch.setattr(syft_runner, "is_available", lambda: True)
    monkeypatch.setattr(trivy_runner, "is_available", lambda: True)


def test_a_runnable_audit_gives_back_the_cache_it_dated_and_the_date(
    tmp_path, cache, scanners_installed
):
    # The cache handed back is the one the scan is given, so what was dated is
    # what is scanned.
    assert refuse_unrunnable(tmp_path, cache) == DatedDatabase(cache=cache, built_at=BUILT_AT)


def test_a_path_that_is_not_a_directory_is_refused(tmp_path, cache, scanners_installed):
    with pytest.raises(CannotRun, match="is not a directory to audit"):
        refuse_unrunnable(tmp_path / "nowhere", cache)


@pytest.mark.parametrize("absent", ["syft", "trivy"])
def test_a_missing_scanner_is_refused_rather_than_reported_as_nothing_found(
    tmp_path, cache, monkeypatch, absent
):
    # No scanner and no findings look identical in a report.
    monkeypatch.setattr(syft_runner, "is_available", lambda: absent != "syft")
    monkeypatch.setattr(trivy_runner, "is_available", lambda: absent != "trivy")
    with pytest.raises(CannotRun, match=f"{absent} is not installed"):
        refuse_unrunnable(tmp_path, cache)


def test_both_missing_scanners_are_named_at_once(tmp_path, cache, monkeypatch):
    monkeypatch.setattr(syft_runner, "is_available", lambda: False)
    monkeypatch.setattr(trivy_runner, "is_available", lambda: False)
    with pytest.raises(CannotRun, match="syft, trivy is not installed"):
        refuse_unrunnable(tmp_path, cache)


def test_a_missing_database_stops_the_run_before_it_can_look_clean(
    tmp_path, scanners_installed
):
    # Trivy with no database finds nothing and exits 0. By the time a report is
    # written the damage is done, because the report is believable.
    with pytest.raises(CannotRun, match="reads exactly like a clean repository"):
        refuse_unrunnable(tmp_path, tmp_path / "no-cache")


@pytest.mark.parametrize(
    "written", ["{}", '{"UpdatedAt": ""}', "not json at all"],
    ids=["no date", "empty date", "unreadable"],
)
def test_a_database_that_says_nothing_useful_is_the_same_as_none(
    tmp_path, scanners_installed, written
):
    with pytest.raises(CannotRun, match="no advisory database build date"):
        refuse_unrunnable(tmp_path, written_cache(tmp_path, written))


def test_the_repository_is_checked_before_the_scanners_are(tmp_path, cache, monkeypatch):
    # The cheapest refusal first: a typo in a path should not wait on a PATH walk.
    monkeypatch.setattr(syft_runner, "is_available", lambda: False)
    with pytest.raises(CannotRun, match="is not a directory"):
        refuse_unrunnable(tmp_path / "nowhere", cache)

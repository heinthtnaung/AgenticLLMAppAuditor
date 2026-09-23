"""Guards on the refusals: a run that cannot be trusted does not start."""

import json

import pytest

from cli.preflight import CannotRun, refuse_unrunnable
from deps import syft_runner, trivy_runner

BUILT_AT = "2026-09-22T02:00:05Z"


@pytest.fixture
def database(tmp_path):
    """Write a database metadata file the way Trivy writes one."""
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"UpdatedAt": BUILT_AT}), encoding="utf-8")
    return metadata


@pytest.fixture
def scanners_installed(monkeypatch):
    """Say both scanners are here, so a test can be about something else."""
    monkeypatch.setattr(syft_runner, "is_available", lambda: True)
    monkeypatch.setattr(trivy_runner, "is_available", lambda: True)


def test_a_runnable_audit_gives_back_the_database_date(tmp_path, database, scanners_installed):
    assert refuse_unrunnable(tmp_path, database) == BUILT_AT


def test_a_path_that_is_not_a_directory_is_refused(tmp_path, database, scanners_installed):
    with pytest.raises(CannotRun, match="is not a directory to audit"):
        refuse_unrunnable(tmp_path / "nowhere", database)


@pytest.mark.parametrize("absent", ["syft", "trivy"])
def test_a_missing_scanner_is_refused_rather_than_reported_as_nothing_found(
    tmp_path, database, monkeypatch, absent
):
    # No scanner and no findings look identical in a report.
    monkeypatch.setattr(syft_runner, "is_available", lambda: absent != "syft")
    monkeypatch.setattr(trivy_runner, "is_available", lambda: absent != "trivy")
    with pytest.raises(CannotRun, match=f"{absent} is not installed"):
        refuse_unrunnable(tmp_path, database)


def test_both_missing_scanners_are_named_at_once(tmp_path, database, monkeypatch):
    monkeypatch.setattr(syft_runner, "is_available", lambda: False)
    monkeypatch.setattr(trivy_runner, "is_available", lambda: False)
    with pytest.raises(CannotRun, match="syft, trivy is not installed"):
        refuse_unrunnable(tmp_path, database)


def test_a_missing_database_stops_the_run_before_it_can_look_clean(
    tmp_path, scanners_installed
):
    # Trivy with no database finds nothing and exits 0. By the time a report is
    # written the damage is done, because the report is believable.
    with pytest.raises(CannotRun, match="reads exactly like a clean repository"):
        refuse_unrunnable(tmp_path, tmp_path / "no-metadata.json")


@pytest.mark.parametrize(
    "written", ["{}", '{"UpdatedAt": ""}', "not json at all"],
    ids=["no date", "empty date", "unreadable"],
)
def test_a_database_that_says_nothing_useful_is_the_same_as_none(
    tmp_path, scanners_installed, written
):
    metadata = tmp_path / "metadata.json"
    metadata.write_text(written, encoding="utf-8")
    with pytest.raises(CannotRun, match="no advisory database build date"):
        refuse_unrunnable(tmp_path, metadata)


def test_the_repository_is_checked_before_the_scanners_are(tmp_path, database, monkeypatch):
    # The cheapest refusal first: a typo in a path should not wait on a PATH walk.
    monkeypatch.setattr(syft_runner, "is_available", lambda: False)
    with pytest.raises(CannotRun, match="is not a directory"):
        refuse_unrunnable(tmp_path / "nowhere", database)

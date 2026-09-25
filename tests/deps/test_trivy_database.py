"""Guards on the advisory database's build date: the check that stops a silent clean report."""

import json
from pathlib import Path

import pytest

from deps.trivy_database import database_built_at, metadata_of, trivy_cache_directory
from samples import NOT_PATHS

# Written by Trivy 0.74.0 alongside a current database. `UpdatedAt` is when the
# database was built; `DownloadedAt` is only when this machine fetched it.
BUILT_AT = "2026-09-22T02:00:05.774028462Z"
REAL_METADATA = {
    "Version": 2,
    "NextUpdate": "2026-09-23T02:00:05.774027771Z",
    "UpdatedAt": BUILT_AT,
    "DownloadedAt": "2026-09-22T04:06:38.609232067Z",
}


def metadata_file(tmp_path: Path, content: str) -> Path:
    """Write a metadata file holding exactly the given text."""
    written = tmp_path / "metadata.json"
    written.write_text(content, encoding="utf-8")
    return written


def test_the_database_reports_the_date_it_was_built(tmp_path):
    assert database_built_at(metadata_file(tmp_path, json.dumps(REAL_METADATA))) == BUILT_AT


def test_the_download_time_is_never_reported_as_the_build_date(tmp_path):
    # A stale database copied here this morning is still stale; DownloadedAt would
    # call it fresh, and a scan against it would report a clean repository.
    built_at = database_built_at(metadata_file(tmp_path, json.dumps(REAL_METADATA)))
    assert built_at == BUILT_AT
    assert built_at != REAL_METADATA["DownloadedAt"]


def test_no_database_at_all_answers_none(tmp_path):
    assert database_built_at(tmp_path / "db" / "metadata.json") is None


def test_a_metadata_file_that_cannot_be_opened_answers_none(tmp_path):
    unopenable = tmp_path / "metadata.json"
    unopenable.mkdir()
    assert database_built_at(unopenable) is None


def test_a_corrupt_metadata_file_answers_none(tmp_path):
    truncated = metadata_file(tmp_path, '{"Version":2,"UpdatedAt":"2026-09-2')
    assert database_built_at(truncated) is None


def test_a_metadata_file_that_is_not_text_answers_none(tmp_path):
    binary = tmp_path / "metadata.json"
    binary.write_bytes(b"\xff\xfe\x00{")
    assert database_built_at(binary) is None


@pytest.mark.parametrize(
    "content",
    ['["UpdatedAt"]', '"2026-09-22T02:00:05Z"', "2026", "null"],
)
def test_metadata_that_is_valid_json_of_the_wrong_shape_answers_none(content, tmp_path):
    assert database_built_at(metadata_file(tmp_path, content)) is None


@pytest.mark.parametrize(
    "metadata",
    [
        {"Version": 2, "DownloadedAt": "2026-09-22T04:06:38Z"},
        {"UpdatedAt": None},
        {"UpdatedAt": 20260922},
        {"UpdatedAt": ""},
        {"UpdatedAt": "   "},
    ],
)
def test_metadata_with_no_usable_build_date_answers_none(metadata, tmp_path):
    assert database_built_at(metadata_file(tmp_path, json.dumps(metadata))) is None


def test_a_metadata_path_given_as_a_string_reads_the_same_file(tmp_path):
    written = metadata_file(tmp_path, json.dumps(REAL_METADATA))
    assert database_built_at(str(written)) == database_built_at(written) == BUILT_AT


@pytest.mark.parametrize("value, named", NOT_PATHS)
def test_a_metadata_path_that_is_no_kind_of_path_is_refused_by_its_type(value, named):
    # A path this cannot read answers None; a value that is no path at all is a
    # caller's fault and is said out loud.
    with pytest.raises(TypeError, match=f"must be a str or a Path, not {named}"):
        database_built_at(value)


HOME = "/home/someone"
# Trivy 0.74's order, measured with `trivy fs --debug`, which logs the cache dir.
UNDER_HOME = Path(HOME) / ".cache" / "trivy"


def test_with_nothing_set_the_cache_is_under_home():
    assert trivy_cache_directory({"HOME": HOME}) == UNDER_HOME


def test_xdg_cache_home_moves_the_cache(tmp_path):
    moved = {"HOME": HOME, "XDG_CACHE_HOME": str(tmp_path)}
    assert trivy_cache_directory(moved) == tmp_path / "trivy"


def test_trivy_cache_dir_outranks_xdg_cache_home(tmp_path):
    named = {"TRIVY_CACHE_DIR": str(tmp_path / "named"), "XDG_CACHE_HOME": str(tmp_path / "xdg")}
    assert trivy_cache_directory({"HOME": HOME, **named}) == tmp_path / "named"


@pytest.mark.parametrize("variable", ["TRIVY_CACHE_DIR", "XDG_CACHE_HOME"])
def test_a_variable_set_to_nothing_is_passed_over_as_trivy_passes_it_over(variable):
    assert trivy_cache_directory({"HOME": HOME, variable: ""}) == UNDER_HOME


def test_a_relative_trivy_cache_dir_is_where_the_run_starts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert trivy_cache_directory({"TRIVY_CACHE_DIR": "cache"}) == tmp_path / "cache"


def test_a_relative_xdg_cache_home_is_refused_because_trivy_would_leave_for_a_temporary_one():
    with pytest.raises(ValueError, match="'relative', which is relative"):
        trivy_cache_directory({"HOME": HOME, "XDG_CACHE_HOME": "relative"})


def test_with_no_variable_to_go_on_there_is_no_cache_and_the_run_is_refused():
    with pytest.raises(ValueError, match="no TRIVY_CACHE_DIR, XDG_CACHE_HOME or HOME is set"):
        trivy_cache_directory({})


def test_the_build_date_is_read_from_the_database_in_the_cache(tmp_path):
    cache = tmp_path / "cache"
    (cache / "db").mkdir(parents=True)
    (cache / "db" / "metadata.json").write_text(json.dumps(REAL_METADATA), encoding="utf-8")
    assert database_built_at(metadata_of(cache)) == BUILT_AT


def test_a_cache_dir_in_a_trivy_yaml_is_not_read(tmp_path, monkeypatch):
    # Accepted: the scan is handed the resolved cache as `--cache-dir`, which
    # outranks a trivy.yaml, so the file cannot move the database under it and is
    # not read. Reading it turns this red.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "trivy.yaml").write_text(f"cache:\n  dir: {tmp_path}/yaml\n", encoding="utf-8")
    assert trivy_cache_directory({"HOME": HOME}) == UNDER_HOME

"""Guards on the advisory database's build date: the check that stops a silent clean report."""

import json
from pathlib import Path

import pytest

from deps.trivy_database import DATABASE_METADATA_PATH, database_built_at
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


def test_the_database_is_looked_for_where_trivy_keeps_it():
    assert DATABASE_METADATA_PATH.parts[-4:] == (".cache", "trivy", "db", "metadata.json")

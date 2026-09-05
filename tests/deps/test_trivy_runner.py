"""The advisory runner's pure parts: the index, the pin, and the database date.

Nothing here runs Trivy -- reports are built by hand in its JSON shape, so the
suite never starts a subprocess and never depends on this machine having the
tool or its database. The launch and its offline flags are asserted in
test_advisory_launch.py; this file owns what the runner does with a report.
"""

import json

from advisory_fixtures import (
    ADVISORY_ID,
    ADVISORY_PURL,
    CVSS_SOURCE,
    CVSS_VECTOR,
    DB_UPDATED_AT,
    FIXED_VERSION,
    TRIVY_VERSION,
    advisory_record,
    trivy_report,
    trivy_vulnerability,
)
from deps.trivy_runner import GENERATOR_NAME, advisory_index, db_snapshot_date, pin

SECOND_ADVISORY = "GHSA-xxxx-yyyy-zzzz"
OTHER_PURL = "pkg:pypi/requests@2.31.0"


def test_the_index_is_keyed_by_the_versioned_purl() -> None:
    """The purl is the join key the mapping shares, so it is the index's key."""
    index = advisory_index(trivy_report(
        trivy_vulnerability(), trivy_vulnerability(vuln_id=SECOND_ADVISORY, purl=OTHER_PURL)))
    assert sorted(index) == sorted([ADVISORY_PURL, OTHER_PURL])


def test_a_record_is_renamed_into_the_projects_vocabulary() -> None:
    """Trivy's field names stop at the runner: the check never learns whose report it was."""
    index = advisory_index(trivy_report(trivy_vulnerability()))
    assert index[ADVISORY_PURL] == [advisory_record(
        ADVISORY_ID, FIXED_VERSION, CVSS_VECTOR, CVSS_SOURCE)]


def test_a_record_trivy_rated_with_no_word_carries_no_severity() -> None:
    """The other direction of the rename: absent in the report is null in the artifact."""
    index = advisory_index(trivy_report(trivy_vulnerability(severity=None)))
    assert index[ADVISORY_PURL][0]["advisory_severity"] is None
    # The vector is a separate field from the word, and it was still quoted.
    assert index[ADVISORY_PURL][0]["advisory_cvss_vector"] == CVSS_VECTOR


def test_records_are_sorted_by_advisory_id_whatever_the_scan_order() -> None:
    """Scan order must not reach the artifact, or two runs would differ."""
    index = advisory_index(trivy_report(
        trivy_vulnerability(vuln_id=SECOND_ADVISORY), trivy_vulnerability()))
    ids = [record["advisory_id"] for record in index[ADVISORY_PURL]]
    assert ids == sorted([ADVISORY_ID, SECOND_ADVISORY])


def test_trivys_empty_string_for_no_fix_becomes_null() -> None:
    """Trivy writes "" for "no fix published", so null has one spelling in the artifact."""
    index = advisory_index(trivy_report(trivy_vulnerability(fixed="")))
    assert index[ADVISORY_PURL][0]["advisory_fixed_version"] is None


def test_the_vector_is_quoted_from_the_severity_source_trivy_names() -> None:
    """Two sources disagree; the one Trivy itself names is the one quoted."""
    cvss = {"ghsa": {"V3Vector": "CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"},
            CVSS_SOURCE: {"V3Vector": CVSS_VECTOR}}
    index = advisory_index(trivy_report(trivy_vulnerability(source="ghsa", cvss=cvss)))
    record = index[ADVISORY_PURL][0]
    assert record["advisory_cvss_vector"] == cvss["ghsa"]["V3Vector"]
    assert record["advisory_cvss_source"] == "ghsa"


def test_a_source_with_no_vector_leaves_both_cvss_fields_null() -> None:
    """A source named beside no vector would be a citation with nothing behind it."""
    index = advisory_index(trivy_report(
        trivy_vulnerability(source="redhat", cvss={"redhat": {"V3Score": 5.5}})))
    record = index[ADVISORY_PURL][0]
    assert record["advisory_cvss_vector"] is None
    assert record["advisory_cvss_source"] is None


def test_a_record_without_a_purl_is_skipped() -> None:
    """No purl means no join key, so the record can never anchor a finding."""
    assert advisory_index(trivy_report(trivy_vulnerability(purl=None))) == {}


def test_an_empty_report_indexes_to_nothing() -> None:
    """A scan that matched nothing is a valid, empty index."""
    assert advisory_index({"Trivy": {"Version": TRIVY_VERSION}, "Results": []}) == {}


def test_the_pin_names_the_generator_its_version_and_the_database_date() -> None:
    """The three values that make "scanned for known vulnerabilities" a dated claim."""
    assert pin(trivy_report(), DB_UPDATED_AT) == {
        "advisory_generator_name": GENERATOR_NAME,
        "advisory_generator_version": TRIVY_VERSION,
        "advisory_db_updated_at": DB_UPDATED_AT,
    }


def test_no_cached_database_answers_none_rather_than_raising(tmp_path) -> None:
    """A missing database degrades the audit; it is a normal answer, not a crash."""
    assert db_snapshot_date(tmp_path) is None


def test_the_database_date_is_its_own_updated_at(tmp_path) -> None:
    """The pin is a property of the database build, never the local clock."""
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "metadata.json").write_text(
        json.dumps({"UpdatedAt": DB_UPDATED_AT, "DownloadedAt": "2026-09-01T00:00:00Z"}),
        encoding="utf-8")
    assert db_snapshot_date(tmp_path) == DB_UPDATED_AT


def test_severity_is_kept_only_when_a_source_and_vector_attribute_it() -> None:
    """The severity word is a quotation, so it never appears without its source."""
    from deps.trivy_runner import advisory_index
    report = {"Results": [{"Vulnerabilities": [
        {"VulnerabilityID": "CVE-A", "PkgIdentifier": {"PURL": "pkg:npm/a@1"},
         "Severity": "HIGH", "SeveritySource": "ghsa",
         "CVSS": {"ghsa": {"V3Vector": "CVSS:3.1/AV:N"}}},
        {"VulnerabilityID": "CVE-B", "PkgIdentifier": {"PURL": "pkg:npm/b@1"},
         "Severity": "HIGH", "SeveritySource": "nvd", "CVSS": {}}]}]}
    index = advisory_index(report)
    attributed = index["pkg:npm/a@1"][0]
    assert attributed["advisory_severity"] == "HIGH"
    assert attributed["advisory_cvss_source"] == "ghsa"
    unattributed = index["pkg:npm/b@1"][0]
    assert unattributed["advisory_severity"] is None
    assert unattributed["advisory_cvss_source"] is None

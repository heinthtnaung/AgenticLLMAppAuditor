"""Guards on reading a Trivy report: every source kept apart, and what is refused."""

import pytest

from deps.scanner import ScannerFailed
from deps.trivy_report import read_advisories
from samples import (
    DJANGO_PURL,
    GHSA_VECTOR,
    PYYAML_PURL,
    REDHAT_VECTOR,
    load,
    trivy_record,
    trivy_report_of,
)

# Captured from Trivy 0.74.0 over a directory of pinned Python requirements.
REPORT = "trivy_report.json"
REPORT_WITH_NO_RESULTS = "trivy_report_no_results.json"

def test_a_well_formed_report_is_indexed_by_versioned_purl():
    index = read_advisories(load(REPORT))
    assert list(index) == [DJANGO_PURL, PYYAML_PURL]


def test_an_advisory_keeps_its_id_and_the_fix_as_published():
    # The fix is quoted as the advisory writes it: three release branches, not one.
    advisory = read_advisories(load(REPORT))[DJANGO_PURL][0]
    assert advisory.advisory_id == "CVE-2019-14234"
    assert advisory.fixed_version == "1.11.23, 2.1.11, 2.2.4"
    assert advisory.purl == DJANGO_PURL


def test_every_source_that_scored_a_finding_survives_with_its_own_vector():
    # The whole council downstream reads these disagreements. Collapsing them to
    # one vector, or preferring NVD, would delete the evidence it works from.
    advisory = read_advisories(load(REPORT))[DJANGO_PURL][0]
    assert advisory.vectors == {"ghsa": GHSA_VECTOR, "nvd": GHSA_VECTOR, "redhat": REDHAT_VECTOR}
    assert len(set(advisory.vectors.values())) == 2


def test_the_sources_of_an_advisory_come_back_in_a_fixed_order():
    # The order Trivy happens to write them in is not an order. Two runs must
    # serialise one advisory identically, down to the sequence of its sources.
    out_of_order = trivy_record(
        CVSS={"redhat": {"V3Vector": REDHAT_VECTOR}, "ghsa": {"V3Vector": GHSA_VECTOR}}
    )
    vectors = read_advisories(trivy_report_of(out_of_order))[DJANGO_PURL][0].vectors
    assert list(vectors) == ["ghsa", "redhat"]


def test_a_finding_without_nvd_keeps_the_sources_that_did_score_it():
    # NVD scores roughly four findings in five, so a missing NVD vector is normal
    # and must not take the sources that did score the finding down with it.
    without_nvd = trivy_record(CVSS={"redhat": {"V3Vector": REDHAT_VECTOR, "V3Score": 5.3}})
    assert read_advisories(trivy_report_of(without_nvd))[DJANGO_PURL][0].vectors == {
        "redhat": REDHAT_VECTOR
    }


def test_a_finding_scored_under_cvss_v2_only_is_kept_with_no_vectors():
    # Refusing it would drop a real finding; inventing a v3 vector for it would be
    # worse. It arrives with nothing to score and says so.
    advisory = read_advisories(load(REPORT))[PYYAML_PURL][0]
    assert advisory.advisory_id == "CVE-2001-0001"
    assert advisory.vectors == {}


def test_a_finding_with_no_scores_and_no_fix_is_kept():
    advisory = read_advisories(load(REPORT))[PYYAML_PURL][-1]
    assert advisory.advisory_id == "GHSA-0000-0000-0000"
    assert advisory.fixed_version is None
    assert advisory.vectors == {}


def test_a_v4_only_vector_is_not_read_as_a_v3_one():
    scored = {"V40Vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N", "V40Score": 9.3}
    v4_only = trivy_record(CVSS={"ghsa": scored})
    assert read_advisories(trivy_report_of(v4_only))[DJANGO_PURL][0].vectors == {}


def test_the_vectors_of_an_advisory_cannot_be_edited_after_the_fact():
    advisory = read_advisories(load(REPORT))[DJANGO_PURL][0]
    with pytest.raises(TypeError):
        advisory.vectors["nvd"] = REDHAT_VECTOR


def test_advisories_come_back_sorted_rather_than_in_scan_order():
    scanned = [entry["VulnerabilityID"] for entry in load(REPORT)["Results"][0]["Vulnerabilities"]]
    assert scanned != sorted(scanned)
    found = [advisory.advisory_id for advisory in read_advisories(load(REPORT))[PYYAML_PURL]]
    assert found == sorted(scanned)


def test_the_same_report_is_read_the_same_way_every_time():
    assert read_advisories(load(REPORT)) == read_advisories(load(REPORT))


def test_a_report_that_found_nothing_gives_no_advisories():
    assert read_advisories(load(REPORT_WITH_NO_RESULTS)) == {}


# The last is a target Trivy found nothing in: it omits the key, never empties it.
@pytest.mark.parametrize(
    "report",
    [{"Results": None}, {"Results": []}, {"SchemaVersion": 2},
     {"Results": [{"Target": "docs/requirements.txt", "Type": "pip"}]}],
)
def test_a_report_with_nothing_to_report_gives_no_advisories(report):
    assert read_advisories(report) == {}


def test_an_advisory_with_no_purl_to_join_on_is_refused_by_name():
    with pytest.raises(ScannerFailed, match="'CVE-2019-14234' carries no package URL"):
        read_advisories(trivy_report_of(trivy_record(PkgIdentifier={"UID": "c94254c37d734085"})))


def test_an_advisory_with_no_id_is_refused():
    with pytest.raises(ScannerFailed, match="carries no advisory id"):
        read_advisories(trivy_report_of(trivy_record(VulnerabilityID="")))


@pytest.mark.parametrize("report", [[], "Results", {"Results": "none"}])
def test_a_document_that_is_not_a_trivy_report_is_refused(report):
    with pytest.raises(ScannerFailed, match="Trivy report"):
        read_advisories(report)


def test_a_scores_block_of_the_wrong_shape_is_refused():
    with pytest.raises(ScannerFailed, match="'CVSS' must be an object"):
        read_advisories(trivy_report_of(trivy_record(CVSS="9.8")))

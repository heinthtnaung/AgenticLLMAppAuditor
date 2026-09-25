"""Guards on the record: what a run gathered, counted apart and in a fixed order."""

from report.absences import Coverage
from report.record import Report, build_report
from report_samples import PROVENANCE, advisory, catalogue, component, finding, unidentified

DJANGO = component()
PYYAML = component("pyyaml", "5.1")


def a_report(
    components=(), findings=(), advisories=None, council=(), unidentified=(),
    risk=(), approval=None, overridden=(), coverage=Coverage(),
):
    """Build one report from whatever a test is about."""
    found = catalogue(*components, unidentified=unidentified)
    return build_report(
        PROVENANCE, found, findings, advisories or {}, council, risk, approval, overridden, coverage
    )


def test_a_run_gathers_its_findings_and_counts_what_was_catalogued():
    report = a_report(components=(DJANGO, PYYAML), findings=(finding(DJANGO),))
    assert isinstance(report, Report)
    assert report.component_count == 2
    assert len(report.findings) == 1


def test_a_component_nothing_was_published_against_is_a_result():
    report = a_report(components=(DJANGO, PYYAML), findings=(finding(DJANGO),))
    assert report.components_without_findings == (PYYAML.purl,)


def test_an_advisory_matching_no_component_is_a_different_result():
    # A component with no advisory may really be clean. An advisory with no
    # component is a CVE that fell out of the join, and the report looks clean
    # either way -- so the two are counted apart.
    orphan = advisory(purl=PYYAML.purl)
    report = a_report(components=(DJANGO,), advisories={PYYAML.purl: (orphan,)})
    assert report.advisories_without_components == (PYYAML.purl,)
    assert report.components_without_findings == (DJANGO.purl,)


def test_the_two_kinds_of_nothing_are_both_sorted_so_two_runs_agree():
    report = a_report(components=(PYYAML, DJANGO))
    assert report.components_without_findings == tuple(sorted([DJANGO.purl, PYYAML.purl]))


def test_the_same_run_builds_the_same_record():
    assert a_report(components=(DJANGO,), findings=(finding(DJANGO),)) == a_report(
        components=(DJANGO,), findings=(finding(DJANGO),)
    )


def test_an_artifact_nothing_could_join_to_is_carried_rather_than_dropped():
    # The third kind of nothing. Refusing the whole run over one of these turns a
    # non-issue into total failure, and dropping it silently is the other wrong answer.
    report = a_report(components=(DJANGO,), unidentified=(unidentified(),))
    assert [one.name for one in report.unidentified_artifacts] == ["./local-action"]


def test_an_unidentifiable_artifact_is_not_counted_as_a_component():
    report = a_report(components=(DJANGO,), unidentified=(unidentified(),))
    assert report.component_count == 1
    assert report.components_without_findings == (DJANGO.purl,)


def test_an_override_naming_an_advisory_this_scan_found_matched_something():
    one = finding(DJANGO)
    report = a_report(findings=(one,), overridden=(one.advisory.advisory_id,))
    assert report.overrides_without_findings == ()


def test_an_override_naming_an_advisory_nothing_found_is_counted_not_dropped():
    # Uncounted, a mistyped advisory id would apply to nothing quietly, and an
    # escalation that did not apply would leave a finding a band lower than intended.
    report = a_report(findings=(finding(DJANGO),), overridden=("CVE-2021-42799",))
    assert report.overrides_without_findings == ("CVE-2021-42799",)


def test_an_override_that_matched_nothing_does_not_stop_the_run():
    # An answer file reused across repositories will legitimately name advisories
    # absent from one of them, so this is counted rather than refused.
    report = a_report(findings=(finding(DJANGO),), overridden=("CVE-OTHER",))
    assert len(report.findings) == 1


def test_overrides_that_matched_nothing_are_sorted_so_two_runs_agree():
    report = a_report(overridden=("CVE-2", "CVE-1"))
    assert report.overrides_without_findings == ("CVE-1", "CVE-2")

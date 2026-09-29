"""Guards on the join: a CVE affecting an installed component, with every source kept apart."""

import pytest

from findings.finding import Finding, build_findings, unmatched_purls
from finding_samples import (
    CNA_SCORE,
    CNA_VECTOR,
    DJANGO_PURL,
    GHSA_SCORE,
    GHSA_VECTOR,
    HARMLESS_SCORE,
    HARMLESS_VECTOR,
    PYYAML_PURL,
    REDHAT_SCORE,
    REDHAT_VECTOR,
    TENABLE_SCORE,
    TENABLE_VECTOR,
    VERSION_2_VECTOR,
    advisory,
    component,
    index,
)

PYYAML = component(name="pyyaml", version="5.1", purl=PYYAML_PURL)
PYYAML_ADVISORY = advisory(advisory_id="CVE-2020-14343", purl=PYYAML_PURL)

# Differs from GHSA on all three impact metrics, which is the disagreement the
# saved Trivy report actually carries for CVE-2019-14234.
DISAGREEING = advisory(vectors={"ghsa": GHSA_VECTOR, "redhat": REDHAT_VECTOR})


def test_an_advisory_against_an_installed_component_is_a_finding():
    findings = build_findings([component()], index(advisory()))
    assert len(findings) == 1
    assert findings[0].component.purl == DJANGO_PURL
    assert findings[0].advisory.advisory_id == "CVE-2019-14234"
    assert findings[0].advisory.fixed_version == "2.2.4"


def test_a_component_with_no_advisory_produces_no_finding():
    findings = build_findings([component(), PYYAML], index(PYYAML_ADVISORY))
    assert [finding.component.name for finding in findings] == ["pyyaml"]


def test_nothing_installed_produces_nothing():
    assert build_findings([], index(advisory())) == ()


def test_a_component_gets_one_finding_per_advisory_against_it():
    second = advisory(advisory_id="CVE-2020-7471")
    third = advisory(advisory_id="CVE-2021-3281")
    findings = build_findings([component()], index(third, advisory(), second))
    assert [finding.advisory.advisory_id for finding in findings] == [
        "CVE-2019-14234",
        "CVE-2020-7471",
        "CVE-2021-3281",
    ]
    assert {finding.component.name for finding in findings} == {"django"}


def test_a_finding_keeps_every_source_attributed_and_scored():
    finding = build_findings([component()], index(DISAGREEING))[0]
    assert [(score.source, score.base_score) for score in finding.scores] == [
        ("ghsa", GHSA_SCORE),
        ("redhat", REDHAT_SCORE),
    ]


def test_disagreeing_sources_report_the_metrics_they_differ_on():
    finding = build_findings([component()], index(DISAGREEING))[0]
    assert finding.disputed_metrics() == ("C", "I", "A")


def test_one_metric_apart_is_reported_as_one_metric():
    # CVE-2025-37164: the CNA scored it 10.0 and Tenable 9.8, on Scope alone.
    contested = advisory(vectors={"cna": CNA_VECTOR, "tenable": TENABLE_VECTOR})
    finding = build_findings([component()], index(contested))[0]
    assert finding.disputed_metrics() == ("S",)
    assert [score.base_score for score in finding.scores] == [CNA_SCORE, TENABLE_SCORE]


def test_a_dispute_is_the_union_across_every_source():
    third = "CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    contested = advisory(
        vectors={"ghsa": CNA_VECTOR, "nvd": TENABLE_VECTOR, "redhat": third},
    )
    finding = build_findings([component()], index(contested))[0]
    assert finding.disputed_metrics() == ("AV", "S")


@pytest.mark.parametrize(
    "vectors",
    [{"ghsa": GHSA_VECTOR}, {"ghsa": GHSA_VECTOR, "nvd": GHSA_VECTOR}, {}],
    ids=["one source", "two agreeing sources", "no source"],
)
def test_sources_that_do_not_disagree_dispute_nothing(vectors):
    finding = build_findings([component()], index(advisory(vectors=vectors)))[0]
    assert finding.disputed_metrics() == ()


def test_a_dispute_ignores_the_sources_that_could_not_be_read():
    mixed = advisory(vectors={"ghsa": GHSA_VECTOR, "nvd": VERSION_2_VECTOR})
    finding = build_findings([component()], index(mixed))[0]
    assert finding.disputed_metrics() == ()


def test_a_refused_vector_does_not_lose_the_advisory_or_the_other_sources():
    mixed = advisory(vectors={"ghsa": GHSA_VECTOR, "nvd": VERSION_2_VECTOR})
    finding = build_findings([component()], index(mixed))[0]
    assert [score.source for score in finding.scores] == ["ghsa"]
    assert [refused.source for refused in finding.unreadable] == ["nvd"]
    assert finding.is_scored


def test_nvd_is_not_privileged_when_it_is_the_source_that_cannot_be_read():
    # NVD carries a vector for far fewer advisories than GHSA does; a join that
    # looked to NVD first would report most of these as unscored.
    mixed = advisory(vectors={"ghsa": GHSA_VECTOR, "nvd": VERSION_2_VECTOR})
    finding = build_findings([component()], index(mixed))[0]
    assert finding.scores[0].base_score == GHSA_SCORE


def test_an_advisory_nobody_scored_is_still_a_finding():
    finding = build_findings([component()], index(advisory(vectors={})))[0]
    assert finding.advisory.advisory_id == "CVE-2019-14234"
    assert finding.scores == ()
    assert finding.unreadable == ()
    assert not finding.is_scored


def test_no_score_is_not_a_score_of_zero():
    unscored = build_findings([component()], index(advisory(vectors={})))[0]
    zero = build_findings([component()], index(advisory(vectors={"nvd": HARMLESS_VECTOR})))[0]
    assert not unscored.is_scored
    assert zero.is_scored
    assert zero.scores[0].base_score == HARMLESS_SCORE


def test_a_finding_offers_no_single_severity_of_its_own():
    # Choosing between disagreeing sources is the council's job and the council
    # is not built. A precedence order invented here would be unattributable.
    finding = build_findings([component()], index(DISAGREEING))[0]
    assert not hasattr(finding, "severity")
    assert not hasattr(finding, "base_score")
    assert not hasattr(finding, "score")
    assert len(finding.scores) == 2


def test_two_runs_over_one_tree_produce_identical_findings():
    components = [PYYAML, component()]
    advisories = index(PYYAML_ADVISORY, advisory(advisory_id="CVE-2020-7471"), advisory())
    assert build_findings(components, advisories) == build_findings(
        list(reversed(components)), advisories
    )


def test_findings_are_ordered_by_component_then_advisory():
    components = [PYYAML, component()]
    advisories = index(PYYAML_ADVISORY, advisory(advisory_id="CVE-2020-7471"), advisory())
    ordered = build_findings(components, advisories)
    assert [(finding.component.name, finding.advisory.advisory_id) for finding in ordered] == [
        ("django", "CVE-2019-14234"),
        ("django", "CVE-2020-7471"),
        ("pyyaml", "CVE-2020-14343"),
    ]


def test_a_finding_is_frozen():
    finding = build_findings([component()], index(advisory()))[0]
    with pytest.raises(AttributeError):
        finding.scores = ()


def test_an_advisory_matching_no_installed_component_is_named_not_dropped():
    # A dropped advisory is a CVE missing from a report that still looks clean.
    assert unmatched_purls([component()], index(PYYAML_ADVISORY)) == (PYYAML_PURL,)


def test_nothing_is_unmatched_when_every_advisory_joins():
    assert unmatched_purls([component()], index(advisory())) == ()


@pytest.mark.parametrize(
    "joiner", [build_findings, unmatched_purls], ids=["build_findings", "unmatched_purls"]
)
@pytest.mark.parametrize("given", [None, [], "pkg:pypi/django@2.2.0"], ids=["none", "list", "str"])
def test_an_advisory_index_that_is_no_mapping_is_refused(joiner, given):
    with pytest.raises(TypeError, match="must be a mapping of purl to advisories"):
        joiner([component()], given)


def test_a_finding_carries_the_whole_component_and_advisory_records():
    finding = build_findings([component()], index(advisory()))[0]
    assert isinstance(finding, Finding)
    assert finding.component.locations == ("/requirements.txt",)
    assert finding.advisory.summary.startswith("Django:")

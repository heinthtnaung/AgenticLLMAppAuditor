"""Guards on the audit artefact: every number re-derivable, and no winner named."""

import json

import pytest

from cvss.score import base_score
from cvss.vector import parse
from report.json_report import as_dictionary, as_json
from report.provenance import RunProvenance, UnknownAdvisoryDatabase
from report.council_record import CouncilAssessment, CouncilWithoutVector
from report.record import build_report
from report_samples import (
    catalogue,
    CONFIDENTIALITY_ONLY,
    DATABASE,
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    TOTAL_LOSS,
    VERSION_2_VECTOR,
    component,
    finding,
    unidentified,
)

DJANGO = component()
DISAGREEING = {"ghsa": TOTAL_LOSS, "nvd": LOW_CONFIDENTIALITY}


def a_report(findings=(), council=(), provenance=PROVENANCE, unidentified=(), overridden=()):
    """Build one report from whatever a test is about."""
    found = catalogue(DJANGO, unidentified=unidentified)
    return build_report(provenance, found, findings, {}, council, (), None, overridden)


def test_every_score_travels_beside_the_vector_it_came_from():
    # The rule the record is shaped by: a score nobody can re-derive is not a
    # score. Every number here is recomputed from the vector printed next to it.
    rendered = as_dictionary(a_report((finding(DJANGO, vectors=DISAGREEING),)))
    published = rendered["findings"][0]["scores"]
    assert [entry["source"] for entry in published] == ["ghsa", "nvd"]
    for entry in published:
        assert entry["base_score"] == base_score(parse(entry["vector"]))


def test_no_winner_is_named_anywhere_on_a_finding():
    rendered = as_dictionary(a_report((finding(DJANGO, vectors=DISAGREEING),)))["findings"][0]
    assert "score" not in rendered
    assert "severity" not in rendered
    assert "authoritative_source" not in rendered
    assert len(rendered["scores"]) == 2


def test_the_metrics_the_sources_differ_on_are_recorded():
    rendered = as_dictionary(a_report((finding(DJANGO, vectors=DISAGREEING),)))["findings"][0]
    assert rendered["disputed_metrics"] == ["C", "I", "A"]
    assert rendered["severity_bands"] == ["Critical", "Medium"]
    assert rendered["score_spread"] == 4.5


def test_a_refused_vector_is_kept_with_its_reason_and_never_scored():
    mixed = {"ghsa": CONFIDENTIALITY_ONLY, "nvd": VERSION_2_VECTOR}
    rendered = as_dictionary(a_report((finding(DJANGO, vectors=mixed),)))["findings"][0]
    assert [entry["source"] for entry in rendered["scores"]] == ["ghsa"]
    refused = rendered["unreadable"][0]
    assert refused["source"] == "nvd"
    assert "CVSS v2" in refused["refusal"]
    assert "base_score" not in refused


def test_a_finding_nobody_scored_carries_no_score_rather_than_a_zero():
    rendered = as_dictionary(a_report((finding(DJANGO, vectors={}),)))["findings"][0]
    assert rendered["scores"] == []
    assert rendered["severity_bands"] == []


def test_what_was_not_assessed_is_a_field_and_not_an_omission():
    named = [entry["what"] for entry in as_dictionary(a_report())["not_assessed"]]
    assert named == ["Organisation Risk Score", "Approval record", "Council ruling"]


def test_a_council_that_did_not_run_is_null_rather_than_absent():
    rendered = as_dictionary(a_report((finding(DJANGO),)))["findings"][0]
    assert rendered["council"] is None


def test_a_council_that_settled_a_vector_is_recorded_with_it():
    settled = CouncilAssessment("CVE-2019-14234", TOTAL_LOSS, True)
    rendered = as_dictionary(a_report((finding(DJANGO),), (settled,)))["findings"][0]
    assert rendered["council"]["ran"]
    assert rendered["council"]["vector"] == TOTAL_LOSS
    assert rendered["council"]["single_assessor"]


def test_a_council_that_ran_and_settled_nothing_says_so_rather_than_looking_absent():
    # The record used to say no council had run. That is a false statement in an
    # audit record, and the likely outcome of any real run under the no-fallback
    # rule, because one unsettled metric of eight discards the whole vector.
    open_still = CouncilWithoutVector("CVE-2019-14234", False, ("S",), ("AC",))
    rendered = as_dictionary(a_report((finding(DJANGO),), (open_still,)))["findings"][0]
    assert rendered["council"]["ran"]
    assert rendered["council"]["vector"] is None
    assert rendered["council"]["unresolved_metrics"] == ["S"]
    assert rendered["council"]["contested_metrics"] == ["AC"]


def test_the_run_says_which_database_it_joined_against():
    rendered = as_dictionary(a_report())["run"]["advisory_database"]
    assert rendered == {"built_at": DATABASE.built_at, "known": True}


def test_a_run_that_could_not_read_a_database_says_so_rather_than_looking_clean():
    # Trivy with no database finds nothing and exits 0, so this flag is the
    # difference between a clean repository and a report that means nothing.
    blind = RunProvenance("r", "s", "t", UnknownAdvisoryDatabase("no metadata.json"))
    rendered = as_dictionary(a_report(provenance=blind))["run"]["advisory_database"]
    assert rendered == {"known": False, "reason": "no metadata.json"}


def test_the_same_record_renders_the_same_bytes():
    report = a_report((finding(DJANGO, vectors=DISAGREEING),))
    assert as_json(report) == as_json(report)


def test_the_artefact_is_json_and_ends_in_a_newline():
    rendered = as_json(a_report((finding(DJANGO),)))
    assert rendered.endswith("\n")
    assert json.loads(rendered)["run"]["finding_count"] == 1


@pytest.mark.parametrize("key", ["repository", "syft_version", "trivy_version", "component_count"])
def test_the_run_records_what_produced_it(key):
    assert key in as_dictionary(a_report())["run"]


def test_the_artifacts_nothing_could_join_to_are_named_in_the_record():
    rendered = as_dictionary(a_report(unidentified=(unidentified(),)))
    assert rendered["unidentified_artifacts"] == [
        {"name": "./local-action", "ecosystem": "github-action", "locations": ["/.github/"]}
    ]


def test_a_run_where_everything_was_identified_names_none():
    assert as_dictionary(a_report())["unidentified_artifacts"] == []


def test_an_override_that_matched_no_finding_is_in_the_record():
    rendered = as_dictionary(a_report(overridden=("CVE-2021-42799",)))
    assert rendered["overrides_without_findings"] == ["CVE-2021-42799"]


def test_a_run_whose_overrides_all_matched_names_none():
    assert as_dictionary(a_report())["overrides_without_findings"] == []

"""Reading a saved report back and re-rendering it is byte-identical to the original.

The guard `cli.approve` rests on this: if the record read from the JSON does not
re-render to the very bytes a run wrote, approving refuses. So every kind of thing
a record can hold is built the way a run builds it, rendered, read back, and
rendered again -- and the two renderings are compared byte for byte, in all three
formats, because a single differing byte is what the guard trips on.
"""

import json

import pytest

from council_runs import QUOTED_BY_ONE, council_ran, council_states, fell_back
from escalation_runs import ANOTHER_VALUE, SETTLING, escalated, split_on_av
from full_runs import fully_assessed
from order_runs import one_way
from organisation.risk import assess, per_source
from report.absences import NO_EXPLAINER_ASKED, Coverage
from report.html_report import as_html
from report.json_report import as_json
from report.load_json import ReportJsonFault
from report.load_report import council_was_named, no_explainer_asked, report_from_json
from report.model_identity import ESCALATION_ROLE, MEMBER_ROLE, UnknownDigest, UnknownOllamaVersion
from report.provenance import AdvisoryDatabase, LocalModels, RunProvenance, UnknownAdvisoryDatabase
from report.record import Report, build_report
from report.text_report import as_text
from report_pages import (
    ANSWERS,
    DJANGO,
    all_answers,
    full_report,
    full_report_with_link,
    report_with_models,
)
from report_samples import (
    CONFIDENTIALITY_ONLY,
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    catalogue,
    component,
    finding,
)
from same_evidence_runs import same_words
from scoring.question import Answer

RENDERERS = (as_text, as_json, as_html)
TWO_SOURCES = {"ghsa": CONFIDENTIALITY_ONLY, "nvd": LOW_CONFIDENTIALITY}
TYPED = all_answers({"EXP-1": Answer.YES, "BUS-1": Answer.YES, "THR-1": Answer.UNKNOWN})


def reloaded(report: Report) -> Report:
    """Render a report to JSON and read it straight back into a record."""
    return report_from_json(json.loads(as_json(report)), "report.json")


def assert_round_trips(report: Report) -> None:
    """Assert the record read back re-renders to the same bytes in every format."""
    back = reloaded(report)
    for render in RENDERERS:
        assert render(back) == render(report)


def council_variants() -> Report:
    """Build a record holding every council state a finding's entry can be in, one finding each."""
    outcomes = (
        *council_states(), escalated(SETTLING), split_on_av(ANOTHER_VALUE), one_way(), fell_back(),
        council_ran(advisory_id="CVE-ONE-QUOTE", **QUOTED_BY_ONE), same_words("CVE-SAME-WORDS"),
    )
    components = [component(f"pkg{index}", "1.0") for index, _ in enumerate(outcomes)]
    raised = tuple(
        finding(installed, advisory_id=outcome.advisory_id, vectors=TWO_SOURCES)
        for installed, outcome in zip(components, outcomes)
    )
    return build_report(PROVENANCE, catalogue(*components), raised, {}, tuple(outcomes))


def unknown_provenance() -> Report:
    """Build a record whose server, digests and database were all unreadable, each its own type."""
    local = LocalModels(
        server="http://remote:11434", context_tokens=4096, timeout_seconds=90.0, temperature=0,
        seed=7, think=True, order_check=False, escalation_model="big:27b",
        ollama_version=UnknownOllamaVersion("server did not answer /api/version"),
        models=(
            UnknownDigest("qwen2.5:7b", MEMBER_ROLE, "no digest returned"),
            UnknownDigest("big:27b", ESCALATION_ROLE, "no digest returned"),
        ),
        remote_host="remote:11434",
    )
    provenance = RunProvenance(
        "fetched/x", "syft-x", "trivy-x", UnknownAdvisoryDatabase("no trivy db here"), local
    )
    one = finding(component(), vectors={"ghsa": CONFIDENTIALITY_ONLY})
    return build_report(provenance, catalogue(component()), (one,), {})


def typed_run() -> Report:
    """Build a record whose answers were typed at the terminal, so it names an answers source."""
    provenance = RunProvenance(
        "fetched/x", "syft-x", "trivy-x", AdvisoryDatabase("2026-09-22T02:00:05Z"),
        answers_source="asked at the prompt and saved to reports/x.answers.json",
    )
    one = finding(component(), vectors={"ghsa": CONFIDENTIALITY_ONLY})
    return build_report(provenance, catalogue(component()), (one,), {})


def nothing_scored() -> Report:
    """Build a record whose answers were given but which had no finding to weigh them against."""
    return build_report(
        PROVENANCE, catalogue(component()), (), {}, coverage=Coverage(answers_given=True)
    )


def unread_manifest() -> Report:
    """Build a record with a manifest the scan read no version from, named under not assessed."""
    one = finding(component(), vectors={"ghsa": CONFIDENTIALITY_ONLY})
    return build_report(
        PROVENANCE, catalogue(component()), (one,), {},
        coverage=Coverage(unread_manifests=("/pkg/package.json",)),
    )


def typed_answers() -> Report:
    """Build a record scored from Yes and Unknown answers, so a score is weighed and flagged."""
    one = finding(component(), vectors=TWO_SOURCES)
    return build_report(
        PROVENANCE, catalogue(component()), (one,), {}, risk=[assess(one, TYPED, per_source(one))]
    )


RECORDS = {
    "fully_assessed": fully_assessed,
    "full_report": full_report,
    "report_with_models": report_with_models,
    "full_report_with_link": full_report_with_link,
    "council_variants": council_variants,
    "unknown_provenance": unknown_provenance,
    "typed_run": typed_run,
    "nothing_scored": nothing_scored,
    "unread_manifest": unread_manifest,
    "typed_answers": typed_answers,
}


@pytest.mark.parametrize("name", list(RECORDS), ids=list(RECORDS))
def test_every_record_re_renders_to_the_same_bytes(name):
    # The guard the whole feature rests on: a record read back is the record written.
    assert_round_trips(RECORDS[name]())


@pytest.mark.parametrize("name", ["nothing_scored", "unread_manifest"], ids=["scored", "unread"])
def test_the_coverage_a_record_does_not_store_is_recovered(name):
    # Coverage has no field of its own, so it is rebuilt from the absences and the
    # provenance; a shape where only coverage differs would pass the render guard unseen.
    built = RECORDS[name]()
    assert reloaded(built).coverage == built.coverage


def test_an_answered_finding_scores_the_same_after_a_round_trip():
    # The risk is recomputed from the recorded answers by the real engine, not read,
    # so a round trip puts the same number, band and floors back.
    one = finding(DJANGO, vectors=TWO_SOURCES)
    report = build_report(
        PROVENANCE, catalogue(DJANGO), (one,), {}, risk=[assess(one, ANSWERS, per_source(one))]
    )
    advisory_id = one.advisory.advisory_id
    assert reloaded(report).risk[advisory_id].scores == report.risk[advisory_id].scores


def test_a_no_explainer_note_names_no_model_or_dropped_item():
    # The "no council was asked" note a run with no council writes has neither; a block
    # that claims the note yet names one is a recorded entry, so the run did name a council.
    note = {"assessed": False, "because": NO_EXPLAINER_ASKED}
    assert no_explainer_asked(note) is True
    assert no_explainer_asked({**note, "model": "m"}) is False
    assert no_explainer_asked({**note, "dropped_items": [{"metric": "C"}]}) is False


def test_a_run_with_no_council_names_none_and_one_with_a_council_names_it():
    assert council_was_named(json.loads(as_json(full_report_with_link()))["findings"]) is False
    assert council_was_named(json.loads(as_json(fully_assessed()))["findings"]) is True


def test_a_document_that_is_not_an_object_is_refused():
    with pytest.raises(ReportJsonFault, match="must be a JSON object"):
        report_from_json([], "report.json")


def test_a_report_with_no_run_block_is_refused():
    with pytest.raises(ReportJsonFault, match="no 'run'"):
        report_from_json({"findings": []}, "report.json")


def test_a_finding_missing_its_advisory_is_refused():
    document = json.loads(as_json(full_report_with_link()))
    del document["findings"][0]["advisory"]
    with pytest.raises(ReportJsonFault, match="advisory"):
        report_from_json(document, "report.json")

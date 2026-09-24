"""Guards on the council in the audit record: everything the design keeps, kept.

**Every assessed record here comes out of a real chairman**, through
`council_runs`: an assessment handing over a vector never carries a contested or
unresolved metric, and a record filled in by hand can say it does. A finding
passed over is built as `cli.council_run.passed_over` builds one.
"""

from cli.council_run import SOURCES_AGREE
from council.prompt import PROMPT_VERSION
from council_runs import (
    AGREED, DECLINED_AND_GUESSED, DISSENTING, LONG_QUOTE, UNPARSEABLE, council_ran, fell_back,
)
from report.council_record import CouncilNotAsked
from report.json_council import council_of
from report.record import build_report
from report_samples import PROVENANCE, catalogue, component, finding

DJANGO = component()


def rendered(outcome):
    """Render one advisory's council entry from the record."""
    one = finding(DJANGO, advisory_id=outcome.advisory_id)
    report = build_report(PROVENANCE, catalogue(DJANGO), (one,), {}, (outcome,))
    return council_of(report, outcome.advisory_id)


def metric_of(outcome, metric: str) -> dict:
    """Give one metric's entry from an advisory's council record."""
    return next(one for one in rendered(outcome)["metrics"] if one["metric"] == metric)


def contested() -> dict:
    """Give AV's entry, which a real council of two families left contested."""
    return metric_of(council_ran(**DISSENTING), "AV")


def test_every_member_that_spoke_is_in_the_record():
    assert [one["member"] for one in contested()["members"]] == ["qwen2.5:7b", "gemma4:latest"]


def test_a_members_lineage_is_recorded_because_agreement_without_it_means_nothing():
    members = contested()["members"]
    assert [one["family"] for one in members] == ["qwen2.5", "gemma4"]
    assert all(one["provider"] and one["model"] and one["prompt_version"] for one in members)


def test_an_answer_is_recorded_with_its_evidence_and_whether_it_checked_out():
    first = contested()["members"][0]
    assert first["said"] == "answered"
    assert (first["value"], first["confidence"]) == ("N", "high")
    assert first["evidence"] == LONG_QUOTE
    assert first["evidence_verified"] is True


def test_the_chairmans_decision_is_recorded_beside_the_members():
    metric = contested()
    assert metric["outcome"] == "contested"
    assert metric["value"] is None


def test_a_settled_metric_records_what_settled_it():
    metric = metric_of(council_ran(), "AV")
    assert metric["value"] == "N"
    assert (metric["basis"], metric["confidence"]) == (AGREED, "high")


def test_an_unresolved_metric_records_which_source_it_fell_back_to():
    metric = metric_of(fell_back(), "AV")
    assert metric["outcome"] == "unresolved"
    assert (metric["value"], metric["fallback_source"]) == ("N", "ghsa")


def test_a_member_that_declined_is_told_apart_from_one_that_guessed():
    members = metric_of(council_ran(**DECLINED_AND_GUESSED), "UI")["members"]
    assert [one["said"] for one in members] == ["declined", "guessed"]
    assert members[0]["value"] is None
    assert members[1]["value"] == "R"


def test_a_member_whose_call_failed_records_why():
    failed = metric_of(council_ran(**UNPARSEABLE), "AV")["members"][1]
    assert failed["said"] == "failed"
    assert "'NONSENSE' is not a value of Attack Vector" in failed["reason"]


def test_a_member_whose_call_failed_is_named_as_fully_as_one_that_answered():
    # The call an auditor most needs to trace to a model, and a local member
    # recorded without its model or as hosted is a false fact about the run.
    failed = metric_of(council_ran(**UNPARSEABLE), "AV")["members"][1]
    named = {key: failed[key] for key in ("member", "provider", "model", "family", "ran_local")}
    assert named == {
        "member": "gemma4:latest", "provider": "ollama", "model": "gemma4:latest",
        "family": "gemma4", "ran_local": True,
    }
    assert failed["prompt_version"] == PROMPT_VERSION


def test_a_council_that_did_not_run_on_an_advisory_is_null():
    report = build_report(PROVENANCE, catalogue(DJANGO), (finding(DJANGO),), {})
    assert council_of(report, "CVE-2019-14234") is None


def test_a_finding_the_council_was_not_put_to_says_so_and_says_why():
    # Three states, and null is only the third: no council in this run at all.
    # A scoped run that wrote null here would report a finding it passed over as
    # a finding nothing ran on.
    passed = CouncilNotAsked("CVE-1", SOURCES_AGREE)
    assert rendered(passed) == {"ran": False, "because": SOURCES_AGREE}


def test_a_finding_of_a_run_with_no_council_at_all_is_null():
    one = finding(DJANGO, advisory_id="CVE-1")
    report = build_report(PROVENANCE, catalogue(DJANGO), (one,), {})
    assert council_of(report, "CVE-1") is None


def test_an_assessed_finding_says_a_council_ran_on_it_whether_or_not_it_settled():
    assert rendered(council_ran())["ran"] is True
    assert rendered(council_ran(**DISSENTING))["ran"] is True

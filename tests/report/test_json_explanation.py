"""Guards on why the sources differ in the JSON record: on every finding, and saying why not."""

from council.explanation_prompt import EXPLANATION_PROMPT_VERSION
from explanation_runs import QUOTED, WHY, explained_report
from report.absences import NO_EXPLAINER_ASKED, Coverage
from report.json_explanation import NOT_RECORDED, explanation_of
from report.record import build_report
from report_samples import PROVENANCE, catalogue, component, finding

# A record no model was asked for names neither a model nor a prompt version.
NOBODY_ASKED = ["assessed", "because", "dropped_items"]


def test_an_explained_finding_names_the_model_the_version_each_item_and_what_was_dropped():
    assert explanation_of(explained_report(), "CVE-EXPLAINED") == {
        "assessed": True,
        "model": "big:27b",
        "prompt_version": EXPLANATION_PROMPT_VERSION,
        "items": [{
            "metric": "C", "why": WHY, "evidence": QUOTED,
            "evidence_verified": True, "why_checked": False,
        }],
        "dropped": 1,
        "dropped_items": [{
            "metric": "C", "why": "A second go.", "evidence": "all of the files",
            "evidence_verified": False, "why_checked": False, "reason": "unverified quotation",
        }],
    }


def test_a_finding_not_explained_says_why():
    report = explained_report()
    assert explanation_of(report, "CVE-UNEXPLAINED") == {
        "assessed": False,
        "model": "big:27b",
        "prompt_version": EXPLANATION_PROMPT_VERSION,
        "because": "big:27b: the model offered 1 item, and none was kept (unverified quotation 1)",
        "dropped_items": [{
            "metric": "C", "why": "It is bad.", "evidence": "the whole disk",
            "evidence_verified": False, "why_checked": False, "reason": "unverified quotation",
        }],
    }
    assert explanation_of(report, "CVE-AGREED")["because"].startswith("no two of its readable")


def test_a_finding_in_a_run_with_no_council_says_nobody_asked():
    report = build_report(PROVENANCE, catalogue(component()), (finding(),), {})
    assert explanation_of(report, "CVE-2019-14234") == {
        "assessed": False, "because": NO_EXPLAINER_ASKED, "dropped_items": [],
    }


def test_a_council_run_holding_no_record_for_a_finding_does_not_claim_nobody_asked():
    named = Coverage(council_named=True)
    report = build_report(PROVENANCE, catalogue(component()), (finding(),), {}, coverage=named)
    assert explanation_of(report, "CVE-2019-14234")["because"] == NOT_RECORDED


def test_the_model_and_the_prompt_version_are_named_where_a_model_was_asked_and_only_there():
    report = explained_report()
    nobody = build_report(PROVENANCE, catalogue(component()), (finding(),), {})
    assert list(explanation_of(report, "CVE-EXPLAINED")) == [
        "assessed", "model", "prompt_version", "items", "dropped", "dropped_items",
    ]
    assert list(explanation_of(report, "CVE-UNEXPLAINED")) == [
        "assessed", "model", "prompt_version", "because", "dropped_items",
    ]
    assert list(explanation_of(report, "CVE-AGREED")) == NOBODY_ASKED
    assert list(explanation_of(nobody, "CVE-2019-14234")) == NOBODY_ASKED


def test_every_kept_item_says_its_quotation_was_checked_and_its_prose_was_not():
    items = explanation_of(explained_report(), "CVE-EXPLAINED")["items"]
    assert [(one["evidence_verified"], one["why_checked"]) for one in items] == [(True, False)]


def test_the_count_of_items_not_kept_is_the_list_of_them():
    record = explanation_of(explained_report(), "CVE-EXPLAINED")
    assert record["dropped"] == len(record["dropped_items"])

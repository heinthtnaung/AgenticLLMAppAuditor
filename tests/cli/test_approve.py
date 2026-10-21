"""Recording a decision on a report that already ran: the three reports it rewrites.

The reports are written under `tmp_path`, never the repository's `reports/`, and no
model is asked -- the record is read back from the JSON a run wrote. The happy path
asserts the rewritten reports are exactly what a run carrying that decision would have
written; the refusals are in `test_approve_refusals`. The helpers are in
`approve_samples`.
"""

import json

import pytest

from approve_samples import (
    BLOCK,
    DECISION,
    RENDERERS,
    answers_at,
    approve,
    built,
    built_rich,
    run,
    saved,
)
from cli.main import APPROVAL_RECORDED
from organisation.approval import Approval, Decision
from report.json_report import as_json
from report.text_report import as_text

# The seven fields the record's JSON carries that no text or HTML page renders. A
# consistent edit to any one re-renders to itself and is not caught -- the accepted gap
# (rule 24). Paths are into `approve_samples.built_rich`, whose one finding is index 0.
JSON_ONLY_FIELDS = [
    (["findings", 0, "advisory", "summary"], "a summary nobody wrote"),
    (["findings", 0, "advisory", "fixed_version"], "9.9.9"),
    (["findings", 0, "component", "locations"], ["elsewhere/package-lock.json"]),
    (["findings", 0, "council", "metrics", 0, "members", 0, "evidence"], "made up"),
    (["findings", 0, "council", "metrics", 0, "members", 0, "prompt_version"], "p-999"),
    (["unidentified_artifacts", 0, "locations"], ["moved"]),
    (["run", "local_models", "seed"], 8),
]
FIELD_IDS = ["summary", "fixed_version", "component-locations", "evidence",
             "prompt_version", "artifact-locations", "seed"]


def set_in(document: dict, path: list, value) -> None:
    """Set one value deep in a parsed document, following the path to its last key."""
    cursor = document
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value


def test_approving_rewrites_the_three_reports_as_a_run_with_the_decision_would(tmp_path):
    _json, code, out, error = approve(tmp_path)
    # Literal 0, so a mutant that renumbers APPROVAL_RECORDED to a found-something code is caught.
    assert code == 0
    assert "reports written to" in error
    expected = built(DECISION)
    # stdout is the text report, as an ordinary run writes, not the JSON or another format.
    assert out == as_text(expected)
    for suffix, render in RENDERERS.items():
        assert (tmp_path / f"vulnscout{suffix}").read_text(encoding="utf-8") == render(expected)


def test_the_recorded_decision_is_marked_as_added_after_the_run(tmp_path):
    report_json, _code, _out, _error = approve(tmp_path)
    written = json.loads(report_json.read_text(encoding="utf-8"))["approval"]
    assert written == {
        "approved": True, "approver": "dana", "decision": "approved",
        "recorded_at": "2026-10-20T10:00:00Z", "note": "", "attached_after_run": True,
    }


def test_only_the_approval_changes_and_nothing_else(tmp_path):
    before = json.loads(as_json(built(None)))
    report_json, _code, _out, _error = approve(tmp_path)
    after = json.loads(report_json.read_text(encoding="utf-8"))
    for key in ("run", "findings", "secrets", "unidentified_artifacts"):
        assert after[key] == before[key]


def test_replace_approval_overwrites_a_decision_a_report_already_carries(tmp_path):
    first = Approval("hein", Decision.APPROVED, "2026-09-01T00:00:00Z", attached_after_run=True)
    report_json = saved(tmp_path, built(first))
    block = {"approver": "dana", "decision": "overridden", "recorded_at": "2026-10-20T10:00:00Z"}
    argv = ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, block)),
            "--replace-approval"]
    code, _out, _error = run(argv)
    assert code == APPROVAL_RECORDED
    written = json.loads(report_json.read_text(encoding="utf-8"))["approval"]
    assert written["approver"] == "dana"
    assert written["decision"] == "overridden"


@pytest.mark.parametrize("path,value", JSON_ONLY_FIELDS, ids=FIELD_IDS)
def test_a_json_only_edit_to_a_field_no_page_shows_is_not_caught(tmp_path, path, value):
    # The guard is cross-rendering agreement, not a signature: a field in the JSON alone
    # re-renders to itself and is approved. Closing the gap turns every case here red.
    report_json = saved(tmp_path, built_rich())
    document = json.loads(report_json.read_text(encoding="utf-8"))
    set_in(document, path, value)
    report_json.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    code, _out, _error = run(
        ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, BLOCK))]
    )
    assert code == APPROVAL_RECORDED
    assert json.loads(report_json.read_text(encoding="utf-8"))["approval"]["approved"] is True

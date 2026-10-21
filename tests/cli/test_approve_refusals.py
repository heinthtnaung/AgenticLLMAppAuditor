"""Recording a decision refuses bad input: each is named, exits 2, and rewrites nothing.

A report this tool did not write, one scored by other rules, one edited by hand, one
whose JSON is malformed, a read-only report file, an answers file with no decision, and
a report that already carries one. The success path is in `test_approve`; the helpers
are in `approve_samples`.
"""

import json

from approve_samples import (
    BLOCK,
    DECISION,
    NEEDS_PERMISSIONS,
    OWNER_WRITE,
    READ_ONLY,
    RENDERERS,
    answers_at,
    built,
    built_with_secret,
    run,
    saved,
)
from cli.main import COULD_NOT_RUN


def approve_saved(tmp_path, report, block=BLOCK):
    """Save a record and run approve on it, giving the JSON path and what the run wrote."""
    report_json = saved(tmp_path, report)
    argv = ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, block))]
    return (report_json, *run(argv))


def test_a_report_this_tool_did_not_write_is_refused(tmp_path):
    report_json = saved(tmp_path, built(None))
    edited = tmp_path / "vulnscout.txt"
    edited.write_text(edited.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
    code, _out, error = run(
        ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, BLOCK))]
    )
    assert code == COULD_NOT_RUN
    assert "vulnscout.txt" in error
    assert "edited by hand or written by another version" in error


def test_a_hand_edit_is_refused_before_anything_is_rewritten(tmp_path):
    report_json = saved(tmp_path, built(None))
    (tmp_path / "vulnscout.html").write_text("tampered", encoding="utf-8")
    before = report_json.read_text(encoding="utf-8")
    run(["--approve", str(report_json), "--answers", str(answers_at(tmp_path, BLOCK))])
    assert report_json.read_text(encoding="utf-8") == before


def test_a_report_scored_by_other_rules_is_refused(tmp_path):
    report_json = saved(tmp_path, built(None))
    document = json.loads(report_json.read_text(encoding="utf-8"))
    document["run"]["scoring_rules_version"] = "ors-99"
    report_json.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    code, _out, error = run(
        ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, BLOCK))]
    )
    assert code == COULD_NOT_RUN
    assert "ors-99" in error
    assert "version that wrote it" in error


def test_an_answers_file_with_no_approval_block_is_refused(tmp_path):
    report_json = saved(tmp_path, built(None))
    code, _out, error = run(
        ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, None))]
    )
    assert code == COULD_NOT_RUN
    assert "no approval block" in error


def test_an_answers_file_whose_decision_is_no_decision_is_named_and_refused(tmp_path):
    # read_approval names only the bad value; the approve path names the file too.
    report_json = saved(tmp_path, built(None))
    block = {"approver": "dana", "decision": "maybe", "recorded_at": "2026-10-20T10:00:00Z"}
    code, _out, error = run(
        ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, block))]
    )
    assert code == COULD_NOT_RUN
    assert "answers.json" in error
    assert "'maybe' is not a decision" in error


def test_an_answers_file_whose_time_is_no_instant_is_named_and_refused(tmp_path):
    report_json = saved(tmp_path, built(None))
    block = {"approver": "dana", "decision": "approved", "recorded_at": "yesterday"}
    code, _out, error = run(
        ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, block))]
    )
    assert code == COULD_NOT_RUN
    assert "answers.json" in error
    assert "'yesterday' is not an ISO 8601 instant" in error


def test_a_report_that_already_carries_an_approval_is_refused(tmp_path):
    _json, code, _out, error = approve_saved(tmp_path, built(DECISION))
    assert code == COULD_NOT_RUN
    assert "already carries an approval" in error
    assert "--replace-approval" in error


def test_a_report_whose_json_is_malformed_is_named_and_refused_not_a_traceback(tmp_path):
    # A non-numeric line number raises inside the loader; it is wrapped, named, and exits 2,
    # rather than escaping as a traceback a pipeline would read as findings.
    report_json = saved(tmp_path, built_with_secret())
    document = json.loads(report_json.read_text(encoding="utf-8"))
    document["secrets"][0]["start_line"] = "abc"
    report_json.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    code, _out, error = run(
        ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, BLOCK))]
    )
    assert code == COULD_NOT_RUN
    assert "vulnscout.json" in error
    assert "is not a report this tool can read" in error


@NEEDS_PERMISSIONS
def test_a_read_only_report_file_is_refused_before_any_is_rewritten(tmp_path):
    report_json = saved(tmp_path, built(None))
    before = {suffix: (tmp_path / f"vulnscout{suffix}").read_text() for suffix in RENDERERS}
    read_only = tmp_path / "vulnscout.html"
    read_only.chmod(READ_ONLY)
    try:
        code, _out, error = run(
            ["--approve", str(report_json), "--answers", str(answers_at(tmp_path, BLOCK))]
        )
        assert code == COULD_NOT_RUN
        assert "not writable" in error
        for suffix in RENDERERS:
            assert (tmp_path / f"vulnscout{suffix}").read_text() == before[suffix]
    finally:
        read_only.chmod(OWNER_WRITE)


def test_no_report_to_approve_is_refused(tmp_path):
    code, _out, error = run(
        ["--approve", str(tmp_path / "missing.json"), "--answers", str(answers_at(tmp_path, BLOCK))]
    )
    assert code == COULD_NOT_RUN
    assert "no report to approve" in error

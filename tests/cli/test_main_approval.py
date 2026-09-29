"""Guards on a run whose findings need approval: said plainly, and no new exit code for it."""

import json

from cli.main import FOUND_SOMETHING
from cli_samples import run_command_line, written_answers
from report.summary_words import UNAPPROVED


def test_a_finding_needing_approval_with_none_recorded_exits_one_like_any_finding(
    monkeypatch, tmp_path
):
    # The sample's sources disagree, so it needs approval, and no answer file carries one.
    code, out, _ = run_command_line([], monkeypatch, tmp_path)
    assert code == FOUND_SOMETHING
    assert UNAPPROVED in " ".join(out.split("\n\n")[1].split("\n"))


def test_an_approved_run_needing_approval_exits_one_too_and_counts_the_finding(
    monkeypatch, tmp_path
):
    given = ["--answers", str(written_answers(tmp_path)), "--format", "json"]
    code, out, _ = run_command_line(given, monkeypatch, tmp_path)
    assert code == FOUND_SOMETHING
    assert json.loads(out)["run"]["findings_needing_approval"] == 1

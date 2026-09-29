"""Guards on a run that finds a secret: exit 1, never weighed, and the secret nowhere at all."""

import json
import re
from pathlib import Path

from cli.main import FOUND_SOMETHING
from cli.report_files import SUFFIXES
from cli_samples import LODASH, REPORTS_FOLDER, REPOSITORY_NAME, run_command_line, written_answers
from deps.trivy_secrets import SecretFinding
from report.absences import NOTHING_TO_WEIGH

# Trivy's own report, captured offline over a scratch folder of two made-up tokens.
CAPTURED = Path(__file__).parents[1] / "deps" / "fixtures" / "trivy_report_secrets.json"
# The two tokens that folder held, made up and granting nothing. Split so no
# secret scanner reads this file as holding one.
TOKENS = {
    "github-pat": "ghp_" + "FAKEtokenFORtestsNOTreal0123456789ab",
    "gitlab-pat": "glpat-" + "FAKEnotREALtoken0000",
}
MASK = re.compile(r"\*{8,}")
SECRET = SecretFinding(
    "config/settings.py", 2, 2, "github-pat", "GitHub", "CRITICAL",
    "GitHub Personal Access Token",
)
NOTHING_ELSE = {"components": (LODASH,), "advisories": {}}


def unmasked() -> dict:
    """Give the captured report as a Trivy that failed to mask would write it."""
    report = json.loads(CAPTURED.read_text(encoding="utf-8"))
    report["Results"] = [unmasked_result(one) for one in report["Results"]]
    return report


def unmasked_result(result: dict) -> dict:
    """Put each secret's token back where Trivy masked it, in its match and its quoted lines."""
    return {**result, "Secrets": [unmasked_entry(one) for one in result.get("Secrets") or []]}


def unmasked_entry(entry: dict) -> dict:
    """Put one secret's token back in its match and in every line of code Trivy quoted."""
    token = TOKENS[entry["RuleID"]]
    quoted = entry["Code"]["Lines"]
    lines = [{**line, "Content": MASK.sub(token, line["Content"])} for line in quoted]
    return {**entry, "Match": MASK.sub(token, entry["Match"]), "Code": {"Lines": lines}}


def everything_written(tmp_path: Path, out: str, error: str) -> str:
    """Gather what a run printed and every report it wrote into one text to search."""
    folder = tmp_path / REPORTS_FOLDER
    named = [folder / f"{REPOSITORY_NAME}{suffix}" for suffix in SUFFIXES.values()]
    return "\n".join([out, error, *(path.read_text(encoding="utf-8") for path in named)])


def test_the_captured_report_masks_its_tokens_and_unmasking_puts_them_back():
    # Holds the test below to its premise: the tokens are in what the run is handed.
    captured, undone = CAPTURED.read_text(encoding="utf-8"), json.dumps(unmasked())
    assert all(token not in captured and token in undone for token in TOKENS.values())


def test_no_secret_trivy_failed_to_mask_reaches_stdout_stderr_or_any_report(monkeypatch, tmp_path):
    code, out, error = run_command_line([], monkeypatch, tmp_path, trivy_report=unmasked())
    assert code == FOUND_SOMETHING
    written = everything_written(tmp_path, out, error)
    assert "SECRETS (2)" in written
    assert [token for token in TOKENS.values() if token in written] == []


def test_a_run_that_found_only_a_secret_exits_one_like_any_finding(monkeypatch, tmp_path):
    code, out, _ = run_command_line([], monkeypatch, tmp_path, secrets=(SECRET,), **NOTHING_ELSE)
    assert code == FOUND_SOMETHING
    assert "0 findings across 1 component" in out


def test_a_secret_is_never_weighed_into_an_organisation_risk_score(monkeypatch, tmp_path):
    given = ["--answers", str(written_answers(tmp_path)), "--format", "json"]
    _, out, _ = run_command_line(given, monkeypatch, tmp_path, secrets=(SECRET,), **NOTHING_ELSE)
    record = json.loads(out)
    absent = {one["what"]: one["because"] for one in record["not_assessed"]}
    assert record["run"]["secret_count"] == 1
    assert absent["Organisation Risk Score"] == NOTHING_TO_WEIGH

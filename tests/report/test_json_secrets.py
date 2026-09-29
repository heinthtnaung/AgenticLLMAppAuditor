"""Guards on the secrets in the audit artefact: each one's place and rule, and their count."""

import json

from report.json_report import as_json
from report.record import build_report
from report_samples import PROVENANCE, catalogue, component, secret


def written(*secrets) -> dict:
    """Write a record carrying these secrets and read the JSON back."""
    report = build_report(PROVENANCE, catalogue(component()), (), {}, secrets=secrets)
    return json.loads(as_json(report))


def test_each_secret_is_written_with_its_file_lines_and_rule():
    assert written(secret("keys/deploy.pem", 1, end_line=27))["secrets"] == [{
        "file": "keys/deploy.pem", "start_line": 1, "end_line": 27, "rule_id": "github-pat",
        "category": "GitHub", "severity": "CRITICAL", "title": "GitHub Personal Access Token",
    }]


def test_the_run_counts_the_secrets_at_none_as_well():
    assert written()["run"]["secret_count"] == 0
    assert written(secret(), secret("b.env", 1))["run"]["secret_count"] == 2


def test_a_secret_is_not_a_finding_and_is_never_weighed():
    record = written(secret())
    assert record["findings"] == [] and record["run"]["finding_count"] == 0

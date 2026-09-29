"""Guards on reading a Trivy report's secrets: where each one is, and never the secret."""

from dataclasses import fields

import pytest

from deps.scanner import ScannerFailed
from deps.trivy_report import read_advisories
from deps.trivy_secrets import SecretFinding, read_secrets
from samples import PYYAML_PURL, load

# Captured from Trivy 0.74.0, offline, over a scratch folder holding PyYAML 5.1
# and two made-up tokens: one run, both scanners, one document.
REPORT = "trivy_report_secrets.json"
# Made up here, and split so no secret scanner reads this file as holding one.
PLAINLY_FAKE = "ghp_" + "HANDbuiltFAKEvalueNOTaTOKEN000000000"

GITLAB = SecretFinding(
    "config/deploy.env", 1, 1, "gitlab-pat", "GitLab", "CRITICAL",
    "GitLab Personal Access Token",
)
GITHUB = SecretFinding(
    "config/settings.py", 2, 2, "github-pat", "GitHub", "CRITICAL",
    "GitHub Personal Access Token",
)


def secret_entry(**overrides) -> dict:
    """Build one Trivy secret in the shape Trivy emits it, its mask undone, changed as asked."""
    entry = {
        "RuleID": "github-pat", "Category": "GitHub", "Severity": "CRITICAL",
        "Title": "GitHub Personal Access Token", "StartLine": 2, "EndLine": 2,
        "Match": f'GITHUB_TOKEN = "{PLAINLY_FAKE}"',
        "Code": {"Lines": [{"Number": 2, "Content": f'GITHUB_TOKEN = "{PLAINLY_FAKE}"'}]},
    }
    return {**entry, **overrides}


def report_with(*entries, target: object = "config/settings.py") -> dict:
    """Wrap secrets in the result Trivy files them under."""
    return {"Results": [{"Target": target, "Class": "secret", "Secrets": list(entries)}]}


def test_every_secret_is_read_with_its_file_lines_and_rule_in_file_order():
    assert read_secrets(load(REPORT)) == (GITLAB, GITHUB)


def test_the_run_that_found_the_secrets_found_the_advisories_too():
    assert list(read_advisories(load(REPORT))) == [PYYAML_PURL]


def test_a_secret_finding_has_no_field_that_could_carry_the_secret():
    # Trivy's mask is its promise, not this tool's: `Match` and the quoted code are never read.
    named = {field.name for field in fields(SecretFinding)}
    kept = {"target", "start_line", "end_line", "rule_id", "category", "severity", "title"}
    assert named == kept


def test_a_secret_trivy_left_unmasked_is_read_without_its_value():
    read = read_secrets(report_with(secret_entry()))
    assert read == (GITHUB,)
    assert PLAINLY_FAKE not in repr(read)


@pytest.mark.parametrize("report", [
    {"Results": [{"Target": "requirements.txt", "Vulnerabilities": []}]},
    report_with(),
    {},
], ids=["no secrets key", "empty secrets", "no results"])
def test_a_report_whose_rules_matched_nothing_gives_no_secrets(report):
    assert read_secrets(report) == ()


def test_secrets_come_back_in_file_then_line_order_whatever_order_trivy_wrote():
    later, earlier = secret_entry(StartLine=9, EndLine=9), secret_entry(StartLine=3, EndLine=4)
    assert [one.start_line for one in read_secrets(report_with(later, earlier))] == [3, 9]


@pytest.mark.parametrize("changed, fault", [
    ({"RuleID": ""}, "carries no 'RuleID'"),
    ({"Title": None}, "carries no 'Title'"),
    ({"Severity": 4}, "carries no 'Severity'"),
    ({"StartLine": 0}, "no line number in 'StartLine'"),
    ({"StartLine": True}, "no line number in 'StartLine'"),
    ({"EndLine": "2"}, "no line number in 'EndLine'"),
    ({"StartLine": 5, "EndLine": 4}, "ends before it starts"),
])
def test_a_malformed_secret_is_refused_naming_its_file_and_the_fault(changed, fault):
    with pytest.raises(ScannerFailed) as refused:
        read_secrets(report_with(secret_entry(**changed)))
    assert "in 'config/settings.py'" in str(refused.value) and fault in str(refused.value)


def test_a_refusal_never_quotes_the_field_it_refused():
    with pytest.raises(ScannerFailed) as refused:
        read_secrets(report_with(secret_entry(StartLine=PLAINLY_FAKE)))
    assert PLAINLY_FAKE not in str(refused.value)


@pytest.mark.parametrize("report, fault", [
    (report_with("a string"), "must be a JSON object"),
    ({"Results": [{"Target": "x", "Secrets": {"RuleID": "r"}}]}, "must be a list"),
    (report_with(secret_entry(), target=None), "names no 'Target'"),
])
def test_a_secrets_block_of_the_wrong_shape_is_refused(report, fault):
    with pytest.raises(ScannerFailed, match=fault):
        read_secrets(report)


def test_a_document_that_is_no_trivy_report_is_refused():
    with pytest.raises(ScannerFailed, match="A Trivy report must be a JSON object"):
        read_secrets([])

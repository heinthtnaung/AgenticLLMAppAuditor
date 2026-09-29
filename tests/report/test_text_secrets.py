"""Guards on the terminal's secrets block: two lines a secret, and said at none."""

from report.record import build_report
from report.secret_words import NONE_MATCHED
from report.text_report import as_text
from report.text_secrets import secrets_block
from report_samples import PROVENANCE, catalogue, component, secret


def recorded(*secrets):
    """Build a record carrying these secrets and one component."""
    return build_report(PROVENANCE, catalogue(component()), (), {}, secrets=secrets)


def test_each_secret_is_placed_on_one_line_and_described_on_the_next():
    printed = secrets_block(recorded(secret(), secret("keys/deploy.pem", 1, end_line=27)))
    assert printed.split("\n") == [
        "SECRETS (2)",
        "  config/settings.py:2",
        "    CRITICAL  ·  GitHub Personal Access Token  ·  GitHub  ·  rule github-pat",
        "  keys/deploy.pem:1-27",
        "    CRITICAL  ·  GitHub Personal Access Token  ·  GitHub  ·  rule github-pat",
    ]


def test_a_run_whose_rules_matched_nothing_says_so_rather_than_leaving_the_block_out():
    assert secrets_block(recorded()).split("\n") == ["SECRETS (0)", f"  {NONE_MATCHED}"]


def test_the_block_is_on_the_page_after_the_findings_and_before_what_matched_nothing():
    page = as_text(recorded(secret()))
    assert page.index("SECRETS (1)") < page.index("MATCHED NOTHING")

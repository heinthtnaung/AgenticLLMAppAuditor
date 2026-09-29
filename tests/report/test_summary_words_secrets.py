"""Guards on the summary's secret count: said at none, and on both pages."""

import html

import pytest

from report.html_report import as_html
from report.record import build_report
from report.summary_words import secrets_count
from report.text_report import as_text
from report_samples import PROVENANCE, catalogue, component, secret


def recorded(*secrets):
    """Build a record carrying these secrets and one component."""
    return build_report(PROVENANCE, catalogue(component()), (), {}, secrets=secrets)


@pytest.mark.parametrize("found, said", [(0, "0 secrets"), (1, "1 secret"), (2, "2 secrets")])
def test_the_secrets_are_counted_by_the_rules_that_looked_at_none_as_well(found, said):
    secrets = [secret(start_line=line) for line in range(1, found + 1)]
    counted = secrets_count(recorded(*secrets))
    assert counted == f"{said} matched the secret rules built into Trivy."


def test_both_pages_carry_the_count_in_their_summary():
    report = recorded(secret())
    assert secrets_count(report) in as_text(report).split("\n\n")[1].split("\n")
    assert f'<p class="count">{html.escape(secrets_count(report))}</p>' in as_html(report)

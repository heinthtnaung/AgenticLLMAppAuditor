"""Guards on the page's secrets section: where each one is, and said at none."""

import html

from report.html_report import as_html
from report.html_secrets import secrets_section
from report.record import build_report
from report.secret_words import NONE_MATCHED
from report_samples import PROVENANCE, catalogue, component, secret

SEPARATOR = '<span class="separator">·</span>'


def recorded(*secrets):
    """Build a record carrying these secrets and one component."""
    return build_report(PROVENANCE, catalogue(component()), (), {}, secrets=secrets)


def test_each_secret_is_listed_by_its_place_then_what_matched_it():
    said = SEPARATOR.join([
        "<code>config/settings.py:2</code>", "CRITICAL", "GitHub Personal Access Token",
        "GitHub", "rule github-pat",
    ])
    page = secrets_section(recorded(secret()))
    assert "<h2>Secrets (1)</h2>" in page
    assert f'<ul class="secrets"><li>{said}</li></ul>' in page


def test_a_run_whose_rules_matched_nothing_says_so_rather_than_leaving_the_section_out():
    page = secrets_section(recorded())
    assert "<h2>Secrets (0)</h2>" in page
    assert f'<p class="note">{html.escape(NONE_MATCHED)}</p>' in page


def test_the_section_is_on_the_page_before_what_matched_nothing():
    page = as_html(recorded(secret()))
    assert page.index("Secrets (1)") < page.index("Matched nothing")

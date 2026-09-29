"""Guards on the page's Secrets tab: where each one is, said at none, and kept in the redesign.

The template the redesign follows has no secrets tab; these hold that the section
the tool already carried is still on the page, on a tab of its own, rather than
dropped in the move.
"""

import html

from report.html_report import as_html
from report.html_secrets import secrets_panel
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
    page = secrets_panel(recorded(secret()))
    assert "<h2>Secrets (1)</h2>" in page
    assert f'<ul class="secrets"><li>{said}</li></ul>' in page


def test_a_run_whose_rules_matched_nothing_says_so_rather_than_leaving_the_tab_out():
    page = secrets_panel(recorded())
    assert "<h2>Secrets (0)</h2>" in page
    assert f'<p class="note">{html.escape(NONE_MATCHED)}</p>' in page


def test_the_secrets_tab_and_its_panel_are_on_the_whole_page():
    # The digest and the secrets are the two sections the template lacks; the
    # redesign keeps both, secrets on a tab of their own.
    page = as_html(recorded(secret()))
    assert 'data-tab="secrets" aria-controls="panel-secrets"' in page
    assert 'id="panel-secrets"' in page
    assert "config/settings.py:2" in page

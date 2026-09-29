"""The secrets on their own tab: each one's file and lines, and what matched it.

The template the redesign follows has no secrets tab; this one keeps the section
the tool already carried rather than dropping it in the move. With none matched,
the tab says so rather than going missing. The secret itself is never on the page,
because the record never holds it (`deps.trivy_secrets`).
"""

from report.html_layout import empty_note, listing, panel_head, separated, tag, text
from report.record import Report
from report.secret_words import NONE_MATCHED, described, location_of

SECRETS_LEDE = (
    "Where one of Trivy's built-in rules matched something shaped like a credential. "
    "Only the file, the lines and the rule are shown: the secret is not on this page, "
    "and not in the record behind it."
)


def secrets_panel(report: Report) -> str:
    """Give the Secrets tab: every secret a rule matched, or that none did."""
    head = panel_head(f"Secrets ({len(report.secrets)})", SECRETS_LEDE)
    if not report.secrets:
        return head + empty_note(NONE_MATCHED)
    entries = [secret_entry(one) for one in report.secrets]
    return head + listing(entries, "secrets")



def secret_entry(secret) -> str:
    """Give one secret: where it is, then what matched it."""
    said = [text(one) for one in described(secret)]
    return separated([tag("code", text(location_of(secret))), *said])

"""The secrets on the page: each one's file and lines, and what matched it.

With none, the section says so rather than going missing. The secret itself is
not on the page, because the record never holds it (`deps.trivy_secrets`).
"""

from report.html_layout import listing, section, separated, tag, text
from report.record import Report
from report.secret_words import NONE_MATCHED, described, location_of

SECRETS_LEDE = (
    "Where one of Trivy's built-in rules matched something shaped like a credential. "
    "Only the file, the lines and the rule are shown: the secret is not on this page, "
    "and not in the record behind it."
)


def secrets_section(report: Report) -> str:
    """List every secret a rule matched, or say plainly that none did."""
    title = f"Secrets ({len(report.secrets)})"
    if not report.secrets:
        return section(title, SECRETS_LEDE, tag("p", text(NONE_MATCHED), "note"))
    entries = [secret_entry(one) for one in report.secrets]
    return section(title, SECRETS_LEDE, listing(entries, "secrets"))


def secret_entry(secret) -> str:
    """Give one secret: where it is, then what matched it."""
    said = [text(one) for one in described(secret)]
    return separated([tag("code", text(location_of(secret))), *said])

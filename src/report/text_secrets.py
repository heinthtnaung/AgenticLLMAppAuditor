"""The secrets on the terminal: each one's file and lines, then what matched it.

Two lines each, because a path is as long as the tree is deep and a column wide
enough for the longest would push everything else off the page. With none, the
block says so rather than going missing, and the secret itself is never here.
"""

from report.record import Report
from report.secret_words import NONE_MATCHED, described, location_of
from report.text_layout import INDENT, SOURCE_SEPARATOR, section

SECRETS_TITLE = "SECRETS"


def secrets_block(report: Report) -> str:
    """List every secret a rule matched, or say plainly that none did."""
    title = f"{SECRETS_TITLE} ({len(report.secrets)})"
    if not report.secrets:
        return section(title, [f"{INDENT}{NONE_MATCHED}"])
    return section(title, [secret_entry(one) for one in report.secrets])


def secret_entry(secret) -> str:
    """Give one secret: where it is on the first line, what matched it on the second."""
    return f"{INDENT}{location_of(secret)}\n{INDENT * 2}{SOURCE_SEPARATOR.join(described(secret))}"

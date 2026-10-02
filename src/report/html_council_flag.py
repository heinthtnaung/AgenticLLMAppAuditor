"""The same-evidence flag as a compact badge, named once for the overview cell and the card.

It shows, beside a council ruling, the metrics members read two ways from the same
words -- read off the record's rulings (`report.council_record`), never worked out
here. It is informational: it moves no filter count, tag or approval, and the full
sentence is the council tab's, in `report.council_words`.
"""

from report.council_queries import flagged_metrics
from report.council_record import CouncilOutcome
from report.html_layout import tag, text

SAME_EVIDENCE_LABEL = "same evidence"


def same_evidence_flag(outcome: CouncilOutcome | None) -> str:
    """Give the flag naming the metrics read two ways from the same words, else nothing."""
    if outcome is None:
        return ""
    metrics = flagged_metrics(outcome)
    if not metrics:
        return ""
    return tag("span", text(f"{SAME_EVIDENCE_LABEL}: {', '.join(metrics)}"), "flag")

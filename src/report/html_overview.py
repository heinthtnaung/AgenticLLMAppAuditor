"""The Overview tab: the tiles a reader lands on, the two scales named, and every finding.

**The two scales are named before a reader meets either.** A published CVSS base
score and the Organisation Risk Score are two claims this page never merges
(`docs/SCORING_MODEL.md`), so the callout says which is which above the table that
shows both.

**The All findings table lists what each finding carries, no source a column.** A
column headed `nvd` is empty on most rows of a real repository, so the CVSS and
Org risk cells each hold one mini chip per source the finding actually has. The
table filters by whether a finding needs approval, disagrees, agrees or was
settled, and searches by text; with no script it is the full table, unfiltered.
"""

from report.approval_needed import needing_approval
from report.council_beside import council_figure
from report.disagreement import sources_agree, sources_disagree
from report.html_filters import Segment, empty_line, search_box, segmented, toolbar
from report.html_layout import tag, text
from report.html_overview_rows import finding_row
from report.html_overview_tiles import stat_tiles, two_scales
from report.record import Report
from report.summary_words import (
    approval_count, counts, inventory_pointer, secrets_count, unread_pointer,
)
from report.html_absences import approval_card, not_assessed_card

FINDINGS_TABLE = "findings-table"
COLUMNS = ("Advisory", "Sources", "CVSS", "Org risk", "Council", "Approval")


def overview_panel(report: Report) -> str:
    """Give the Overview tab: the summary tiles, the two scales, the side cards, all findings."""
    split = tag("div", two_scales() + side_cards(report), "split")
    return stat_tiles(report) + split + all_findings(report)


def side_cards(report: Report) -> str:
    """Put the two overview cards -- the human act, and what was not done -- side by side."""
    return tag("div", approval_card(report) + not_assessed_card(report), "side-cards")


def all_findings(report: Report) -> str:
    """Head the findings table with the run's counts, filter it, and list every finding."""
    head = tag("div", tag("h2", text("All findings")) + summary_block(report), "section-head")
    return head + findings_toolbar(report) + findings_table(report)


def summary_block(report: Report) -> str:
    """Give the count paragraphs: the findings, then the approval, then the secrets."""
    pointers = (inventory_pointer(report), unread_pointer(report))
    said = " ".join(part for part in (counts(report), *pointers) if part)
    block = tag("p", text(said), "count") + approval_line(report)
    return block + tag("p", text(secrets_count(report)), "count")


def approval_line(report: Report) -> str:
    """Count the findings needing approval in a paragraph of its own, or give nothing when none."""
    said = approval_count(report)
    return tag("p", text(said), "count") if said else ""


def findings_toolbar(report: Report) -> str:
    """Give the filter bar over the findings table: the segmented tags and a search box."""
    search = search_box("Search findings", "Search CVE or component…")
    return toolbar(FINDINGS_TABLE, segmented(segments(report)) + search)


def segments(report: Report) -> tuple[Segment, ...]:
    """Count each filter by the same predicate the record uses, so the counts cannot drift."""
    findings = report.findings
    disagree = [one for one in findings if sources_disagree(one)]
    agree = [one for one in findings if sources_agree(one)]
    settled = [one for one in findings if council_figure(report, one.advisory.advisory_id)]
    return (
        Segment("all", "All", len(findings)),
        Segment("approval", "Needs approval", len(needing_approval(report))),
        Segment("disagree", "Disagree", len(disagree)),
        Segment("agree", "Agree", len(agree)),
        Segment("settled", "Council settled", len(settled)),
    )


def findings_table(report: Report) -> str:
    """Give the table itself, carrying the id the filter bar reads, one row per finding."""
    header = tag("tr", "".join(tag("th", text(one)) for one in COLUMNS))
    rows = "".join(finding_row(report, one) for one in report.findings)
    body = tag("thead", header) + tag("tbody", rows)
    table = f'<table id="{FINDINGS_TABLE}" class="data rt">{body}</table>'
    return tag("div", table + empty_line("No finding matches."), "table-wrap")

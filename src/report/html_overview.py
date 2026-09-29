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

from cvss.score import severity_band
from report.approval_needed import needing_approval, reasons_for
from report.council_beside import council_figure
from report.disagreement import agreement_unchecked, score_spread, sources_agree, sources_disagree
from report.html_filters import Segment, empty_line, search_box, segmented, toolbar
from report.html_layout import (
    CVSS_SCALE, badge, cell, jump, mini_chip, number, scored_chip, tag, text,
)
from report.html_overview_council import council_cell
from report.html_overview_tiles import stat_tiles, two_scales
from report.html_risk import NO_SOURCE, RISK_SCALE, source_of
from report.record import Report
from report.summary_words import (
    approval_count, counts, inventory_pointer, secrets_count, unread_pointer,
)
from report.html_absences import approval_card, not_assessed_card

FINDINGS_TABLE = "findings-table"
COLUMNS = ("Advisory", "Sources", "CVSS", "Org risk", "Council", "Approval")
# A mini chip's shape class: a CVSS square and an Organisation Risk pill, never one badge.
RISK_SHAPE = "risk"
DASH = "—"


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


def finding_row(report: Report, finding) -> str:
    """Give one finding's row: what it is, its scores by source, its council and approval."""
    advisory_id = finding.advisory.advisory_id
    cells = (
        advisory_cell(finding),
        sources_cell(finding),
        cvss_cell(finding),
        risk_cell(report, advisory_id),
        council_cell(report, advisory_id),
        approval_cell(report, finding),
    )
    return f'<tr data-tags="{row_tags(report, finding)}">{"".join(cells)}</tr>'


def row_tags(report: Report, finding) -> str:
    """Give the filter tags on one row: its group by the record's predicate, and its marks."""
    tags = [group_tag(finding)]
    if reasons_for(report, finding):
        tags.append("approval")
    if council_figure(report, finding.advisory.advisory_id):
        tags.append("settled")
    return " ".join(tags)


def group_tag(finding) -> str:
    """Name the group a finding belongs to, by the same predicate the panels split on."""
    if sources_disagree(finding):
        return "disagree"
    if sources_agree(finding):
        return "agree"
    return "refused" if agreement_unchecked(finding) else "unscored"


def advisory_cell(finding) -> str:
    """Give the advisory cell: a link to the finding's home tab, and the component under it."""
    advisory_id = finding.advisory.advisory_id
    home = "disagree" if sources_disagree(finding) else "agree"
    named = jump(f"{home}/{advisory_id}", text(advisory_id))
    installed = f"{finding.component.name} {finding.component.version}"
    component = tag("span", text(installed), "component")
    return cell("Advisory", tag("div", named + component, "cell-adv"))


def sources_cell(finding) -> str:
    """Give the sources cell: the badge for how they relate, and the spread when they disagree."""
    if sources_disagree(finding):
        sub = tag("span", text(f"{number(score_spread(finding))} apart"), "sub")
        return cell("Sources", tag("div", badge("Disagree", "alarm") + sub, "stack"))
    if not finding.is_scored:
        return cell("Sources", badge("Not scored", "muted"))
    label, tone = ("Refused", "muted") if finding.unreadable else ("Agree", "ok")
    return cell("Sources", badge(label, tone))


def cvss_cell(finding) -> str:
    """Give the CVSS cell: one mini chip per source, in the order the finding carries them."""
    chips = [cvss_mini(one) for one in finding.scores]
    return cell("CVSS", tag("div", "".join(chips) or DASH, "minis"))


def cvss_mini(score) -> str:
    """Give one source's published CVSS score as a mini chip."""
    band = severity_band(score.base_score)
    return mini_chip(score.source, number(score.base_score), band, CVSS_SCALE)


def risk_cell(report: Report, advisory_id: str) -> str:
    """Give the Org risk cell: one mini chip per source, linked to the finding's risk entry."""
    weighed = report.risk.get(advisory_id)
    if weighed is None:
        return cell("Org risk", tag("div", DASH, "minis"))
    chips = "".join(risk_mini(one) for one in weighed.scores)
    return cell("Org risk", jump(f"risk/{advisory_id}", chips, "goto cell-link minis"))


def risk_mini(scored) -> str:
    """Give one source's org score as a mini pill, or the full org chip where none scored."""
    # The no-source sentinel is a sentence, not a source, so it gets the full org
    # chip rather than a mini whose source column a sentence would overflow.
    if source_of(scored) == NO_SOURCE:
        return scored_chip(RISK_SCALE, number(scored.score), scored.band, "risk")
    return mini_chip(source_of(scored), number(scored.score), scored.band, RISK_SHAPE)


def approval_cell(report: Report, finding) -> str:
    """Give the Approval cell: the mark where the finding needs one, else a dash."""
    if reasons_for(report, finding):
        return cell("Approval", badge("Needs approval", "alarm"))
    return cell("Approval", DASH)

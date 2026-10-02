"""One finding's row in the All findings table: its cells, filter tags and phone labels.

Its own file so `report.html_overview` stays under the size limit and about the
table as a whole. Each cell holds one mini chip per source the finding carries, so
a source is never a column, and the CVSS and Organisation Risk scores are never
merged (`docs/SCORING_MODEL.md`), so their minis never look alike: the CVSS one
outlined with a band-coloured edge, the Organisation Risk one filled with its
band colour.
"""

from cvss.score import severity_band
from report.approval_needed import reasons_for
from report.council_beside import council_figure
from report.disagreement import agreement_unchecked, score_spread, sources_agree, sources_disagree
from report.html_layout import (
    CVSS_SCALE,
    badge,
    cell,
    jump,
    mini_chip,
    number,
    scored_chip,
    tag,
    text,
)
from report.html_overview_council import council_cell
from report.html_risk import NO_SOURCE, RISK_SCALE, source_of
from report.record import Report

# The stacked-row labels a phone reads: longer than the desktop headers because a
# cell that stacks under its label has room the column head does not, and it says
# a cell holds one score per source, as the template's data-labels do.
CVSS_PHONE_LABEL = "CVSS by source"
RISK_PHONE_LABEL = "Org risk by source"
# A mini's fill class: the Organisation Risk mini filled with its band colour, the
# CVSS mini outlined with a band-coloured edge, never one badge.
RISK_FILL = "risk"
DASH = "—"


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
    return cell(CVSS_PHONE_LABEL, tag("div", "".join(chips) or DASH, "minis"))


def cvss_mini(score) -> str:
    """Give one source's published CVSS score as a mini chip."""
    band = severity_band(score.base_score)
    return mini_chip(score.source, number(score.base_score), band, CVSS_SCALE)


def risk_cell(report: Report, advisory_id: str) -> str:
    """Give the Org risk cell: one mini chip per source, linked to the finding's risk entry."""
    weighed = report.risk.get(advisory_id)
    if weighed is None:
        return cell(RISK_PHONE_LABEL, tag("div", DASH, "minis"))
    chips = "".join(risk_mini(one) for one in weighed.scores)
    return cell(RISK_PHONE_LABEL, jump(f"risk/{advisory_id}", chips, "goto cell-link minis"))


def risk_mini(scored) -> str:
    """Give one source's org score as a filled mini, or the full org chip where none scored."""
    # The no-source sentinel is a sentence, not a source, so it gets the full org
    # chip rather than a mini whose source column a sentence would overflow.
    if source_of(scored) == NO_SOURCE:
        return scored_chip(RISK_SCALE, number(scored.score), scored.band, "risk")
    return mini_chip(source_of(scored), number(scored.score), scored.band, RISK_FILL)


def approval_cell(report: Report, finding) -> str:
    """Give the Approval cell: the mark where the finding needs one, else a dash."""
    if reasons_for(report, finding):
        return cell("Approval", badge("Needs approval", "alarm"))
    return cell("Approval", DASH)

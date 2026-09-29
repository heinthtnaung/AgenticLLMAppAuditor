"""The parts a finding card is built from, shared by the Disagreements and Agreements tabs.

Its own file because both tabs assemble the same head, source table and refused
list; `report.html_findings` decides which cards a reader sees and in what order,
and this renders one of them, so the two change for different reasons.

**Every source is a row, and no source has a column.** A table headed `nvd` is
empty on most rows of a real repository, so what is rendered is the list the
finding carries, in name order, which is not a ranking. A refused vector is kept
on the card, marked not scored and never as 0.0.
"""

from cvss.score import severity_band
from report.approval_needed import NEEDS_APPROVAL, reasons_for
from report.html_layout import (
    CVSS_SCALE, badge, cell, external_link, jump, listing, number, scored_chip, tag, text,
)
from report.html_vector import vector_markup
from report.record import Report

NOTHING_PUBLISHED = "No source published a readable v3 vector."


def article(finding, prefix: str, body: str) -> str:
    """Wrap one finding's card with the id its tab routes to, so a link can scroll to it."""
    ident = f'id="{prefix}-{text(finding.advisory.advisory_id)}"'
    return f'<article class="card finding" {ident}>{body}</article>'


def card_head(report: Report, finding) -> str:
    """Head a card with the advisory, the component, and the approval mark where it has one."""
    installed = f"{finding.component.name} {finding.component.version}"
    named = tag("span", advisory_name(finding.advisory), "adv")
    named += tag("span", text(installed), "component")
    return tag("header", tag("div", named, "title") + approval_badge(report, finding), "card-head")


def approval_badge(report: Report, finding) -> str:
    """Mark a finding needing approval, naming the halves of the rule it meets."""
    reasons = reasons_for(report, finding)
    if not reasons:
        return ""
    said = " and ".join(reason.value for reason in reasons)
    return badge(f"{NEEDS_APPROVAL}: {said}", "alarm")


def advisory_name(advisory) -> str:
    """Give the advisory's id, linked to its page with an external-link mark, or as plain text."""
    if advisory.url is None:
        return text(advisory.advisory_id)
    return external_link(advisory.url, text(advisory.advisory_id))


def source_table(finding) -> str:
    """Put every source's score and vector in a compact table, one row each, in name order."""
    head = "<thead><tr><th>Source</th><th>CVSS</th><th>Vector</th></tr></thead>"
    differing = tuple(finding.disputed_metrics())
    rows = "".join(source_row(one, differing) for one in finding.scores)
    return tag("table", head + tag("tbody", rows), "data compact rt")


def source_row(score, differing: tuple[str, ...]) -> str:
    """Give one source: its name, the score its vector comes to, and the vector metric by metric."""
    band = severity_band(score.base_score)
    chip = scored_chip(CVSS_SCALE, number(score.base_score), band, "cvss")
    return "<tr>" + cell("Source", tag("span", text(score.source), "source-name")) + cell(
        "CVSS", chip
    ) + cell("Vector", vector_markup(score.vector, differing)) + "</tr>"


def unreadable_table(finding) -> str:
    """List every source this calculator refused, kept as not scored and never as 0.0."""
    return listing([unreadable_row(one) for one in finding.unreadable], "sources")


def unreadable_row(source) -> str:
    """Give one refused source: what it published, and why the calculator would not read it."""
    return (
        tag("span", text(source.source), "source-name")
        + tag("span", "not scored", "not-scored")
        + tag("code", text(source.vector), "vector")
        + tag("span", text(source.refusal), "refusal")
    )


def nothing_published() -> str:
    """Say plainly that no source published a readable vector for a finding."""
    return tag("p", text(NOTHING_PUBLISHED), "spread")


def card_links(report: Report, finding) -> str:
    """Link a card to the finding's other views, where those views carry it."""
    advisory_id = finding.advisory.advisory_id
    links = []
    if advisory_id in report.risk:
        links.append(jump(f"risk/{advisory_id}", text("Org risk") + " &rarr;"))
    if advisory_id in report.council:
        links.append(jump(f"council/{advisory_id}", text("Council ruling") + " &rarr;"))
    return tag("p", "".join(links), "card-links") if links else ""

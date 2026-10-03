"""The Overview tab's summary tiles, and the callout that names the two scales apart.

Its own file so `report.html_overview` stays about the findings table. Each tile
is a figure off the record with a label and a jump to the tab that explains it;
the two contested tiles carry the alarm tone, because they are the ones a reader
should not scroll past.
"""

from report.approval_needed import needing_approval
from report.council_beside import council_figure
from report.council_queries import was_assessed
from report.disagreement import sources_disagree
from report.html_layout import tag, text
from report.record import Report

LEGEND = (
    "Two claims appear on this page and are never merged. A published CVSS base score runs "
    "0.0 to 10.0 and belongs to the source that published it; the Organisation Risk Score "
    "runs 0 to 100 and is this system's own. A finding that is CVSS Critical and "
    "organisation Low is the normal case, not an error."
)
CVSS_NOTE = "Published CVSS base score, one per source that published a vector."
ORG_NOTE = "The Organisation Risk Score, this system's own assessment of this environment."


def stat_tiles(report: Report) -> str:
    """Give the row of summary tiles a reader lands on, each a jump to the tab behind it."""
    return tag("div", "".join(tile for tile in tiles(report)), "stats")


def tiles(report: Report) -> list[str]:
    """Give each tile in order, so the grid renders them without a loop in the markup."""
    return [
        findings_tile(report),
        disagree_tile(report),
        approval_tile(report),
        council_tile(report),
        inventory_tile(report),
        secrets_tile(report),
    ]


def findings_tile(report: Report) -> str:
    """Give the tile counting the findings and the components they were found across."""
    sub = f"across {report.component_count} components"
    return stat(len(report.findings), "Findings", sub, "", "")


def disagree_tile(report: Report) -> str:
    """Give the alarm tile counting the findings whose sources disagree."""
    count = len([one for one in report.findings if sources_disagree(one)])
    return stat(count, "Sources disagree", "read these first", "disagree", "tone-alarm")


def approval_tile(report: Report) -> str:
    """Give the alarm tile counting the findings that need approval."""
    sub = "High/Critical org risk, or sources that disagree"
    return stat(len(needing_approval(report)), "Need approval", sub, "", "tone-alarm")


def council_tile(report: Report) -> str:
    """Give the tile saying how many assessed findings the council settled a vector for."""
    # "no council ran" only when nothing was recorded; a run that assessed nothing
    # but passed findings over says so instead, so the tile and the panel agree.
    if not report.council:
        return stat_text("0", "Council settled a vector", "no council ran", "council", "")
    assessed = [one for one in report.council.values() if was_assessed(one)]
    settled = [one for one in assessed if council_figure(report, one.advisory_id)]
    shown = f"{len(settled)}/{len(assessed)}"
    sub = council_sub(report, assessed, settled)
    return stat_text(shown, "Council settled a vector", sub, "council", "")


def council_sub(report: Report, assessed: list, settled: list) -> str:
    """Say what is left: the findings passed over, or the assessed metrics still open."""
    not_asked = len(report.council) - len(assessed)
    if not_asked:
        return f"{not_asked} not asked"
    return f"{len(assessed) - len(settled)} left open"


def inventory_tile(report: Report) -> str:
    """Give the tile counting the catalogued components no advisory matched."""
    count = len(report.components_without_findings)
    return stat(count, "Components, no advisory", "matched nothing", "inventory", "")


def secrets_tile(report: Report) -> str:
    """Give the tile counting the secrets Trivy's rules matched."""
    sub = "matched a rule" if report.secrets else "none matched"
    return stat(len(report.secrets), "Secrets", sub, "secrets", "")


def stat(number: int, label: str, sub: str, target: str, tone: str) -> str:
    """Give one tile from a numeric count, with its label, sub-line, jump and tone."""
    return stat_text(str(number), label, sub, target, tone)


def stat_text(shown: str, label: str, sub: str, target: str, tone: str) -> str:
    """Give one tile whose figure is already text, an anchor where it jumps to a tab."""
    inner = (
        tag("span", text(shown), "stat-num")
        + tag("span", text(label), "stat-label")
        + tag("span", text(sub), "stat-sub")
    )
    css = f"stat {tone}".strip()
    if not target:
        return tag("div", inner, css)
    return f'<a class="{css}" href="#{text(target)}">{inner}</a>'


def two_scales() -> str:
    """Give the callout naming the two scales apart, in the two shapes they never share."""
    cvss = scale_note(scale_key("cvss", "0.0 to 10.0", "cvss-key"), CVSS_NOTE)
    org = scale_note(scale_key("org", "0 to 100", "org-key"), ORG_NOTE)
    head = tag("h3", text("Two scores, never merged"))
    scales = tag("div", cvss + org, "scales")
    return tag("div", head + scales + tag("p", text(LEGEND), "fine"), "callout")


def scale_key(label: str, bound: str, css: str) -> str:
    """Give one scale's legend chip, in the CVSS square or the organisation pill shape.

    The range is a `bound`, not a `value`: it is the scale's extent, not a figure
    off the record, so the page's figure guard does not read it as one.
    """
    inner = tag("span", text(label), "scale") + tag("span", text(bound), "bound")
    return tag("span", inner, f"skey {css}")


def scale_note(chip: str, said: str) -> str:
    """Give one of the two scales: its shape chip, and what the scale is."""
    return tag("div", chip + tag("p", text(said), "small"), "scale-note")

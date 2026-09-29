"""The record as one HTML file: self-contained, offline, tabbed, and readable without scripts.

**Nothing is fetched at any point.** A scan runs behind a corporate proxy and the
page is opened from a file, so the one stylesheet and the one script are inlined:
no `src`, no `link`, no font, no image, no network API. The only address on the
page is each advisory's own, as a link a reader follows or does not.

**Readable with scripts off.** Every panel is a plain section that shows by
default; the `js` class the script adds is the only thing that turns the bar into
tabs and hides the inactive panels. With the script, printing opens every
`details`; with no script each still opens on its own.

**Nothing here computes a number.** Every figure is the one the engine put in the
record, rendered beside the vector or the answer it came from. The output is
deterministic: no clock, no random id, stable ordering, so one record gives
byte-identical HTML.
"""

from report.council_words import models_named
from report.html_absences import inventory_panel
from report.html_assets import script, stylesheet
from report.html_council import council_panel
from report.html_findings import agreements_panel, disagreements_panel
from report.html_layout import separated, tag, text
from report.html_overview import overview_panel
from report.html_risk import risk_panel
from report.html_secrets import secrets_panel
from report.html_tabs import Panel, panels_main, tabbar
from report.disagreement import sources_agree, sources_disagree
from organisation.approval import Approval
from report.provenance import SCORING_RULES_LABEL, AdvisoryDatabase
from report.record import Report

DOCTYPE = "<!DOCTYPE html>"
LANGUAGE = "en"
CHARSET = '<meta charset="utf-8">'
VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'
NO_DATABASE = "NO ADVISORY DATABASE DATE"


def as_html(report: Report) -> str:
    """Render the whole record as one tabbed page, self-contained and readable without scripts."""
    panels = build_panels(report)
    body = masthead(report) + tabbar(panels) + panels_main(panels) + tag("script", script())
    return document(title_of(report), body)


def build_panels(report: Report) -> tuple[Panel, ...]:
    """Build every tab and its panel, in the order the bar shows them."""
    disagreeing = len([one for one in report.findings if sources_disagree(one)])
    # The Agreements tab counts only the findings whose sources were all read and
    # agreed; a refused or unscored finding is neither, and is counted in its own
    # group heading inside the panel.
    agreeing = len([one for one in report.findings if sources_agree(one)])
    return (
        Panel("overview", "Overview", overview_panel(report)),
        Panel("disagree", "Disagreements", disagreements_panel(report), disagreeing, alarm=True),
        Panel("agree", "Agreements", agreements_panel(report), agreeing),
        Panel("risk", "Org risk", risk_panel(report), len(report.risk)),
        Panel("council", "Council", council_panel(report), len(report.council)),
        Panel("secrets", "Secrets", secrets_panel(report), len(report.secrets)),
        Panel("inventory", "Inventory", inventory_panel(report), report.component_count),
    )


def document(title: str, body: str) -> str:
    """Put the page together: one style, one script, no stylesheet link, nothing fetched."""
    page = [DOCTYPE, f'<html lang="{LANGUAGE}">', head(title), tag("body", body), "</html>"]
    return "\n".join([*page, ""])


def head(title: str) -> str:
    """Give the head: the character set, the viewport, the title, and the only stylesheet."""
    return tag("head", CHARSET + VIEWPORT + tag("title", title) + tag("style", stylesheet()))


def title_of(report: Report) -> str:
    """Name the page after the repository it is about."""
    return text(f"Audit of {report.provenance.repository}")


def masthead(report: Report) -> str:
    """Name the repository, what scanned it, the weights the server held, and who approved it."""
    run = report.provenance
    identity = tag("p", text("Vulnerability audit"), "eyebrow") + tag("h1", title_of(report))
    left = identity + tools_line(run) + database_line(run) + models_line(run)
    row = tag("div", left) + approval_indicator(report)
    return tag("header", tag("div", row, "wrap mast-row"), "masthead")


def tools_line(run) -> str:
    """Give the line of tool versions, ending with the scoring rules this run scored by."""
    parts = [
        text(f"syft {run.syft_version}"),
        text(f"trivy {run.trivy_version}"),
        text(f"{SCORING_RULES_LABEL} {run.scoring_rules_version}"),
    ]
    return tag("p", separated(parts), "meta")


def database_line(run) -> str:
    """Say when the advisory database was built, or shout that nothing said."""
    # A scan against no database finds nothing and exits 0, the one failure a
    # clean report cannot be told from, so it is not quiet.
    if isinstance(run.database, AdvisoryDatabase):
        return tag("p", text(f"advisory DB {run.database.built_at}"), "meta")
    return tag("p", text(f"{NO_DATABASE}: {run.database.reason}"), "alarm")


def models_line(run) -> str:
    """Name the weights the server held under each tag when the run began, and its version."""
    return "".join(tag("p", text(one), "meta") for one in models_named(run.local_models))


def approval_indicator(report: Report) -> str:
    """Give the masthead's glance at the human act: a green pill approved, else a muted note."""
    decided = report.approval
    if isinstance(decided, Approval):
        who = f"{decided.decision.value} by " + tag("b", text(decided.approver))
        said = tag("span", who + "<br>" + tag("span", text(decided.recorded_at), "when"))
        return tag("div", tag("span", "", "dot ok") + said, "approval ok")
    reason = tag("span", text(decided.reason), "when")
    said = tag("span", text("No approval recorded") + "<br>" + reason)
    return tag("div", tag("span", "", "dot") + said, "approval")

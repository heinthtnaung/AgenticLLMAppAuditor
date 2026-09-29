"""The inventory tab, and the two overview cards about a human act and what was not done.

**Three kinds of nothing, counted apart.** A component nothing was published
against looks clean and may be; an advisory that matched no component is a CVE
that fell out of the join, which is a report that looks clean and is not; and an
artifact Syft could not identify was never joinable at all. One number covering
all three would hide the middle one, which is the only one that is a defect.

**An absence is laid out, never dropped.** The overview states plainly whether an
organisation approved, and what this run did not assess, so no reader takes
silence for a nil result.
"""

from organisation.approval import Approval
from report.absences import NOTHING_ABSENT
from report.html_filters import empty_line, search_box, toolbar
from report.html_layout import empty_note, group, listing, panel_head, separated, tag, text
from report.record import Report

PURL_LIST = "purl-list"
INVENTORY_LEDE = "The component inventory Syft catalogued, and what in it matched nothing."
NOTHING_LEDE = (
    "Counted apart on purpose. An advisory matching no component is a CVE that fell out of "
    "the join; a component carrying no advisory is only a component nobody published against."
)
UNIDENTIFIED_LEDE = (
    "Catalogued, and joinable to no advisory by nature. Counted rather than dropped, because "
    "dropping one silently loses a CVE."
)
APPROVAL_LEDE = "The one fact on this page about a human act."
NOT_ASSESSED_LEDE = "What this run did not do, so no reader takes silence for a nil result."
NO_UNMATCHED = "Every component Syft catalogued carries at least one advisory."


def inventory_panel(report: Report) -> str:
    """Give the Inventory tab: what matched nothing, the clean components, and the unidentified."""
    head = panel_head("Inventory", INVENTORY_LEDE)
    return head + matched_nothing(report) + clean_components(report) + unidentified_group(report)


def matched_nothing(report: Report) -> str:
    """Count what matched nothing, keeping the kinds apart and naming what is behind each."""
    counted = [
        count_entry(f"{len(report.advisories_without_components)} advisories matched no component",
                    report.advisories_without_components),
        *overrides_entry(report),
    ]
    return group("Matched nothing", NOTHING_LEDE, listing(counted, "count-list"))


def count_entry(said: str, named: tuple[str, ...]) -> str:
    """Give one count, with what it counted behind the count itself when there is anything."""
    if not named:
        return text(said)
    items = [tag("code", text(one)) for one in named]
    return tag("details", tag("summary", text(said)) + listing(items, "artifacts"))


def overrides_entry(report: Report) -> list[str]:
    """Name the answer overrides that matched no finding, so a typo cannot be silent."""
    missed = report.overrides_without_findings
    if not missed:
        return []
    plural = "" if len(missed) == 1 else "s"
    said = f"{len(missed)} answer override{plural} matched no finding: {', '.join(missed)}"
    return [text(said)]


def clean_components(report: Report) -> str:
    """List the components no advisory matched, searchable, since it is the longest list here."""
    purls = report.components_without_findings
    title = f"Components with no advisory ({len(purls)})"
    if not purls:
        return group(title, "", empty_note(NO_UNMATCHED))
    bar = toolbar(PURL_LIST, search_box("Search components"))
    items = listing([tag("code", text(one)) for one in purls], "purls")
    host = f'<div id="{PURL_LIST}" class="card">{items}{empty_line("No component matches.")}</div>'
    return group(title, "", bar + host)


def unidentified_group(report: Report) -> str:
    """Name what was catalogued and could never be joined, rather than dropping it."""
    catalogued = report.unidentified_artifacts
    if not catalogued:
        return ""
    entries = [artifact_entry(one) for one in catalogued]
    title = f"Could not be identified ({len(catalogued)})"
    return group(title, UNIDENTIFIED_LEDE, listing(entries, "artifacts"))


def artifact_entry(artifact) -> str:
    """Name one artifact and the ecosystem it was catalogued under."""
    return separated([tag("code", text(artifact.name)), text(artifact.ecosystem)])


def approval_card(report: Report) -> str:
    """Give the overview card saying who approved this audit, or that nobody has."""
    decided = report.approval
    if isinstance(decided, Approval):
        line = f"{decided.decision.value} by {decided.approver} at {decided.recorded_at}"
        note = tag("p", text(decided.note), "muted small") if decided.note else ""
        return status_card("Approval", line, note + fine(APPROVAL_LEDE), True)
    return status_card("Approval", "no approval recorded", fine(decided.reason), False)


def not_assessed_card(report: Report) -> str:
    """Give the overview card naming what this run did not assess, so silence reads as nothing."""
    entries = [absence_entry(one) for one in report.not_assessed]
    body = listing(entries, "absences") if entries else empty_note(NOTHING_ABSENT)
    return status_card("Not assessed", "", body + fine(NOT_ASSESSED_LEDE), False)


def absence_entry(absence) -> str:
    """Give one thing this report does not carry, and why it does not."""
    what = tag("span", text(absence.what), "absence-what")
    return what + " " + tag("span", text(absence.because), "absence-why")


def status_card(eyebrow: str, line: str, rest: str, ok: bool) -> str:
    """Give one overview status card: its heading, a status line, and the rest below it."""
    headed = tag("p", text(eyebrow), "eyebrow")
    status = tag("p", text(line), "status-line") if line else ""
    css = "card status-card ok" if ok else "card status-card"
    return tag("div", headed + status + rest, css)


def fine(said: str) -> str:
    """Give one muted line of context under a card."""
    return tag("p", text(said), "fine")

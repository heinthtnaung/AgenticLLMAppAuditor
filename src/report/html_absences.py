"""What matched nothing, what nobody settled, and what this run did not assess.

**Three kinds of nothing, counted apart.** A component nothing was published
against looks clean and may be; an advisory that matched no component is a CVE
that fell out of the join, which is a report that looks clean and is not; and an
artifact Syft could not identify was never joinable at all. One number covering
all three would hide the middle one, which is the only one that is a defect.

**An absence is laid out, never dropped.** The tool states plainly that no
organisation answers were supplied, that nobody approved, that no council ran.
An honest report about a partly-built tool is worth more than a complete-looking
one, so `Not assessed` is the last thing on the page and never the first thing
cut for space.
"""

from organisation.approval import Approval
from report.html_layout import listing, section, separated, tag, text
from report.record import NOTHING_ABSENT, Report

NOTHING_LEDE = (
    "Counted apart on purpose. An advisory matching no component is a CVE that fell out of "
    "the join; a component carrying no advisory is only a component nobody published against."
)
UNIDENTIFIED_LEDE = (
    "Catalogued, and joinable to no advisory by nature. Counted rather than dropped, because "
    "dropping one silently loses a CVE."
)
APPROVAL_LEDE = "The one fact on this page about a human act."
NOT_ASSESSED_LEDE = (
    "What this run did not do, so no reader takes silence for a nil result."
)


def matched_nothing_section(report: Report) -> str:
    """Count what matched nothing, keeping the kinds apart and naming what is behind each."""
    counted = [
        count_entry(f"{len(report.components_without_findings)} components carry no advisory",
                    report.components_without_findings),
        count_entry(f"{len(report.advisories_without_components)} advisories matched no component",
                    report.advisories_without_components),
        *overrides_entry(report),
    ]
    return section("Matched nothing", NOTHING_LEDE, listing(counted, "counts"))


def count_entry(said: str, named: tuple[str, ...]) -> str:
    """Give one count, with what it counted behind the count itself when there is anything."""
    # The count is the summary rather than a "show" beside it: fifty-five purls
    # is not a list anybody reads, and a count nothing opens is a count nobody
    # can check.
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


def unidentified_section(report: Report) -> str:
    """Name what was catalogued and could never be joined, rather than dropping it."""
    catalogued = report.unidentified_artifacts
    if not catalogued:
        return ""
    entries = [artifact_entry(one) for one in catalogued]
    title = f"Could not be identified ({len(catalogued)})"
    return section(title, UNIDENTIFIED_LEDE, listing(entries, "artifacts"))


def artifact_entry(artifact) -> str:
    """Name one artifact and the ecosystem it was catalogued under."""
    return separated([tag("code", text(artifact.name)), text(artifact.ecosystem)])


def approval_section(report: Report) -> str:
    """Say who approved this audit, or leave it to the absence below to say nobody did."""
    decided = report.approval
    if not isinstance(decided, Approval):
        return ""
    said = f"{decided.decision.value} by {decided.approver} at {decided.recorded_at}"
    entry = separated([text(said), text(decided.note)])
    return section("Approval", APPROVAL_LEDE, tag("p", entry, "note"))


def not_assessed_section(report: Report) -> str:
    """Name what this run did not assess, so no reader reads silence as a nil result."""
    entries = [absence_entry(one) for one in report.not_assessed]
    body = listing(entries, "absences") if entries else tag("p", text(NOTHING_ABSENT), "note")
    return section("Not assessed", NOT_ASSESSED_LEDE, body)


def absence_entry(absence) -> str:
    """Give one thing this report does not carry, and why it does not."""
    return (
        tag("span", text(absence.what), "absence-what")
        + " "
        + tag("span", text(absence.because), "absence-why")
    )

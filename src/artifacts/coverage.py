"""Builds `findings.json`'s coverage block: what an audit looked at, and what it did not.

Split out of `findings_document.py`, which was at the ~200-line cap before this
grew again. One responsibility: assemble the coverage claim and refuse one whose
parts contradict each other. `findings_document` re-exports `coverage`, so no
call site moved.
"""

from artifacts.finding import OWASP_IDS

# `not_ingested` means no generator or no cached database, and coverage says so.
ADVISORY_NOT_INGESTED = "not_ingested"
ADVISORY_SNAPSHOT = "snapshot"

def _check_risk_classes(risk_classes_checked: list[str] | None) -> None:
    """Reject a risk class outside the vocabulary a reader can look up.

    An unknown id both claims a class that does not exist and makes the real
    one render as uncovered, which is the wrong direction to be wrong in.
    """
    unknown = sorted(set(risk_classes_checked or []) - set(OWASP_IDS))
    if unknown:
        raise ValueError(f"unknown risk classes {unknown}; expected ids from {OWASP_IDS}")


def _check_unresolved(count: int | None, surfaces_considered: int) -> None:
    """Reject an unresolved count that contradicts the surfaces it is counted from."""
    if count is None:
        return
    if count < 0:
        raise ValueError(f"unresolved_component_count must not be negative, got {count}")
    if count > surfaces_considered:
        raise ValueError(
            f"unresolved_component_count {count} exceeds the {surfaces_considered} "
            "surfaces considered; the mapping holds one entry per surface")


def _check_advisory_pin(advisory_data: str, provenance: tuple) -> None:
    """A snapshot must be pinned and an absence must claim nothing, both directions.

    Without this pairing, "we scanned with Trivy" could appear with a null date
    behind it -- a claim with no version, which is the one failure the pin
    exists to prevent.
    """
    named = [value for value in provenance if value is not None]
    if advisory_data == ADVISORY_SNAPSHOT and len(named) != len(provenance):
        raise ValueError("a snapshot needs its generator name, version and DB date")
    if advisory_data == ADVISORY_NOT_INGESTED and named:
        raise ValueError(f"no advisory data was read, so nothing may pin it: {named}")


def _check_unreached_list(count: int | None, items: list | None) -> None:
    """The list and its count are the same fact, so they are null or sized together."""
    if (count is None) != (items is None):
        raise ValueError("advisory_unreached_components and its count are null together")
    if items is not None and len(items) != count:
        raise ValueError(
            f"advisory_unreached_components has {len(items)} items, count says {count}")


def coverage(surfaces_considered: int, checks_run: list[str],
             advisory_data: str = ADVISORY_NOT_INGESTED,
             risk_classes_checked: list[str] | None = None,
             unresolved_component_count: int | None = None,
             advisory_generator_name: str | None = None,
             advisory_generator_version: str | None = None,
             advisory_db_updated_at: str | None = None,
             advisory_unreached_component_count: int | None = None,
             advisory_unreached_components: list | None = None) -> dict:
    """Say what the search covered, so a short findings list is not read as a clean bill."""
    if surfaces_considered < 0:
        raise ValueError(f"surfaces_considered must not be negative, got {surfaces_considered}")
    if advisory_data not in (ADVISORY_NOT_INGESTED, ADVISORY_SNAPSHOT):
        raise ValueError(f"unknown advisory state {advisory_data!r}")
    _check_risk_classes(risk_classes_checked)
    _check_unresolved(unresolved_component_count, surfaces_considered)
    _check_advisory_pin(advisory_data, (advisory_generator_name,
                                        advisory_generator_version,
                                        advisory_db_updated_at))
    if advisory_data == ADVISORY_NOT_INGESTED and advisory_unreached_component_count is not None:
        raise ValueError("an unreached count needs advisory data behind it")
    _check_unreached_list(advisory_unreached_component_count, advisory_unreached_components)
    return {
        "surfaces_considered": surfaces_considered,
        "checks_run": sorted(checks_run),
        "risk_classes_checked": sorted(risk_classes_checked or []),
        "unresolved_component_count": unresolved_component_count,
        "advisory_data": advisory_data,
        "advisory_generator_name": advisory_generator_name,
        "advisory_generator_version": advisory_generator_version,
        "advisory_db_updated_at": advisory_db_updated_at,
        "advisory_unreached_component_count": advisory_unreached_component_count,
        "advisory_unreached_components": advisory_unreached_components,
    }


# What a narrowed check must say about itself. Counts and their denominator,
# never a rate: the division is the reader's, the way `evaluation.json` holds it.
NARROWED_FIELDS = ("check", "examined_surface_count", "eligible_surface_count")


def _check_one_narrowing(entry: dict, checks_run: list[str], considered: int) -> None:
    """Refuse a narrowing record that cannot be true."""
    if sorted(entry) != sorted(NARROWED_FIELDS):
        raise ValueError(f"a narrowing must hold exactly {NARROWED_FIELDS}, got {sorted(entry)}")
    examined, eligible = entry["examined_surface_count"], entry["eligible_surface_count"]
    if not 0 <= examined <= eligible <= considered:
        raise ValueError(
            f"{entry['check']} examined {examined} of {eligible} surfaces against "
            f"{considered} considered, which is not a fraction of what was there")
    if examined == eligible:
        # Refused so that an empty list is a reliable test for "nothing was
        # narrowed" -- every reader will branch on exactly that.
        raise ValueError(f"{entry['check']} examined every eligible surface; that is not a narrowing")
    if entry["check"] not in checks_run:
        raise ValueError(f"{entry['check']} was narrowed but is not in checks_run, which is a contradiction")


def check_narrowings(narrowed: list[dict], checks_run: list[str], considered: int) -> list[dict]:
    """Validate every narrowing record and return them sorted by check.

    A narrowed check examined fewer surfaces than it could have, because the
    planner's model chose so. `checks_run` still names it -- it did look -- and
    this is how a reader tells "looked at all of it" from "looked at some".
    """
    seen = [entry["check"] for entry in narrowed]
    if len(set(seen)) != len(seen):
        raise ValueError("two narrowing records name the same check")
    for entry in narrowed:
        _check_one_narrowing(entry, checks_run, considered)
    return sorted(narrowed, key=lambda entry: entry["check"])

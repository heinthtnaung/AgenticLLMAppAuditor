"""Records which check order the audit ran in, and what chose it.

**A file of its own, deliberately.** The order is a fact about one execution,
not evidence about the audited app, and `merge_monotonically` guarantees it is a
permutation of the eligible checks -- so it provably changes nothing else in
`findings.json`: `coverage.checks_run` is sorted, findings and probes are
sorted, and `MAX_STEPS` cannot bind on six checks. Putting a model-chosen value
inside `findings.json` would spend `README.md`'s byte-identical claim, force a
`SCHEMA_VERSION` bump that makes every artifact on disk unreadable to
`report.py` and `vex.py`, and require `run_baseline.py` -- which has no planner
at all -- to invent one. It would be worse inside `coverage`, which
`artifacts/sarif.py` copies wholesale into `findings.sarif.json`.

So nothing reads this file: not the scorer, not the report, not SARIF or VEX.
It exists so a reader can ask "who decided the order?" and get an answer.
"""

from artifacts.findings_document import (
    MODEL_STATUSES, MODEL_USED, findings_to_json)

# Version 2 added `surface_selection` and `refused_narrowing`: which surfaces
# the planner asked each check to examine, and which narrowings were refused.
SCHEMA_VERSION = 2

# Every field a reader can rely on, in the order `build_planner_document`
# assembles them. The file itself is key-sorted, like every other artifact.
DOCUMENT_FIELDS = (
    "schema_version", "status", "identifier", "order", "surface_selection",
    "refused_narrowing", "findings_schema_version")


def _check_identifier(status: str, identifier: str | None) -> None:
    """Refuse a record that names a model without using one, or uses one unnamed.

    Both directions, the way `model_provenance` validates its own pairing: an
    unnamed `used` cannot be reproduced, and a named `disabled` is a claim about
    a model that never ran.
    """
    if status == MODEL_USED and not identifier:
        raise ValueError("a planner that used a model must name it")
    if status != MODEL_USED and identifier is not None:
        raise ValueError(f"status {status!r} must not name a model, got {identifier!r}")


def build_planner_document(planner_run: dict, findings_schema_version: int) -> dict:
    """Assemble the planner artifact from the record `checks/planner.py` returned."""
    status = planner_run["status"]
    if status not in MODEL_STATUSES:
        raise ValueError(f"unknown planner status {status!r}; expected {MODEL_STATUSES}")
    identifier = planner_run["identifier"]
    _check_identifier(status, identifier)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "identifier": identifier,
        # Never sorted: the order is the fact this file exists to record.
        "order": list(planner_run["order"]),
        # Sorted, unlike `order` above -- here membership is the fact and the
        # sequence carries no meaning. Two adjacent lists with opposite rules,
        # said out loud so neither is "tidied" into the other.
        "surface_selection": {check: sorted(ids) for check, ids
                              in sorted(planner_run.get("surface_selection", {}).items())},
        # The only evidence the narrowing guard ever fired: without it a model
        # that asked to narrow everything and was refused is byte-identical to
        # one that asked for nothing.
        "refused_narrowing": sorted(
            planner_run.get("refused_narrowing", []),
            key=lambda entry: (entry["check"], entry["reason"])),
        # What invalidates this file, in place of a timestamp -- the same device
        # `remediation.json` uses to say which findings it describes.
        "findings_schema_version": findings_schema_version,
    }


def planner_to_json(document: dict) -> str:
    """Serialise the planner document to the same stable on-disk form as the others.

    Delegated rather than re-implemented: every artifact this project writes is
    sorted and indented identically, and two serialisers is how two of them
    start disagreeing.
    """
    return findings_to_json(document)

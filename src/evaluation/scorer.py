"""Scores what the auditor found against a hand-written grading key.

Counts only, never rates. Precision, recall and F1 are absent as fields on
purpose: a reader cannot copy a percentage out of this file, so they have to
divide, and to divide they must hold the denominator. No *score* is printed as
a rate either -- the counts travel with the `qualifications` that bound them,
and the division is the reader's. (`main.py` does print a mapping-coverage
percentage, which is a scan statistic and not a score against a key; the
distinction is the point, not an exception to it.)

Every classification here is derived from the artifacts. There is no list of
known misses and no per-app tolerance, because either would turn the scorer
into a place to tune the tool against its own answer key.
"""

from artifacts.finding import SURFACE_SUBJECT, UNRESOLVED_OUTCOMES
from artifacts.findings_document import ADVISORY_NOT_INGESTED, MODEL_USED
from evaluation.grading import matches_key

# Why a key entry went unanswered. Derived, never assigned by hand.
NO_CHECK_FOR_RISK_CLASS = "no_check_for_risk_class"
CHECKED_AND_SILENT = "checked_and_silent"
PROBE_UNRESOLVED = "probe_unresolved"
SURFACE_NOT_EXTRACTED = "surface_not_extracted"
FILE_SKIPPED = "file_skipped"

# What bounds a number, so it never travels without them.
QUALIFICATIONS = (
    "advisory_data_not_ingested",
    "expected_surfaces_not_complete",
    "findings_not_complete",
    "key_ai_drafted",
    "key_unverified",
    "model_disabled",
    "no_key_findings",
    "scan_partial",
    "small_sample",
    "unresolved_components",
)

# Below this many graded findings, any rate is an anecdote.
SMALL_SAMPLE_BELOW = 10


def _miss_reason(entry: dict, findings_document: dict, surfaces: dict) -> tuple[str, str | None]:
    """Say why one key entry went unanswered, from the artifacts alone.

    `probe_reason` is reported whenever a probe gave up on that surface, even
    when the primary reason is something else: "no check covers this class, and
    the trace could not reach it either" is two facts, and dropping one hides
    work that was attempted.
    """
    probe = surfaces["probes"].get((entry["file"], entry["line"]))
    if entry["file"] in surfaces["skipped"]:
        return FILE_SKIPPED, probe
    if entry["owasp_id"] not in findings_document["coverage"]["risk_classes_checked"]:
        return NO_CHECK_FOR_RISK_CLASS, probe
    if entry["file"] not in surfaces["files"]:
        return SURFACE_NOT_EXTRACTED, probe
    if probe is not None:
        return PROBE_UNRESOLVED, probe
    return CHECKED_AND_SILENT, None


def _qualifications(key: dict, findings_document: dict, skipped: list[str]) -> list[str]:
    """Collect everything that bounds this app's numbers."""
    said = []
    if not key["verified"]:
        said.append("key_unverified")
    if key["source"] == "ai_drafted":
        said.append("key_ai_drafted")
    if not key["findings_complete"]:
        said.append("findings_not_complete")
    if not key["expected_surfaces_complete"]:
        said.append("expected_surfaces_not_complete")
    if not key["findings"]:
        said.append("no_key_findings")
    if skipped:
        said.append("scan_partial")
    if findings_document["coverage"]["advisory_data"] == ADVISORY_NOT_INGESTED:
        said.append("advisory_data_not_ingested")
    # Surfaces with no component are surfaces the supply-chain check could not
    # examine, so they bound a supply-chain number the same way the two above do.
    if findings_document["coverage"]["unresolved_component_count"]:
        said.append("unresolved_components")
    if findings_document["model_run"]["status"] != MODEL_USED:
        said.append("model_disabled")
    if len(key["findings"]) < SMALL_SAMPLE_BELOW:
        said.append("small_sample")
    return sorted(said)


def _miss_record(entry: dict, findings_document: dict, surfaces: dict) -> dict:
    """Record one unanswered key entry beside the reason it went unanswered."""
    reason, probe_reason = _miss_reason(entry, findings_document, surfaces)
    return {"key_id": entry["id"], "owasp_id": entry["owasp_id"],
            "reason": reason, "probe_reason": probe_reason}


def _key_provenance(key: dict) -> dict:
    """Copy the key's provenance, so a score is never quoted without who stands behind it."""
    return {
        "upstream_commit": key["upstream_commit"],
        "key_source": key["source"],
        "key_verified": key["verified"],
        "key_verified_by": key["verified_by"],
        "key_verified_date": key["verified_date"],
        "ground_truth_schema_version": key["schema_version"],
    }


def _surface_anchor(subject_id: str) -> tuple[str, int]:
    """Split a surface id into the file and line a key entry is compared against."""
    file, line = subject_id.split(":")[:2]
    return file, int(line)


def _surface_context(surfaces_document: dict, findings_document: dict) -> dict:
    """Index what the scan saw, so a miss can be attributed rather than guessed."""
    return {
        "files": {s["file"] for s in surfaces_document["surfaces"]},
        "skipped": {s["file"] for s in surfaces_document["skipped_files"]},
        # Keyed by subject_kind, not by the shape of the id: a component purl
        # holds colons too, so guessing from them either crashes here or drops
        # a probe silently -- and a dropped probe downgrades "a probe gave up"
        # to "a check was silent", the opposite conclusion.
        #
        # The outcome test is what makes a None in this map unambiguous: a
        # concluded probe carries no reason anyway (Probe forbids it), so
        # without it a missing key and a concluded probe would look alike.
        "probes": {
            _surface_anchor(p["subject_id"]): p["reason"]
            for p in findings_document["probes"]
            if p["subject_kind"] == SURFACE_SUBJECT and p["outcome"] in UNRESOLVED_OUTCOMES
        },
    }


def score_app(app: str, key: dict, findings_document: dict, surfaces_document: dict) -> dict:
    """Score one app, gating each rate on what its key actually claims."""
    produced = findings_document["findings"]
    context = _surface_context(surfaces_document, findings_document)
    skipped = sorted(context["skipped"] & {e["file"] for e in key["findings"]})

    matched = [e for e in key["findings"] if any(matches_key(f, e) for f in produced)]
    answered = {f["finding_id"] for f in produced
                if any(matches_key(f, e) for e in key["findings"])}
    misses = [_miss_record(e, findings_document, context)
              for e in key["findings"] if e not in matched]
    return {
        "app": app,
        **_key_provenance(key),
        "findings_schema_version": findings_document["schema_version"],
        "key_finding_count": len(key["findings"]),
        "produced_finding_count": len(produced),
        "findings_complete": key["findings_complete"],
        "expected_surfaces_complete": key["expected_surfaces_complete"],
        "graded_files_skipped": skipped,
        "true_positives": len(matched),
        "false_negatives": len(key["findings"]) - len(matched),
        # Undefined when the key does not claim to list every finding: an
        # unmatched finding may be real and simply absent from the key.
        "false_positives": (len(produced) - len(answered)
                            if key["findings_complete"] else None),
        "matched_key_ids": sorted(e["id"] for e in matched),
        "unmatched_finding_ids": sorted(f["finding_id"] for f in produced
                                        if f["finding_id"] not in answered),
        "misses": sorted(misses, key=lambda m: m["key_id"]),
        "recall_reportable": bool(key["findings"]) and not skipped,
        "precision_reportable": key["findings_complete"],
        "qualifications": _qualifications(key, findings_document, skipped),
    }

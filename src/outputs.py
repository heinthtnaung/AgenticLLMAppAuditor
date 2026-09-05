"""Puts one audit's results on disk: the JSON artifacts, then the two reports.

Split out of `main.py`, which is the command line and was at its size limit.
This module owns one job -- writing what a run produced -- and it is also where
the only model call in an audit happens, so a reader looking for "does this tool
ever call a model" finds the answer in one place.

Both reports are rendered from the files just written rather than from what is
still in memory. A report is a reading of the artifacts, and reading them back
is what keeps it one.
"""

import sys
from collections import Counter
from pathlib import Path

from artifacts.findings_document import MODEL_UNAVAILABLE, MODEL_USED, model_provenance
from artifacts.remediation import (
    MODEL_UNAVAILABLE as ADVICE_UNAVAILABLE_REASON,
    UNAVAILABLE,
    advice_entry,
    build_remediation_document,
    remediation_to_json,
)
from artifacts.sarif import sarif_to_json, to_sarif
from artifacts.skipped_file import SkippedFile
from artifacts.surface import Surface
from checks import advise
from parsing.languages import PYTHON
from retrieval import retrieve
import config
import model_client
from reporting import remediation_report
from reporting import report

# Every per-app artifact name, in one place, because three modules join paths
# from them and two copies is how the two copies start disagreeing.
SURFACES_NAME = "surfaces.json"
AIBOM_NAME = "aibom.json"
SBOM_NAME = "sbom.json"
CYCLONEDX_NAME = "sbom.cyclonedx.json"
MAPPING_NAME = "mapping.json"
FINDINGS_NAME = "findings.json"

# Which order the checks ran in and what chose it. Read by nothing --
# see `docs/SCHEMAS.md`; it exists so a reader can ask who decided.
PLANNER_NAME = "planner.json"
SARIF_NAME = "findings.sarif.json"
REMEDIATION_NAME = "remediation.json"
REPORT_NAME = "report.md"
REMEDIATION_REPORT_NAME = "remediation.md"


def report_skipped_files(skipped: list[SkippedFile]) -> None:
    """Warn about each file the scan could not analyse."""
    for record in skipped:
        where = f" (line {record.line})" if record.line else ""
        print(f"warning: skipped {record.file}: {record.reason}{where}", file=sys.stderr)


def report_coverage(mapping_document: dict) -> None:
    """Say how much of the app the mapping reached.

    Printed rather than stored: a mapping covering a third of the surfaces
    looks the same on disk as one covering all of them.
    """
    total, mapped = mapping_document["surface_count"], mapping_document["mapped_count"]
    share = f"{mapped / total:.0%}" if total else "n/a"
    print(f"  mapped {mapped} of {total} surfaces ({share})", file=sys.stderr)
    for reason, count in sorted(mapping_document["reason_counts"].items()):
        if count:
            print(f"    {reason:22} {count}", file=sys.stderr)
    for name in mapping_document["undeclared_components"]:
        print(f"  used but never declared: {name}", file=sys.stderr)


def declared_language(surfaces: list[Surface]) -> str:
    """Say which language this app is mostly written in, for a snippet's fence."""
    counted = Counter(surface.language for surface in surfaces)
    return counted.most_common(1)[0][0] if counted else PYTHON


def _unreachable_advice(findings: list[dict]) -> tuple[list[dict], dict]:
    """Record one entry per finding when no model answered, and say so once."""
    entries = [advice_entry(finding["finding_id"], UNAVAILABLE, ADVICE_UNAVAILABLE_REASON)
               for finding in findings]
    return entries, model_provenance(MODEL_UNAVAILABLE)


def build_remediation(findings_document: dict, language: str,
                      module_names: tuple[str, ...]) -> str:
    """Ask the model to advise on every finding, and record what it said or did not.

    A model that cannot be reached degrades the artifact rather than failing the
    audit: producing less is a normal outcome here, exactly as a missing Syft
    yields no bill of materials. The knowledge base degrades separately and is
    probed once for the whole run -- an unreachable model and an unbuilt index
    are two different absences, and the artifact records each on its own block.
    """
    findings = findings_document["findings"]
    # Probed before the findings are looked at, so an app with nothing found
    # still records whether an index was there. `knowledge_base` describes the
    # run's inputs, not its output: "indexed, and no entries" is a fact worth
    # having, and it costs one embed call that `advise_all([])` would not make.
    grounding = retrieve.probe(config.get_path("AUDITOR_KNOWLEDGE_DIR"))
    try:
        digest = model_client.model_digest()
        entries = advise.advise_all(findings, language, module_names, grounding.passages_for)
        provenance = model_provenance(
            MODEL_USED, model_client.MODEL, model_client.DECODE_SETTINGS, digest)
    except RuntimeError:
        entries, provenance = _unreachable_advice(findings)
    document = build_remediation_document(
        entries, provenance, grounding.knowledge, findings_document["schema_version"])
    return remediation_to_json(document)


def standard_format(findings_document: dict) -> dict[str, str]:
    """Return the findings in the interchange formats other tooling reads.

    Derived from the document the run already built, never a second producer of
    the facts. Today that is SARIF; a second in-process format would join here
    rather than lengthen the command line.

    OpenVEX deliberately does **not**: `emit_vex.py` writes it as a command of
    its own, because `vexctl` authors that document and an audit must not gain
    an external binary -- nor the artifact count a reader has learned.
    """
    return {SARIF_NAME: sarif_to_json(to_sarif(findings_document))}


def write_all(out: Path, documents: dict[str, str], app: str) -> int:
    """Write every artifact, render both reports from them, and return the file count."""
    out.mkdir(parents=True, exist_ok=True)
    for name, text in sorted(documents.items()):
        (out / name).write_text(text, encoding="utf-8")

    (out / REPORT_NAME).write_text(
        report.render_from_files(app, out / FINDINGS_NAME, out / SURFACES_NAME),
        encoding="utf-8")
    (out / REMEDIATION_REPORT_NAME).write_text(
        remediation_report.render_from_files(app, out / REMEDIATION_NAME, out / FINDINGS_NAME),
        encoding="utf-8")
    return len(documents) + 2

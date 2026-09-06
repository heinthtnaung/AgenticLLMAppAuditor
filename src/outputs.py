"""Puts one audit's results on disk: the JSON artifacts, then the two reports.

**One job, since the split.** Four used to live here -- the artifact filenames,
two stderr progress helpers, the remediation document with the audit's only
model call, and this file writing. They are now `artifacts/names.py`,
`reporting/progress.py` and `remediation_run.py`. The old docstring claimed "one
job" and then said the module was also where the model call happened, which was
the tell.

Both reports are rendered from the files just written rather than from what is
still in memory. A report is a reading of the artifacts, and reading them back
is what keeps it one.
"""

from pathlib import Path

from artifacts.sarif import sarif_to_json, to_sarif
from reporting import remediation_report
from reporting import report

# The names live in `artifacts/names.py`: `deps/inputs.py` and three commands
# read them too, and a leaf package importing this module for a filename made
# the dependency point the wrong way. Re-exported here because the modules that
# write artifacts already import them from this one.
from artifacts.names import (                                    # noqa: E402
    AIBOM_NAME, CYCLONEDX_NAME, FINDINGS_NAME, MAPPING_NAME, PLANNER_NAME,
    REMEDIATION_NAME, REMEDIATION_REPORT_NAME, REPORT_NAME, SARIF_NAME,
    SBOM_NAME, SURFACES_NAME)


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

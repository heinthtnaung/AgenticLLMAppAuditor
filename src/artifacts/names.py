"""What each artifact a run produces is called. Constants only.

Here rather than in the module that writes them, because the writers are not the
only readers: `deps/inputs.py` joins three of these paths, `evaluation/harness.py`
and `run_baseline.py` open two each, and `emit_vex.py` opens one. Every one of
those kept its own copy of the string, under a comment in `outputs.py` claiming
the names lived "in one place, because two copies is how the two copies start
disagreeing" -- which was true of the comment and false of the code.

Constants and nothing else, so a leaf package can read a filename without
importing the orchestration that writes it.

**Everything a run can leave on disk, not only what the audit path writes.**
The VEX document and the two exported report formats are written by commands of
their own rather than by the audit, and they used to be named in those modules
instead -- which made this module's own first line false and left the web UI's
download list deriving `report.pdf` from a suffix a second time. Sixteen names,
and the count is asserted against what a run really writes.
"""

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

# Written by `emit_vex.py`, a command of its own, so an audit that read no
# advisory data produces no such file at all.
VEX_NAME = "findings.openvex.json"

# What the two reports are written as, and what `export_reports.py` renders them
# into. Suffixes rather than whole names, because that module derives the
# rendered names with `Path.with_suffix` from the two report names above and one
# derivation is enough.
MARKDOWN_SUFFIX = ".md"
HTML_SUFFIX = ".html"
PDF_SUFFIX = ".pdf"

# Every name a run can leave behind, in the order a reader meets them. The audit
# writes the first eleven; the VEX document and the four exports need their own
# command, so a given directory may hold any prefix of this set rather than all
# of it. `tests/web/test_artifact_inventory.py` holds it against what the
# writers actually produce.
ALL_NAMES = (
    SURFACES_NAME, AIBOM_NAME, SBOM_NAME, CYCLONEDX_NAME, MAPPING_NAME,
    FINDINGS_NAME, PLANNER_NAME, SARIF_NAME, REMEDIATION_NAME,
    REPORT_NAME, REMEDIATION_REPORT_NAME, VEX_NAME,
    REPORT_NAME.replace(MARKDOWN_SUFFIX, HTML_SUFFIX),
    REPORT_NAME.replace(MARKDOWN_SUFFIX, PDF_SUFFIX),
    REMEDIATION_REPORT_NAME.replace(MARKDOWN_SUFFIX, HTML_SUFFIX),
    REMEDIATION_REPORT_NAME.replace(MARKDOWN_SUFFIX, PDF_SUFFIX),
)

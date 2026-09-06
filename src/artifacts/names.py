"""What each artifact a run produces is called. Constants only.

Here rather than in the module that writes them, because the writers are not the
only readers: `deps/inputs.py` joins three of these paths, `evaluation/harness.py`
and `run_baseline.py` open two each, and `emit_vex.py` opens one. Every one of
those kept its own copy of the string, under a comment in `outputs.py` claiming
the names lived "in one place, because two copies is how the two copies start
disagreeing" -- which was true of the comment and false of the code.

Constants and nothing else, so a leaf package can read a filename without
importing the orchestration that writes it.
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

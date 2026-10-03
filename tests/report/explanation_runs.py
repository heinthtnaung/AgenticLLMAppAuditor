"""Records of why the sources differ, built by the real explainer, the model's reply from a table.

As `council_runs` does for the council: the records come out of
`cli.explanation_run`, the step an audit takes, so none has a shape no run can
produce. **Nothing here opens a socket** -- the model answers from a dict.
"""

import json

from cli.explanation_run import explanations
from council.providers import ollama_member
from report.absences import Coverage
from report.record import Report, build_report
from report_samples import (
    CONFIDENTIALITY_ONLY,
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    TOTAL_LOSS,
    catalogue,
    component,
    finding,
)

EXPLAINER = ollama_member("big:27b")
DETAILS = "An issue was discovered. Remote users can read some files."
QUOTED = "Remote users can read some files"
WHY = "It says some files, which one reader takes as limited and another as total."
# ghsa reads confidentiality as H and nvd as L, and the two agree on the rest.
DISAGREEING = {"ghsa": CONFIDENTIALITY_ONLY, "nvd": LOW_CONFIDENTIALITY}
# Kept on C; the second item's quotation is not in the advisory, so it is dropped.
EXPLAINED = {"items": [
    {"metric": "C", "why": WHY, "quotation": QUOTED},
    {"metric": "C", "why": "A second go.", "quotation": "all of the files"},
]}
INVENTED = {"items": [{"metric": "C", "why": "It is bad.", "quotation": "the whole disk"}]}


def replying(reply: dict):
    """Give a registry whose model answers every explanation from one table."""
    return {"ollama": lambda member, prompt: json.dumps(reply)}


def disputed(advisory_id: str):
    """Build one finding whose two sources read confidentiality apart."""
    return finding(component(), advisory_id=advisory_id, details=DETAILS, vectors=DISAGREEING)


def explained_report() -> Report:
    """Build a record of three findings: one explained, one not, and one whose sources agree."""
    kept, unkept = disputed("CVE-EXPLAINED"), disputed("CVE-UNEXPLAINED")
    agreeing = finding(component(), advisory_id="CVE-AGREED", vectors={"ghsa": TOTAL_LOSS})
    records = (
        *explanations((kept, agreeing), EXPLAINER, replying(EXPLAINED)),
        *explanations((unkept,), EXPLAINER, replying(INVENTED)),
    )
    found = (kept, unkept, agreeing)
    return build_report(
        PROVENANCE, catalogue(component()), found, {},
        coverage=Coverage(council_named=True), explanations=records,
    )

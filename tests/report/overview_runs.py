"""Findings the overview tests share: sources that disagree, agree, are refused or unscored.

Named `overview_runs` and not `samples`: pytest puts each test directory on the
path and imports by basename. The panel tests and the row tests build their records
off these helpers, so what "disagree", "refused" or "unscored" means moves both at
once rather than drifting between two copies.
"""

from organisation.risk import assess, per_source
from report.record import build_report
from report_samples import (
    CONFIDENTIALITY_ONLY,
    LOW_CONFIDENTIALITY,
    PROVENANCE,
    TOTAL_LOSS,
    VERSION_2_VECTOR,
    catalogue,
    component,
    finding,
)
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

DJANGO = component()
PYYAML = component("pyyaml", "5.1")


def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


EXPOSED = all_answers({"EXP-1": Answer.YES, "BUS-1": Answer.YES, "BUS-2": Answer.YES})


def disagreeing():
    """One finding two sources read differently."""
    return finding(DJANGO, vectors={"ghsa": LOW_CONFIDENTIALITY, "redhat": TOTAL_LOSS})


def agreeing():
    """One finding whose one readable source stands alone, so its sources agree."""
    return finding(PYYAML, advisory_id="CVE-AGREE", vectors={"ghsa": CONFIDENTIALITY_ONLY})


def refused():
    """One finding whose readable source stands beside a vector this calculator refused."""
    return finding(DJANGO, advisory_id="CVE-REFUSED",
                   vectors={"ghsa": CONFIDENTIALITY_ONLY, "nvd": VERSION_2_VECTOR})


def unscored():
    """One finding nobody published a readable vector for."""
    return finding(DJANGO, advisory_id="CVE-UNSCORED", vectors={"nvd": VERSION_2_VECTOR})


def report_of(*findings, council=(), answers=None):
    """Build a report over these findings, weighed and settled where a test asks."""
    risk = [assess(one, answers, per_source(one)) for one in findings] if answers else ()
    return build_report(PROVENANCE, catalogue(DJANGO, PYYAML), findings, {}, council, risk)

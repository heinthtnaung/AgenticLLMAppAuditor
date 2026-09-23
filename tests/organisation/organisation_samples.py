"""The findings and answers the organisation tests weigh, built by hand.

Named `organisation_samples` and not `samples`: pytest puts each test directory
on the path and imports by basename.
"""

import json

from deps.syft_report import Component
from deps.trivy_report import Advisory
from findings.finding import build_finding
from scoring.library import APPROVED_QUESTIONS
from scoring.question import Answer

CVSS_8_0 = "CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:U/C:H/I:H/A:H"  # 8.0
LOW_CONFIDENTIALITY = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"  # 5.3
TOTAL_LOSS = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"  # 9.8

# Both High on the published scale, and either side of an organisation boundary
# once this environment is weighed in.
HIGH_LOW = "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:L/A:L"  # 7.0
HIGH_HIGH = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"  # 7.5

LODASH = Component("lodash", "4.17.20", "pkg:npm/lodash@4.17.20", "npm", ("/package-lock.json",))

# The worked example's environment: no exposure, no threat, business-critical
# and in production and holding sensitive data.
WORKED_EXAMPLE_ANSWERS = {
    "EXP-1": Answer.NO, "EXP-2": Answer.NO, "EXP-3": Answer.NO,
    "EXP-4": Answer.NO, "EXP-5": Answer.NO,
    "BUS-1": Answer.YES, "BUS-2": Answer.YES, "BUS-3": Answer.YES, "BUS-4": Answer.NO,
    "THR-1": Answer.NO, "THR-2": Answer.NO, "THR-3": Answer.NO,
}


# Internet-facing but disabled: exposure 40 - 30 = 10, and nothing else answered
# Yes. It is what puts 7.0 and 7.5 either side of the Low/Medium boundary.
ON_THE_BOUNDARY = {
    **{identifier: Answer.NO for identifier in WORKED_EXAMPLE_ANSWERS},
    "EXP-1": Answer.YES,
    "EXP-5": Answer.YES,
}


def advisory(advisory_id: str = "CVE-2021-23337", **vectors) -> Advisory:
    """Build one advisory with whichever sources a test needs on it."""
    return Advisory(
        advisory_id=advisory_id,
        purl=LODASH.purl,
        fixed_version="4.17.21",
        summary="Command injection in lodash",
        details="A remote attacker can inject commands through a template option.",
        vectors=dict(vectors),
    )


def finding(advisory_id: str = "CVE-2021-23337", **vectors):
    """Build one finding through the real join, so its scores are really computed."""
    return build_finding(LODASH, advisory(advisory_id, **vectors))


BLANK_ANSWERS = {asked.question_id: "No" for asked in APPROVED_QUESTIONS}


def all_answers(overrides=None) -> dict:
    """Answer every approved question No, except the ones a test names."""
    return {**{asked.question_id: Answer.NO for asked in APPROVED_QUESTIONS}, **(overrides or {})}


def written(directory, complete: bool = True, **document) -> object:
    """Write one answer file, completing its answers unless a test is about not doing so."""
    if complete:
        document["answers"] = {**BLANK_ANSWERS, **document.get("answers", {})}
    path = directory / "answers.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path

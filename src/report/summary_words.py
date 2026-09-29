"""The summary line both renderings lead with: its counts, and what they leave out.

The wording is here once so the two pages cannot drift; where it goes on the
page, and how it wraps, stays with each rendering.

**A refused source is counted, and not as a disagreement.** A vector this
calculator could not read cannot be compared with the others, so it is no
dissent -- but a finding carrying one is not simply agreed either, and saying
nothing let that pass unseen. So the count is said, where there is one to say.

"0 findings across 38 components" over a repository whose manifests had no lock
file is not a clean result, and the summary is the first thing a reader reads.
So there it never stands alone: the pointer leads from the counts to the
manifests named under not assessed. "0 findings across 0 components" says less
still -- nothing was checked at all -- and gets a pointer of its own.

**The findings needing approval are counted beside the rule that marked them.**
Without organisation answers there is no risk score, so only disagreement can
mark one, and a count that did not say so would read as both halves checked.
Where any finding needs approval and none is recorded, the summary says that too.

**The secrets are counted at none as well.** They are not findings -- no CVSS,
no score, no council -- so they are a sentence of their own, and the count
names the rules that looked, because no match is not the same as no secret.
"""

from organisation.approval import NotApproved
from organisation.approval_rule import ApprovalReason
from report.approval_needed import needing_approval
from report.council_words import counted
from report.disagreement import carries_a_refused_source, sources_disagree
from report.record import Report

DISAGREE_CLAUSE = "{} sources that disagree"
REFUSED_CLAUSE = "{} a source this calculator could not read"
UNREAD_POINTER = "Not in these counts: {} with no lock file Syft reads, named under not assessed."
EMPTY_POINTER = "Not a clean result: Syft catalogued no component, so nothing was checked."
APPROVAL_COUNT = "Approval is needed for {} of {}: {}."
BOTH_HALVES = f"{ApprovalReason.RISK_BAND.value}, or {ApprovalReason.SOURCES_DISAGREE.value}"
UNWEIGHED = (
    f"With no organisation answers, none was checked for {ApprovalReason.RISK_BAND.value}."
)
UNAPPROVED = "No approval is recorded for this audit."
# No apostrophe: the page escapes one to `&#x27;`, a number to anything reading its figures.
SECRETS_COUNT = "{} matched the secret rules built into Trivy."


def counts(report: Report) -> str:
    """Count the findings, those whose readable sources disagree, and any with a refused source."""
    # A vector the calculator refused is not counted as a dissent, whatever it says.
    contested = len([one for one in report.findings if sources_disagree(one)])
    refused = len([one for one in report.findings if carries_a_refused_source(one)])
    found = counted(len(report.findings), "finding")
    catalogued = counted(report.component_count, "component")
    said = f"{found} across {catalogued}. {DISAGREE_CLAUSE.format(carry(contested))}"
    # Left out at none, so a run with no refused source reads as it always has.
    return f"{said}; {REFUSED_CLAUSE.format(carry(refused))}." if refused else f"{said}."


def carry(count: int) -> str:
    """Give a count of findings with its verb, singular when there is one of them."""
    return f"{count} carries" if count == 1 else f"{count} carry"


def unread_pointer(report: Report) -> str:
    """Point from the counts to the manifests nothing was read from, or give nothing when none."""
    unread = report.coverage.unread_manifests
    if not unread:
        return ""
    return UNREAD_POINTER.format(counted(len(unread), "manifest"))


def inventory_pointer(report: Report) -> str:
    """Say an inventory of nothing is not a clean result, or give nothing when it holds one."""
    if report.component_count:
        return ""
    return EMPTY_POINTER


def approval_count(report: Report) -> str:
    """Count the findings needing approval and the rule that marked them, and say if unapproved."""
    if not report.findings:
        return ""
    needing = len(needing_approval(report))
    # Without answers there is no risk score, so only disagreement could mark a finding.
    halves = BOTH_HALVES if report.risk else ApprovalReason.SOURCES_DISAGREE.value
    said = [APPROVAL_COUNT.format(needing, len(report.findings), halves)]
    if not report.risk:
        said.append(UNWEIGHED)
    if needing and isinstance(report.approval, NotApproved):
        said.append(UNAPPROVED)
    return " ".join(said)


def secrets_count(report: Report) -> str:
    """Count the secrets Trivy's built-in rules matched, and say so at none too."""
    return SECRETS_COUNT.format(counted(len(report.secrets), "secret"))

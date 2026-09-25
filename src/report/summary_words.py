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
manifests named under not assessed.
"""

from report.council_words import counted
from report.disagreement import carries_a_refused_source, sources_disagree
from report.record import Report

DISAGREE_CLAUSE = "{} sources that disagree"
REFUSED_CLAUSE = "{} a source this calculator could not read"
UNREAD_POINTER = "Not in these counts: {} with no lock file Syft reads, named under not assessed."


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

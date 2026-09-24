"""What both renderings add to the summary line when the scan read nothing from a manifest.

"0 findings across 38 components" over a repository whose manifests had no lock
file is not a clean result, and the summary is the first thing a reader reads.
So there it never stands alone: this points from the counts to the manifests
named under not assessed. The wording is here once so the two pages cannot
drift; where it goes on the page stays with each rendering.
"""

from report.council_words import counted
from report.record import Report

UNREAD_POINTER = "Not in these counts: {} with no lock file Syft reads, named under not assessed."


def unread_pointer(report: Report) -> str:
    """Point from the counts to the manifests nothing was read from, or give nothing when none."""
    unread = report.coverage.unread_manifests
    if not unread:
        return ""
    return UNREAD_POINTER.format(counted(len(unread), "manifest"))

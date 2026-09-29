"""The findings that need approval, on the terminal, each with the reasons the rule gives.

A mark beside each finding does not fit this page: an agreeing finding is one
line already near its width. So they are listed in a block of their own, which
also puts each reason on the line, because a mark nobody can trace to the rule
is a flag nobody can check.
"""

from report.approval_needed import NEEDS_APPROVAL, needing_approval, reasons_for
from report.record import Report
from report.text_layout import INDENT, SOURCE_SEPARATOR, id_width, identified, section


def approval_needed_block(report: Report) -> str:
    """List every finding the rule marks as needing approval, with the reasons it meets."""
    needing = needing_approval(report)
    if not needing:
        return ""
    width = id_width(needing)
    entries = [f"{INDENT}{identified(one, width)}  {reasons_line(report, one)}" for one in needing]
    return section(f"{NEEDS_APPROVAL.upper()} ({len(needing)})", entries)


def reasons_line(report: Report, finding) -> str:
    """Give the reasons one finding needs approval, side by side in the rule's order."""
    return SOURCE_SEPARATOR.join(reason.value for reason in reasons_for(report, finding))

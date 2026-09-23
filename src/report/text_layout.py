"""The typography the terminal rendering shares: spacing, columns, and a titled block.

Column widths are measured off what is actually there rather than guessed, so a
GHSA identifier nineteen characters long does not push one row out of line with
its neighbours and there is no constant to outgrow.
"""

INDENT = "  "
SOURCE_SEPARATOR = "  ·  "
NAME_WIDTH = 30


def section(title: str, entries: list[str]) -> str:
    """Put a titled block together."""
    return "\n".join([title, *entries])


def named(finding) -> str:
    """Name the component a finding is against, padded so the columns line up."""
    return f"{finding.component.name} {finding.component.version}".ljust(NAME_WIDTH)


def identified(finding, width: int) -> str:
    """Give the advisory id, padded to the widest in its own group."""
    return finding.advisory.advisory_id.ljust(width)


def id_width(findings: tuple) -> int:
    """Widen the id column to the longest id present rather than guessing one."""
    return max((len(one.advisory.advisory_id) for one in findings), default=0)

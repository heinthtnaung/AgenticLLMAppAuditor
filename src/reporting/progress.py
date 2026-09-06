"""What a run tells the operator while it works, on stderr.

Split out of `outputs.py`, which was doing four jobs. These two are the only
place the auditor speaks to a person mid-run rather than writing a file, and
both exist because the fact they carry is invisible on disk: a file the scan
could not read leaves no trace in `surfaces.json`, and a mapping covering a
third of the surfaces looks exactly like one covering all of them.

stderr, not stdout, so a caller piping the artifact paths somewhere still sees
the warnings.
"""

import sys

from artifacts.skipped_file import SkippedFile


def report_skipped_files(skipped: list[SkippedFile]) -> None:
    """Warn about each file the scan could not analyse."""
    for record in skipped:
        where = f" (line {record.line})" if record.line else ""
        print(f"warning: skipped {record.file}: {record.reason}{where}", file=sys.stderr)


def report_coverage(mapping_document: dict) -> None:
    """Say how much of the app the mapping reached.

    Printed rather than stored: a mapping covering a third of the surfaces
    looks the same on disk as one covering all of them.
    """
    total, mapped = mapping_document["surface_count"], mapping_document["mapped_count"]
    share = f"{mapped / total:.0%}" if total else "n/a"
    print(f"  mapped {mapped} of {total} surfaces ({share})", file=sys.stderr)
    for reason, count in sorted(mapping_document["reason_counts"].items()):
        if count:
            print(f"    {reason:22} {count}", file=sys.stderr)
    for name in mapping_document["undeclared_components"]:
        print(f"  used but never declared: {name}", file=sys.stderr)

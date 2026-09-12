"""What a run tells the operator while it works, on stderr.

Split out of `outputs.py`, which was doing four jobs. These two are the only
place the auditor speaks to a person mid-run rather than writing a file, and
both exist because the fact they carry is invisible on disk: a file the scan
could not read leaves no trace in `surfaces.json`, and a mapping covering a
third of the surfaces looks exactly like one covering all of them.

stderr, not stdout, so a caller piping the artifact paths somewhere still sees
the warnings.

`stage` was added for the web UI, which shows an audit advancing rather than a
spinner. It takes its listener as an **argument**, threaded down from the entry
point: a module-level callback would make what `audit_run.audit` does depend on
state no caller can see in its signature, and that module's own docstring
already sets the opposite rule ("Nothing in this module chooses a model. It is
handed one"). With no listener it prints, exactly as the two functions below do,
so the command line gained progress lines and nothing else changed.
"""

import sys
from typing import Callable

from artifacts.skipped_file import SkippedFile

# Called with (stage name, detail) at each boundary. Detail is for a person, so
# nothing may join on it -- the same rule a probe's `detail` carries.
StageListener = Callable[[str, str], None]

# Every boundary an audit announces, in the order they happen. A closed
# vocabulary, like `PROBE_OUTCOMES` and `OWASP_IDS`: a caller showing progress
# needs to know the whole list in advance to say what has not happened yet, and
# a typo that silently became a new stage would leave a step showing as pending
# for the rest of the run.
STAGES = (
    "fetch",         # the tree is present and pinned
    "surfaces",      # the LLM surfaces are extracted
    "dependencies",  # SBOM, AIBOM and the mapping
    "advisories",    # advisory data read, or established as absent
    "checks",        # every check has run
    "advice",        # remediation advice built
    "write",         # artifacts on disk
    "publish",       # VEX and the exported reports
)


def stage(name: str, detail: str = "", on_stage: StageListener | None = None) -> None:
    """Announce one boundary: on stderr always, and to a listener when given."""
    if name not in STAGES:
        raise ValueError(f"unknown stage {name!r}; expected one of {STAGES}")
    print(f"-- {name}{f': {detail}' if detail else ''}", file=sys.stderr)
    if on_stage is not None:
        on_stage(name, detail)


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

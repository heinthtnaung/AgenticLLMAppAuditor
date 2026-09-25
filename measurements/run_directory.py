"""The directory a recorded audit runs in, which is not the project root, and what is kept of it.

`audit` writes `reports/<repository>.txt`, `.json` and `.html` where it is run.
Run from the project root, as the recorder once ran it, a recorded run replaced
the operator's own reports there, and its JSON -- the one artefact holding every
member's answer on a settled metric -- was kept nowhere.

So the audit runs in a temporary directory instead, holding a link to every
top-level entry of the project but `reports/`. Every relative path the command
names resolves as written -- `fetched/vulnscout`, and an answer file at the root
-- so the report still reads `Audit of fetched/vulnscout`, and the audit makes a
`reports/` of its own there. All three of its renderings are copied out, byte
for byte, before the directory goes: whatever `--format` the command asked for,
the text is kept as text and the JSON as JSON.
"""

import shutil
import sys
from pathlib import Path

from run_provenance import REPOSITORY_ROOT, RecordingFailed

sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from cli.arguments import HTML_FORMAT, JSON_FORMAT, TEXT_FORMAT  # noqa: E402
from cli.main import FOUND_NOTHING, FOUND_SOMETHING  # noqa: E402
from cli.report_files import REPORTS_DIRECTORY, SUFFIXES  # noqa: E402

# An audit that exits with one of these ran, and so wrote its reports; one that
# could not run wrote none, and its exit code in the provenance already says so.
AUDIT_RAN = (FOUND_NOTHING, FOUND_SOMETHING)


def link_project(root: Path, directory: Path) -> None:
    """Link every top-level entry of the project into `directory`, but its `reports/`."""
    for entry in sorted(root.iterdir()):
        if entry.name != REPORTS_DIRECTORY.name:
            (directory / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())


def keep_reports(directory: Path, *, text: Path, record: Path, page: Path, exit_code: int) -> None:
    """Copy out the three renderings the audit wrote, byte for byte, refusing to lose one."""
    written = written_reports(directory)
    copies = {
        SUFFIXES[TEXT_FORMAT]: text, SUFFIXES[JSON_FORMAT]: record, SUFFIXES[HTML_FORMAT]: page,
    }
    present = [suffix for suffix in copies if suffix in written]
    for suffix in present:
        shutil.copyfile(written[suffix], copies[suffix])
    missing = [suffix for suffix in copies if suffix not in present]
    if missing and exit_code in AUDIT_RAN:
        said = " or ".join(missing)
        raise RecordingFailed(f"the audit exited {exit_code} but wrote no {said} report to keep")


def written_reports(directory: Path) -> dict[str, Path]:
    """Find what the audit wrote into its `reports/`, one file for each suffix."""
    folder = directory / REPORTS_DIRECTORY
    found = sorted(folder.iterdir()) if folder.is_dir() else []
    by_suffix = {one.suffix: one for one in found}
    if len(by_suffix) != len(found):
        named = ", ".join(one.name for one in found)
        raise RecordingFailed(f"the audit wrote more than one report of a kind: {named}")
    return by_suffix

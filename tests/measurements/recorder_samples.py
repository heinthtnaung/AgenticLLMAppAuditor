"""A stand-in for `audit`, and a project for it to run in, for the recorder's tests.

The stand-in is a real process, so its streams, its exit code and the files it
writes travel the way an audit's do, and no model, scanner or database is asked.
It writes its three reports into `reports/` where it runs, making the folder or
reusing one as `audit` does, prints on stdout the one `--format` names -- text
unless told otherwise -- byte for byte, and refuses to run -- exit 2, no reports,
nothing printed -- if a path it is given does not resolve.

Named `recorder_samples` and not `samples`: pytest puts each test directory on
the path and imports by basename.
"""

import sys
from pathlib import Path

# Not ASCII, so a copy that re-encoded a rendering would not be byte-identical.
TEXT = "Audit of fetched/vulnscout\n  caf\u00e9 \u2014 the text report\n".encode()
RECORD = '{"run": {"repository": "fetched/vulnscout"}, "note": "café —"}\n'.encode()
PAGE = b"<!DOCTYPE html>\n<title>Audit of fetched/vulnscout</title>\n"
OPERATORS_OWN = b"the operator's own report, from a run of their own\n"
PROGRESS = "call 1/8\n"
CANNOT_RUN = 2

FAKE_AUDIT = f"""
import pathlib, sys
exit_code, *paths = sys.argv[1:]
printed = "text"
if "--format" in paths:
    printed = paths[paths.index("--format") + 1]
    paths = paths[:paths.index("--format")]
if not all(pathlib.Path(one).exists() for one in paths):
    sys.exit({CANNOT_RUN})
renderings = {{"text": {TEXT!r}, "json": {RECORD!r}, "html": {PAGE!r}}}
reports = pathlib.Path("reports")
reports.mkdir(exist_ok=True)
(reports / "vulnscout.txt").write_bytes(renderings["text"])
(reports / "vulnscout.json").write_bytes(renderings["json"])
(reports / "vulnscout.html").write_bytes(renderings["html"])
sys.stdout.buffer.write(renderings[printed])
print({PROGRESS.strip()!r}, file=sys.stderr)
sys.exit(int(exit_code))
"""
AUDIT_SCRIPT = "fake_audit.py"
REPOSITORY = "fetched/vulnscout"
ANSWERS = "answers.example.json"


def audit_command(exit_code: int, *arguments: str) -> tuple[str, ...]:
    """Give the command that runs the stand-in from the project, by a relative path.

    The paths to check come first, and a `--format` with its value, if any, last.
    """
    return (sys.executable, AUDIT_SCRIPT, str(exit_code), *arguments)


def made_project(root: Path) -> Path:
    """Lay out a project with a repository, an answer file, the stand-in and its own reports."""
    (root / REPOSITORY).mkdir(parents=True)
    (root / REPOSITORY / "package-lock.json").write_text("{}", encoding="utf-8")
    (root / ANSWERS).write_text("{}", encoding="utf-8")
    (root / AUDIT_SCRIPT).write_text(FAKE_AUDIT, encoding="utf-8")
    (root / "reports").mkdir()
    (root / "reports" / "vulnscout.json").write_bytes(OPERATORS_OWN)
    return root

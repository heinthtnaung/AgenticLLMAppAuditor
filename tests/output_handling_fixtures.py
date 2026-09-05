"""The tree and the two helpers both LLM02 test files build on.

Shared because a snippet copied into two files is a snippet that drifts: the
same `app.py` anchors the query-text tests in `test_output_handling.py` and the
join tests in `test_output_handling_join.py`, and they must stay the same file
for the two to be talking about one audit.

Everything is written into `tmp_path` by the caller. Nothing here reads a
repository this project does not own, and a synthetic tree is weaker than a
real one: no oversized file, no non-UTF-8 source, no shape nobody thought of.
"""

from pathlib import Path

from artifacts.finding import Finding
from artifacts.surface import DATA_SOURCE, Surface
from checks.output_handling import find_in_tree, run_over_repo
from parsing.extractor_python import extract_file, parse_file

FILE = "app.py"

# Every snippet below puts the call one line past a header, so a finding
# anchored on the wrong line cannot pass by landing on line 1 by accident.
QUERY_LINE = 2

# The motivating shape: the value decides what the database runs.
INTERPOLATED_QUERY = '''def read(cursor, user_id):
    cursor.execute(f"SELECT * FROM t WHERE id = '{user_id}'")
'''

# A query written out in full: the text is decided before the program runs.
CONSTANT_QUERY = '''def read(cursor):
    cursor.execute("SELECT * FROM t")
'''


def audit_source(tmp_path: Path, source: str) -> list[Finding]:
    """Write one Python file into an empty repository and run the check over it.

    The surfaces are the detector's own, so the anchor a finding is joined to is
    the one a real audit of this file would have had.
    """
    path = tmp_path / FILE
    path.write_text(source, encoding="utf-8")
    return run_over_repo(str(tmp_path), extract_file(path, FILE))


def findings_anchored_on(tmp_path: Path, source: str,
                         surfaces: list[Surface]) -> list[Finding]:
    """Run the check over one written file with the surfaces the caller chose as anchors."""
    path = tmp_path / FILE
    path.write_text(source, encoding="utf-8")
    return find_in_tree(parse_file(path), FILE, surfaces)


def surfaces_and_findings(tmp_path: Path,
                          source: str) -> tuple[list[Surface], list[Finding]]:
    """Write one Python file and return both the detector's surfaces and the check's findings.

    A test expecting no finding uses this to first show there *was* an anchor
    to report on, so it cannot pass over a run that found no surface at all.
    """
    path = tmp_path / FILE
    path.write_text(source, encoding="utf-8")
    surfaces = extract_file(path, FILE)
    return surfaces, run_over_repo(str(tmp_path), surfaces)


def execute_anchors(surfaces: list[Surface]) -> list[tuple[str, int]]:
    """The name and line of every data-source surface, sorted so a test can pin the set."""
    return sorted((s.name, s.line) for s in surfaces if s.kind == DATA_SOURCE)

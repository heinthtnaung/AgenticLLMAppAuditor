"""The line the README says a run ends with, checked against the code that prints it.

`README.md` quotes the one stderr line that follows the report, and it is the
line a reader copies to find the three files. It is derived here from
`cli.report_files` rather than pasted, so changing its wording or the files'
names in either place turns this red. Nothing here runs a scan, so it needs no
`README_LIVE_SCAN`.
"""

from pathlib import Path

from cli.report_files import REPORTS_DIRECTORY, report_paths, where_written
from readme_markers import read_readme
from readme_runs import REPOSITORY


def test_the_readme_quotes_the_line_a_run_of_its_repository_ends_with():
    paths = tuple(report_paths(Path(REPOSITORY), REPORTS_DIRECTORY).values())
    assert where_written(paths).strip() in read_readme()

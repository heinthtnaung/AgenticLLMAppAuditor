"""The README's table of tests that skip unless asked for, held to the files and to pytest.

A plain run counts the gated tests as skipped, and a reader of the total asks
what they are, so the page names each gated file, its flag and how many tests it
holds. A count nobody checks is wrong the day a live test is added. `readme_gated`
reads the table and finds the files that declare a flag; this holds one to the
other, and then asks pytest.

The gated files are run once with every flag taken out of the environment, so
each test is collected and skips before its body runs: nothing live runs, and
this needs no flag and no corpus. The number of skips in a file is the number of
tests it holds, provided nothing in it ran, and that is checked too. Each skip's
reason must name its row's flag exactly, as `<FLAG>=1`, because the reason is
what tells a reader of a plain run which flag would run it.
"""

import os
import re
import subprocess
import sys
from dataclasses import dataclass

import pytest

from readme_gated import (
    TESTS_FOLDER,
    live_flags,
    misnamed,
    names_flag,
    rows_on,
    shortened,
    suffixed,
    table_of,
    trailing,
    unquoted,
    without_row,
)
from readme_markers import PROJECT_ROOT, read_readme

SKIP_LINE = re.compile(r"^SKIPPED \[(?P<count>\d+)\] (?P<path>[^:]+):\d+: (?P<reason>.+)$")
ONLY_SKIPS = re.compile(r"^(?P<count>\d+) skipped in [\d.]+s$")
RUN_TIMEOUT_SECONDS = 120
DAMAGE = {
    "row removed": without_row,
    "flag unquoted": unquoted,
    "flag misnamed": misnamed,
    "flag suffixed": suffixed,
}
REASON = "set SYFT_LIVE_SCAN=1 to run Syft over each case for real"
# Read at collection, so that each row is its own test.
PAGE = read_readme()
ROWS = rows_on(PAGE)
DECLARED = live_flags(PROJECT_ROOT)


@dataclass(frozen=True)
class Skip:
    """One line of pytest's skip summary: how many tests, in which file, and why."""

    count: int
    path: str
    reason: str


def run_with_flags_off() -> list[str]:
    """Run the gated files with no flag set, so each test skips, and give what pytest printed."""
    flags = {row.flag for row in ROWS} | set(DECLARED.values())
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", *DECLARED],
        cwd=PROJECT_ROOT,
        env={name: value for name, value in os.environ.items() if name not in flags},
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_SECONDS,
    )
    return finished.stdout.splitlines()


def skip_of(read: re.Match) -> Skip:
    """Give one line of the skip summary the skip pattern matched."""
    return Skip(int(read["count"]), read["path"], read["reason"])


@pytest.fixture(scope="module")
def printed() -> list[str]:
    """Give what one run of every gated file printed, shared by every row's checks."""
    return run_with_flags_off()


@pytest.fixture(scope="module")
def skips(printed: list[str]) -> list[Skip]:
    """Give every skip that run reported."""
    return [skip_of(read) for read in map(SKIP_LINE.match, printed) if read]


def test_the_table_names_every_gated_file_with_the_flag_that_file_declares():
    assert DECLARED, "no test file declares a live flag, so there is nothing to hold the table to"
    assert table_of(PAGE) == DECLARED


@pytest.mark.parametrize("damage", DAMAGE.values(), ids=DAMAGE)
@pytest.mark.parametrize("row", ROWS, ids=[row.flag for row in ROWS])
def test_a_damaged_row_no_longer_matches_the_declared_flags(row, damage):
    damaged = damage(PAGE, row)
    assert damaged != PAGE
    assert table_of(damaged) != DECLARED


@pytest.mark.parametrize(
    "flag, named",
    [("SYFT_LIVE_SCAN", True), ("SYFT_LIVE", False), ("LIVE_SCAN", False), ("SCAN", False)],
)
def test_a_flag_is_named_only_as_a_whole_word(flag, named):
    assert names_flag(REASON, flag) is named


def test_a_gated_file_that_does_not_declare_its_flag_as_a_constant_is_not_found(tmp_path):
    # Accepted: discovery keys on the one convention every gated file follows,
    # so a file gated another way would need a row and nothing would ask for one.
    folder = tmp_path / TESTS_FOLDER
    folder.mkdir()
    (folder / "test_declared_live.py").write_text('LIVE = "DECLARED_LIVE"\n', encoding="utf-8")
    gated_otherwise = 'pytestmark = skipif(not os.environ.get("OTHER_LIVE"), reason="")\n'
    (folder / "test_other_live.py").write_text(gated_otherwise, encoding="utf-8")
    assert live_flags(tmp_path) == {"tests/test_declared_live.py": "DECLARED_LIVE"}


def test_with_every_flag_off_every_test_in_the_gated_files_skips_and_none_runs(printed):
    # Only then is a file's number of skips the number of tests it holds.
    total = ONLY_SKIPS.match(printed[-1]) if printed else None
    assert total, f"expected only skips, and pytest ended with {printed[-1:]}"
    assert int(total["count"]) == sum(row.count for row in ROWS)


@pytest.mark.parametrize("row", ROWS, ids=[row.flag for row in ROWS])
def test_each_row_counts_the_tests_its_file_holds(skips, row):
    assert sum(one.count for one in skips if one.path == row.path) == row.count


@pytest.mark.parametrize("row", ROWS, ids=[row.flag for row in ROWS])
def test_each_files_skip_reason_names_the_flag_its_row_gives_exactly(skips, row):
    reasons = {one.reason for one in skips if one.path == row.path}
    assert reasons and all(names_flag(reason, row.flag) for reason in reasons)
    assert not any(names_flag(reason, shortened(row.flag)) for reason in reasons)
    assert not any(names_flag(reason, trailing(row.flag)) for reason in reasons)

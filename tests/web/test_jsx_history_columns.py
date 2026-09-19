"""The eight headings and the eight cells under them are one claim, paired off.

A table is two lists that have to stay in step, and nothing in this suite held
them together. Three defects were measured green:

- `<th>Options</th>` deleted, leaving eight cells under seven headings -- every
  column after it reading under the wrong name.
- the Findings and Surfaces cells transposed, so the column headed "Findings"
  shows the surface count.
- `when(run.started_at)` changed to `when(run.finished_at)` under "Started".

**This change is the edit that makes it urgent**, which is the argument for the
file: it removed the App column from *both* halves at once, so removing only the
`<th>` would have shipped with the suite green and every remaining column
mislabelled by one.

**`COLUMNS` is an ordered inventory, not a sample.** Each entry pairs a heading
with the expression that has to be inside the cell under it, and the test walks
the two lists in source order and compares them pairwise. That is deliberate:
the stopping rule this suite arrived at after seven rounds of sampling is that a
*rendered* relation is only closed by enumerating a finite inventory. Ten pairs
is finite, so this is closed rather than merely longer -- and an eleventh column
fails here until its row is written, which is the property a spot check cannot
have. It was eight until 2026-09-18, when the two model names left the Options
cell for columns of their own; the enumeration was **extended, not loosened**,
which is the only way a closed inventory survives a change.

**The table has one unlabelled column and it is enumerated too.** The leading
`<th className="pick" />` carries no text, so the heading sweep cannot see it
while the cell sweep can -- eleven cells under ten headings, which is exactly
the drift `paired` exists to report. It is named in `THE_UNLABELLED_COLUMN` and
asserted as the first cell, so the column is accounted for rather than silently
dropped to make the two lists the same length.

`test_jsx_row_files.py` holds what the last cell's three words *mean*; this
holds that they sit under "Files". The two are joined by `COLUMNS`' last entry
and nothing else.

No test in this suite renders React -- a recorded defect -- so this reads the
two lists as text. It can show the pairing is *written* correctly; it cannot show
a browser laying the cells out in that order.

Reads one component as text. No fastapi, no node, no build.
"""

import re

import pytest

from .jsx_sweep import FRONTEND_SRC, strip_comments

GROUP = FRONTEND_SRC / "components" / "HistoryGroup.jsx"

# Every column, in the order the table writes them: the heading, and the
# expression that must appear in the cell beneath it. The whole inventory, so a
# column added or dropped on one side alone cannot pass.
COLUMNS = (
    ("Started", "when(run.started_at)"),
    ("Auditor", "run.auditor"),
    ("Status", "run.status"),
    ("Options", "<RunOptions options={run.options} />"),
    # Fed the whole run rather than its options: what answered is served beside
    # the record, because `options.model` is only what was asked for.
    ("Local", "<ModelCell shown={localModel(run)} />"),
    ("Cloud", "<ModelCell shown={cloudModel(run)} />"),
    ("Findings", "count(run.finding_count)"),
    ("Surfaces", "count(run.surface_count)"),
    ("Took", "seconds(run.seconds)"),
    ("Files", "files(run)"),
)

# The one column with no heading: the select box each row is picked with. Its
# cell is what the pair sweep would otherwise read under "Started".
THE_UNLABELLED_COLUMN = "pick__box"

# The two halves, as the source writes them. `Row` is sliced out first so the
# group header's own `<span>`s cannot be read as cells.
THE_HEADING = re.compile(r"<th>([^<]+)</th>")
# A cell is a `<td>` **or a component that renders exactly one**. `ModelCell`
# is the only one of the second kind and it writes its own `<td className=
# "nowrap">`, so a sweep for literal `<td>` alone reads eight cells under ten
# headings -- the drift this file reports, caused by the guard rather than by
# the page. Named as one alternation so the two kinds stay in source order,
# which is the whole subject here.
THE_CELL = re.compile(
    r"<td\b[^>]*>(?P<written>.*?)</td>|(?P<component><ModelCell\b[^>]*/>)", re.DOTALL)
THE_ROW_FUNCTION = re.compile(r"function Row\(\{ run[^)]*\}\) \{(.*?)\n\}", re.DOTALL)

# Two plants. The first is the transposition -- both expressions are present in
# the file either way, so only the pairing tells them apart.
THE_COLUMNS_TRANSPOSED = (
    ("Findings", "count(run.surface_count)"),
    ("Surfaces", "count(run.finding_count)"),
)

# The second is the drift itself: a table with one heading fewer than it has
# cells, written out as source so `paired` really runs over it. The first
# version of this plant compared two lengths that were 3 and 8 -- a tautology
# that never reached the message it was advertising.
A_TABLE_WITH_A_HEADING_DROPPED = """
              <tr>
                <th className="pick" />
                <th>Started</th><th>Auditor</th>
              </tr>
function Row({ run, picked, onPick }) {
  return (
    <tr>
      <td className="pick"><input className="pick__box" /></td>
      <td>{when(run.started_at)}</td>
      <td>{run.auditor}</td>
      <td>{run.status}</td>
    </tr>
  );
}
"""

# What that failure has to say, so the plant holds the message and not just the
# refusal.
THE_DRIFT_MESSAGE = "the two halves of the table have drifted"

# A timestamp a run has and this column is not about: `finished_at` under
# "Started" is a plausible-looking cell and a wrong one.
THE_WRONG_TIMESTAMP = "when(run.finished_at)"


def group() -> str:
    """The group header's own source, comments stripped: the table lives beside `Row`."""
    return strip_comments(GROUP.read_text(encoding="utf-8"))


def headings(text: str) -> list[str]:
    """Every column heading, in the order the table writes them."""
    return THE_HEADING.findall(text)


def cells(text: str) -> list[str]:
    """Every cell of one row, in order. Read from `Row` alone, not the whole file."""
    found = THE_ROW_FUNCTION.search(text)
    assert found, f"{GROUP.name} no longer declares `function Row({{ run, ... }})`"
    return [" ".join((cell.group("written") or cell.group("component")).split())
            for cell in THE_CELL.finditer(found.group(1))]


def labelled_cells(text: str) -> list[str]:
    """Every cell that sits under a heading: the row without its unlabelled first column."""
    found = cells(text)
    assert THE_UNLABELLED_COLUMN in found[0], (
        f"the first cell is no longer the one with no heading over it: {found[0]!r}")
    return found[1:]


def paired(text: str) -> list[tuple[str, str]]:
    """Each heading beside the cell written under it, or say the two halves differ in length."""
    head, body = headings(text), labelled_cells(text)
    assert len(head) == len(body), (
        f"{len(head)} headings and {len(body)} cells: the two halves of the table have "
        "drifted, so every column after the difference reads under the wrong name")
    return list(zip(head, body))


# --- the inventory is the table ------------------------------------------------

def test_the_headings_are_the_ten_this_file_names_in_order() -> None:
    """The inventory, not a sample: an eleventh column fails here until its row is written."""
    assert headings(group()) == [heading for heading, _ in COLUMNS]


def test_the_two_halves_are_the_same_length() -> None:
    """A dropped `<th>` leaves ten cells under nine headings, which this change made reachable."""
    assert len(headings(group())) == len(labelled_cells(group()))


def test_the_unlabelled_column_is_the_first_cell_and_not_one_of_the_ten() -> None:
    """Accounted for rather than trimmed away: it is why the two raw lists differ by one."""
    assert len(cells(group())) == len(COLUMNS) + 1
    assert THE_UNLABELLED_COLUMN in cells(group())[0]
    assert len(COLUMNS) == len(labelled_cells(group()))


def test_every_cell_carries_what_its_heading_promises() -> None:
    """Walked pairwise: the transposition is invisible to any check that reads one half."""
    wrong = [f"{heading}: {cell}" for (heading, cell), (_, expected) in
             zip(paired(group()), COLUMNS) if expected not in cell]
    assert wrong == []


# --- and the pairing is what is doing the work ---------------------------------

def test_transposed_columns_are_not_accepted() -> None:
    """Planted: both expressions are in the file either way, so only the pairing separates them."""
    wrong = [heading for (heading, cell), (_, expected) in
             zip(THE_COLUMNS_TRANSPOSED, COLUMNS[6:8]) if expected not in cell]
    assert wrong == ["Findings", "Surfaces"]


def test_a_dropped_heading_is_reported_as_drift_and_not_as_a_stray_cell() -> None:
    """Planted, and over real source: the failure has to name the drift, not one bad cell.

    `paired` is run rather than two lengths compared, because the message is
    the point -- a reader who sees "three cells stopped matching" looks at
    three cells, and a reader who sees "the two halves have drifted" looks at
    the table.
    """
    with pytest.raises(AssertionError, match=THE_DRIFT_MESSAGE):
        paired(A_TABLE_WITH_A_HEADING_DROPPED)


def test_the_started_column_is_not_the_finish_time() -> None:
    """The third measured defect: a plausible cell under an honest heading."""
    started = dict(paired(group()))["Started"]
    assert THE_WRONG_TIMESTAMP not in started


def test_the_sweep_read_both_halves_and_not_an_empty_file() -> None:
    """Non-vacuity: two empty lists are equal in length and satisfy every pairwise check."""
    assert len(headings(group())) == len(COLUMNS)
    assert all(cell for cell in cells(group()))

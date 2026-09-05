"""Every way a dataset loader is written, and whether the DATASET kind reaches it.

`DATASET` is the AIBOM kind with the narrowest path to it: a surface has to be
extracted first, and the two data-source tables match *different call shapes*
-- `DATA_SOURCE_CALLS` compares the whole dotted name, `DATA_SOURCE_METHODS`
compares the last segment and requires a receiver. So which spellings of
`load_dataset` and `load_from_disk` an app can use and still be recorded is a
property of the tables, not of the kind, and it is not obvious from either.

That is the trap the import guard in `aibom.py` structurally cannot see: the
guard asks whether a *name* is emitted, and a name can be emitted in one
spelling and missed in another. This file asks the question the guard cannot,
and it asks it at **both layers** -- extracted as a surface, and lifted to a
DATASET component -- so a fix that reached only one of them is visible. That is
what found `ds.load_dataset`, which was missed while the other five spellings
were not, because the table then carried a hard-coded `datasets.` prefix that
no alias survives.

The app is written here and really extracted, so each row is a spelling a
person could plausibly write, not a name looked up in a table.
"""

import pytest

from artifacts.aibom import DATASET, build_aibom
from artifacts.surface import DATA_SOURCE
from parsing.extractor import extract_repo

APP_FILE = "corpus.py"
APP_SOURCE = '''import datasets
import datasets as ds
from datasets import load_dataset, load_from_disk

first = load_dataset("squad")
second = datasets.load_dataset("squad")
third = ds.load_dataset("squad")
fourth = load_from_disk("./cache")
fifth = datasets.load_from_disk("./cache")
sixth = ds.load_from_disk("./cache")
'''

# (line, the name the extractor records) for each spelling above. Three ways to
# write each of the two loaders: imported bare, qualified by its package, and
# qualified by an alias of its package. All three are ordinary Python and the
# HuggingFace documentation uses more than one of them.
DATASET_CALL_SHAPES = [
    (5, "load_dataset"),
    (6, "datasets.load_dataset"),
    (7, "ds.load_dataset"),
    (8, "load_from_disk"),
    (9, "datasets.load_from_disk"),
    (10, "ds.load_from_disk"),
]


def app_surfaces(tmp_path) -> dict[int, str]:
    """Write the app, extract it, and return the surface name found on each line."""
    (tmp_path / APP_FILE).write_text(APP_SOURCE, encoding="utf-8")
    surfaces = extract_repo(str(tmp_path)).surfaces
    assert surfaces, "the app yielded no surfaces at all, so nothing below would prove anything"
    return {surface.line: surface.name
            for surface in surfaces if surface.kind == DATA_SOURCE}


def app_datasets(tmp_path) -> dict[int, str]:
    """The AIBOM's DATASET components for the same app, by the line they came from."""
    (tmp_path / APP_FILE).write_text(APP_SOURCE, encoding="utf-8")
    document = build_aibom(extract_repo(str(tmp_path)).surfaces)
    return {c["line"]: c["name"] for c in document["components"] if c["kind"] == DATASET}


@pytest.mark.parametrize("line,name", DATASET_CALL_SHAPES)
def test_each_spelling_of_a_dataset_loader_is_extracted(tmp_path, line: int, name: str) -> None:
    """A spelling nothing extracts is a dataset the bill of materials cannot record."""
    assert app_surfaces(tmp_path).get(line) == name


@pytest.mark.parametrize("line,name", DATASET_CALL_SHAPES)
def test_each_spelling_reaches_the_dataset_kind(tmp_path, line: int, name: str) -> None:
    """Being extracted is not enough: the leaf must also match `DATASET_CALLS`."""
    assert app_datasets(tmp_path).get(line) == name

"""The shape `key_document` wraps a draft in: one order, and two independent lists.

Two claims, and neither is cosmetic.

**The entries come back sorted by `(file, line, id)`.** A key is a document a
human reads and corrects, and two drafts of the same app diff cleanly only if
their entries are in the same order both times -- the model's reply order is
whatever it happened to say.

**`expected_surfaces` is what the extractor found, not what the model named.**
The two answer different questions: what is there, and what carries a defect. A
key that conflated them could never say a surface was missed, because every
surface in it would be one the model already called out. So the surfaces here
come from a real `extract_repo` over a tree this file writes, never from a
list handed in beside the entries.

Nothing asserts the *shape* of one expected-surface record: no schema states it,
and a check stricter than the schema is as wrong as a looser one. What is
asserted is the count, and that both languages' files reach the list -- enough
that six empty placeholders could not pass.
"""

import json

from drafted_key_fixtures import APP, COMMIT, ENTRY
from key_drafting import key_document
from mixed_app_fixtures import (
    MIXED_APP_SURFACES, PYTHON_FILE, TYPESCRIPT_FILE, write_mixed_app)
from parsing.extractor import extract_repo

# Four entries in the order a model might name them: the second file first, two
# lines out of order within the first file, and two entries sharing a line.
SCRAMBLED = (
    {"id": "K-04", "file": "web.ts", "line": 3, "owasp_id": "LLM01",
     "title": "t", "description": "d"},
    {"id": "K-02", "file": "agent.py", "line": 7, "owasp_id": "LLM06",
     "title": "t", "description": "d"},
    {"id": "K-01", "file": "agent.py", "line": 7, "owasp_id": "LLM01",
     "title": "t", "description": "d"},
    {"id": "K-03", "file": "agent.py", "line": 2, "owasp_id": "LLM01",
     "title": "t", "description": "d"},
)

# The one order two revisions of a key can be diffed in: file, then line, then id.
IN_ORDER = [("agent.py", 2, "K-03"), ("agent.py", 7, "K-01"),
            ("agent.py", 7, "K-02"), ("web.ts", 3, "K-04")]


def placed(entries: tuple[dict, ...]) -> list[tuple[str, int, str]]:
    """The (file, line, id) of every entry a document holds, in the order it holds them."""
    document = key_document(APP, list(entries), COMMIT)
    return [(entry["file"], entry["line"], entry["id"])
            for entry in document["findings"]]


def scanned(tmp_path) -> list:
    """Every surface the extractor really finds in the mixed-language app."""
    return extract_repo(str(write_mixed_app(tmp_path))).surfaces


# --- the order entries come back in -------------------------------------------

def test_the_entries_are_sorted_by_file_then_line_then_id() -> None:
    """One order per key, so a redraft's diff shows what changed and not what moved."""
    assert placed(SCRAMBLED) == IN_ORDER


def test_the_model_named_them_in_a_different_order() -> None:
    """Guard: the test above would pass over a sort that never ran, on sorted input."""
    given = [(entry["file"], entry["line"], entry["id"]) for entry in SCRAMBLED]
    assert given != IN_ORDER


def test_sorting_neither_drops_an_entry_nor_invents_one() -> None:
    """The count is what every figure scored against the key is out of."""
    document = key_document(APP, list(SCRAMBLED), COMMIT)
    assert document["finding_count"] == len(SCRAMBLED) == 4
    assert len(document["findings"]) == 4


def test_two_entries_on_one_line_are_ordered_by_their_ids() -> None:
    """The third sort key is not decoration: one surface can carry two defects."""
    same_line = (SCRAMBLED[1], SCRAMBLED[2])
    assert [entry[2] for entry in placed(same_line)] == ["K-01", "K-02"]


# --- what the expected surfaces are, and where they come from -----------------

def test_the_expected_surfaces_are_the_extractors_not_the_models(tmp_path) -> None:
    """The whole point: one list says what is there, the other what the model called a defect."""
    document = key_document(APP, [ENTRY], COMMIT, scanned(tmp_path))
    assert document["expected_surface_count"] == MIXED_APP_SURFACES
    assert document["finding_count"] == 1


def test_the_two_counts_could_not_be_confused_for_each_other() -> None:
    """Guard: the test above proves nothing if the app has exactly one surface."""
    assert MIXED_APP_SURFACES != 1


def test_the_expected_surface_count_counts_the_list_beside_it(tmp_path) -> None:
    """A count that disagrees with its list makes every figure computed from it wrong."""
    document = key_document(APP, [ENTRY], COMMIT, scanned(tmp_path))
    assert document["expected_surface_count"] == len(document["expected_surfaces"])


def test_a_key_naming_no_defect_still_records_every_surface(tmp_path) -> None:
    """A model that named nothing has not established that the extractor found nothing."""
    document = key_document(APP, [], COMMIT, scanned(tmp_path))
    assert (document["finding_count"], document["expected_surface_count"]) \
        == (0, MIXED_APP_SURFACES)


def test_both_languages_surfaces_reach_the_list(tmp_path) -> None:
    """Guard: the counts above would hold over records naming nothing at all."""
    document = key_document(APP, [ENTRY], COMMIT, scanned(tmp_path))
    recorded = json.dumps(document["expected_surfaces"])
    assert PYTHON_FILE in recorded
    assert TYPESCRIPT_FILE in recorded


def test_a_document_built_without_a_scan_expects_no_surfaces() -> None:
    """The off position: no scan is an empty list, never a list of the model's entries."""
    document = key_document(APP, [ENTRY], COMMIT)
    assert (document["expected_surfaces"], document["expected_surface_count"]) == ([], 0)

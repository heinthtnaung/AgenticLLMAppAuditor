"""Every field a module reads off a grading-key entry is named by a tuple in `harness.py`.

Split from `test_key_entry_check.py`, which is about the refusals
`_check_entry` produces; nothing here calls it. This file scans source, because
a read added to `scorer.py` or `grading.py` and not to a tuple reaches the
scorer unvalidated and raises exactly the bare `KeyError` that check exists to
prevent. An entry is read under three names -- `entry` in the scorer's
per-entry helpers, `e` in `score_app`'s comprehensions, `key_entry` in
`grading.py` -- so the cover is the union of three scans.

`ENTRY_FIELDS` alone is the wrong target for `grading.py`. Three of its entry
reads sit behind `.get()` truthiness tests, and `subscript_keys` cannot tell a
guarded subscript from a crashable one: it sees `key_entry["llm_surface"]`
though the `.get()` protecting it is on the same line. Held to `ENTRY_FIELDS`
the scan would demand those three of every key and refuse valid ones, so the
union `ENTRY_FIELDS | GUARDED_ENTRY_FIELDS` is what it is held to. The narrower
scorer-only subset stays beside it: that one pins the *crashable* set, which is
what `_check_entry` must require, while the union pins the *known* set.

A second scan holds the second tuple to its own criterion -- subscripted, but
only after a `.get()` test -- by pinning it to the *intersection* of the two
scans of `grading.py`. Without that, padding `GUARDED_ENTRY_FIELDS` with a new
*unguarded* read would silence the cover test, leaving the crashable/guarded
classification a human call the suite cannot check.

**Four limits, stated rather than glossed, the first two being what a reader
hits first.** `get_call_keys` matches a constant key only, so a guard written
as `key_entry.get(field)` -- the field name in a variable -- is invisible to
it, and the field it protects is classified crashable. And the intersection is
an *equality*, so a `.get()` truthiness test added over a field that is
crashable puts that field in the intersection and fails the assertion though
nothing is actually broken. That false alarm is by design and it is loud: the
naive way to quiet it, padding `GUARDED_ENTRY_FIELDS` with the field, fails
`test_no_guarded_field_is_subscripted_by_the_scorer` instead, because the
scorer subscripts that field unguarded. The author has to say which set the
field belongs to rather than get the suite green by widening a tuple.

The other two are quieter. The `.get()` scan proves that a guard and a
subscript live in the same module under the same name, not that the guard
dominates that subscript. And `e` is a generic comprehension alias: bind it in
`scorer.py` to something that is not a key entry and this scan silently starts
demanding that object's fields against `ENTRY_FIELDS`.
"""

from pathlib import Path

from ast_scan import get_call_keys, parse, subscript_keys
from conftest import SRC_DIR
from evaluation.grading import GUARDED_ENTRY_FIELDS
from evaluation.harness import ENTRY_FIELDS

# Both modules that read a key entry, and every name each reads one under.
SCORER_SOURCE = SRC_DIR / "evaluation" / "scorer.py"
GRADING_SOURCE = SRC_DIR / "evaluation" / "grading.py"
ENTRY_VARIABLES = ("entry", "e")
GRADING_VARIABLES = ("key_entry",)
ENTRY_READERS = {SCORER_SOURCE: ENTRY_VARIABLES, GRADING_SOURCE: GRADING_VARIABLES}

# Every field either module is *known* to read off an entry, crashable or
# guarded. The union is what the subscript scan can be held to, because
# `subscript_keys` cannot tell the two apart.
KNOWN_ENTRY_FIELDS = set(ENTRY_FIELDS) | set(GUARDED_ENTRY_FIELDS)

# What each name's scan really returns today: `entry` yields id/file/line/
# owasp_id, `e` yields id/file, `key_entry` yields those four bar `id` plus the
# three guarded ones. Read off the scans, not guessed. A read added to either
# module cannot fail this guard; a scan that stopped seeing one -- which would
# make the subsets below vacuously true -- does.
LEAST_READS_PER_NAME = {"entry": 4, "e": 2, "key_entry": 6}

# Reads planted in a throwaway module, to prove each scan really looks: one
# field no entry has, and one read only behind a `.get()` of the same field.
PLANTED_FIELD = "invented_entry_field"
PLANTED_GUARDED_FIELD = "invented_guarded_field"
PLANTED_SOURCE = f'def read(entry):\n    return entry["{PLANTED_FIELD}"]\n'
PLANTED_GRADING_SOURCE = (
    f'def window(key_entry):\n    return key_entry["{PLANTED_FIELD}"]\n'
)
PLANTED_GUARDED_SOURCE = (
    "def window(key_entry):\n"
    f'    if key_entry.get("{PLANTED_GUARDED_FIELD}"):\n'
    f'        return key_entry["{PLANTED_GUARDED_FIELD}"]\n'
    f'    return key_entry["{PLANTED_FIELD}"]\n'
)


def entry_reads(source: Path, names: tuple[str, ...]) -> set[str]:
    """Every field one module subscripts off an entry, under any of its names."""
    tree = parse(source)
    return set().union(*(subscript_keys(tree, name) for name in names))


def plant(tmp_path: Path, source: str) -> Path:
    """Write one throwaway module holding a planted read, and return its path."""
    path = tmp_path / "planted_reader.py"
    path.write_text(source, encoding="utf-8")
    return path


def test_every_entry_field_the_scorer_reads_is_required_here() -> None:
    """Pins the *crashable* set: an unlisted field reaches the scorer unguarded."""
    read = entry_reads(SCORER_SOURCE, ENTRY_VARIABLES)
    assert read <= set(ENTRY_FIELDS), sorted(read - set(ENTRY_FIELDS))


def test_every_entry_field_either_module_reads_is_named_by_a_tuple() -> None:
    """Pins the *known* set: a read added to either module belongs to neither tuple."""
    for source, names in ENTRY_READERS.items():
        read = entry_reads(source, names)
        assert read <= KNOWN_ENTRY_FIELDS, (source.name, sorted(read - KNOWN_ENTRY_FIELDS))


def test_both_modules_read_an_entry_by_subscript_under_every_name() -> None:
    """Guard: a scan that found nothing would make the two subsets vacuously true."""
    for source, names in ENTRY_READERS.items():
        tree = parse(source)
        for name in names:
            assert len(subscript_keys(tree, name)) >= LEAST_READS_PER_NAME[name]


def test_the_guarded_tuple_is_exactly_what_grading_reads_behind_a_get() -> None:
    """The second tuple's own criterion, so it cannot be padded to silence the cover.

    Padding it with an unguarded read fails here, because that field is
    subscripted and never `.get()`-tested: the author has to write the guard.
    `line_end` is in neither: it is `.get()`-tested and never subscripted, so
    it falls outside the intersection exactly as it falls outside the tuple.
    """
    tree = parse(GRADING_SOURCE)
    guarded = subscript_keys(tree, "key_entry") & get_call_keys(tree, "key_entry")
    assert set(GUARDED_ENTRY_FIELDS) == guarded


def test_no_guarded_field_is_subscripted_by_the_scorer() -> None:
    """A field the scorer reads unguarded is crashable, so it belongs to the other tuple."""
    crashable = entry_reads(SCORER_SOURCE, ENTRY_VARIABLES)
    assert not set(GUARDED_ENTRY_FIELDS) & crashable


def test_the_scan_sees_a_planted_read_of_an_unlisted_entry_field(tmp_path) -> None:
    """Mutation check: a field read off an entry must really be picked up by the scan."""
    planted = plant(tmp_path, PLANTED_SOURCE)
    assert subscript_keys(parse(planted), "entry") == {PLANTED_FIELD}


def test_the_scan_sees_a_planted_read_under_gradings_parameter_name(tmp_path) -> None:
    """Mutation check: the other half of the scan really looks, under the other name."""
    read = entry_reads(plant(tmp_path, PLANTED_GRADING_SOURCE), GRADING_VARIABLES)
    assert read == {PLANTED_FIELD}
    assert not read <= KNOWN_ENTRY_FIELDS


def test_the_get_scan_tells_a_guarded_read_from_an_unguarded_one(tmp_path) -> None:
    """Mutation check on the new scan: it sees the `.get()`-tested field and only it."""
    tree = parse(plant(tmp_path, PLANTED_GUARDED_SOURCE))
    assert get_call_keys(tree, "key_entry") == {PLANTED_GUARDED_FIELD}
    assert subscript_keys(tree, "key_entry") == {PLANTED_GUARDED_FIELD, PLANTED_FIELD}

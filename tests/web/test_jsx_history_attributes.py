"""Every attribute on every element the history components write, as a closed register.

**The terminating move, not another sweep.** Seven rounds of sampling each found
something, the last seven MISSED in the one component this change created. The
rule they produced: *a sampled sweep finds the relations you thought of; a
rendered relation is only closed by enumerating a finite inventory.* Forty-four
attributes across three components is finite.

**The register lives in `history_attribute_register.py`** -- forty-four lines of
data, kept out of here so that neither file does two jobs, the way
`icon_tables.py` and `css_rules.py` are kept apart from their guards.

**It is a register, not a claim.** The exact multiset of
`(element, attribute, value)` the source writes. It does not say any of them is
*right* -- the siblings below do that, one claim at a time -- only that none can
leave, change, or be duplicated away unnoticed. That is the failure mode nothing
else saw: `options={run}` for `options={run.options}` left 5,134 tests green
while every row reported the flags of a record that has none, so a run that sent
source to a third party read as one that did not.

**Multiset, and the word is load-bearing.** The first version compared two
*sets* and their lengths and claimed the length caught "a duplicate moving". It
did not: with `(span, className, "mono")` written twice and
`(span, className, "tag tag--rule")` once, changing one `mono` to the other left
both differences empty and the total unchanged, and all four tests passed.
Today's duplicates are cosmetic; the hole opens into the wire half the moment
two wires share a value. `Counter` is the fix, and the lesson is familiar in a
new place: a claim about *how many* is not held by a check about *which*.

**Nothing may be skipped on the way in.** `OPEN_TAG`'s attribute run must match
end to end, so a tag carrying `{...spread}`, two levels of brace nesting, or a
`{` inside a string inside a value parses as nothing and contributes no triples
-- a new wire landing invisibly. Each file's parsed tags are counted against its
opening angle brackets: 32, 7 and 3 today.

**Scope, exactly.** All three files are read whole -- including
`HistoryTable.jsx`'s "Open every repository" button, which was outside every
guard until this register covered the file rather than one element of it. Its
`className` and `type` are held only here; its `onClick={open.toggleAll}` was
too until `test_jsx_history_fold.py` joined that handler to the
`groups.length > 1` gate around it, because a register of attributes cannot say
*when* an element renders. Its label is children rather than an attribute, so
nothing here reaches it -- recorded in `docs/TODO.md`.

**Changing it** costs one line *plus* the question the failure message asks: is
that attribute pinned by a claim somewhere, or is this register the only thing
holding it? That cost is what makes the register closed rather than indicative.

**Two kinds of entry.** Most are *wires* -- props, handlers, `aria-expanded`,
`disabled` -- each pinned by a named claim in `test_jsx_history_wiring.py`,
`test_jsx_forget_busy.py`, `test_jsx_history_group.py`,
`test_jsx_history_fold.py`, `test_jsx_run_flags.py`, `test_jsx_run_options.py`,
`test_jsx_row_files.py` or `test_jsx_history_columns.py`. The rest are
`className`, `type` and React's `key`, held only here; `key` is a reconciliation
hint rather than a wire, and is registered because it is an attribute, not
because its loss would be silent.

Reads three components as text. No fastapi, no node, no build.
"""

import re
from collections import Counter

from .history_attribute_register import BY_FILE, REGISTERED
from .jsx_sweep import strip_comments

# One open tag, and one attribute inside it. The value pattern allows one level
# of nested braces, which is as deep as any of these go -- and the floor below
# is what keeps that "as deep as" honest.
OPEN_TAG = re.compile(
    r"<([A-Za-z][\w.]*)((?:\s+[\w-]+(?:=(?:\"[^\"]*\"|\{(?:[^{}]|\{[^{}]*\})*\}))?)*)\s*/?>")
ATTRIBUTE = re.compile(r"([\w-]+)(?:=(\"[^\"]*\"|\{(?:[^{}]|\{[^{}]*\})*\}))?")

# An element opening, counted the crudest way there is, so the number cannot be
# wrong in the same direction as the parser.
ANY_TAG = re.compile(r"<[A-Za-z]")

# What a failure has to say, because the right response to it is a judgement and
# not a paste.
ADVICE = ("add or remove the line in this file's register, and then answer the "
          "question it exists to ask: is that attribute pinned by a claim "
          "somewhere, or is this register the only thing holding it?")

# A tag this regex cannot read: a spread defeats the attribute run, so the whole
# element parses as nothing and every wire on it lands invisibly.
A_TAG_THE_PARSER_CANNOT_READ = "<button {...props} onClick={onForget}>x</button>"

# A value written twice beside a sibling written once, and the same markup with
# one of the duplicates turned into that sibling. Nothing enters or leaves the
# set of values, and the count of attributes is unchanged -- which is why only a
# multiset can tell these two apart.
TWO_DUPLICATES_AND_A_SIBLING = (
    '<span className="mono"/><span className="mono"/><span className="tag tag--rule"/>')
ONE_DUPLICATE_SWAPPED_FOR_THE_SIBLING = (
    '<span className="mono"/><span className="tag tag--rule"/><span className="tag tag--rule"/>')


def attributes_in(text: str) -> list[tuple[str, str, str]]:
    """Every (element, attribute, value) one piece of source writes, in order."""
    found: list[tuple[str, str, str]] = []
    for tag, attrs in OPEN_TAG.findall(strip_comments(text)):
        found += [(tag, name, value) for name, value in ATTRIBUTE.findall(attrs.strip())
                  if name]
    return found


def source_of(path) -> str:
    """One component's source with its comments gone."""
    return strip_comments(path.read_text(encoding="utf-8"))


def written() -> Counter:
    """The whole register as the three components actually write it, with multiplicities."""
    return Counter(attribute for path, _ in BY_FILE
                   for attribute in attributes_in(path.read_text(encoding="utf-8")))


def unparsed(text: str) -> int:
    """How many element openings this regex could not read. Anything but zero is a hole."""
    return len(ANY_TAG.findall(text)) - len(OPEN_TAG.findall(text))


# --- the register is the source, exactly and with multiplicity ----------------

def test_nothing_is_written_that_the_register_does_not_name() -> None:
    """An attribute added is a wire nobody has asked the question about yet."""
    extra = sorted((written() - REGISTERED).elements())
    assert extra == [], f"{extra}: {ADVICE}"


def test_nothing_the_register_names_has_left() -> None:
    """The measured class: `options={run}` left 5,134 tests green and every row wrong."""
    gone = sorted((REGISTERED - written()).elements())
    assert gone == [], f"{gone}: {ADVICE}"


def test_the_register_matches_the_source_multiplicity_and_all() -> None:
    """A multiset, not a set: one duplicate becoming another left both differences empty."""
    assert written() == REGISTERED


def test_a_duplicate_turning_into_another_registered_value_is_reported() -> None:
    """Planted over the real parser: the set-plus-length version passed this exact swap."""
    before = Counter(attributes_in(TWO_DUPLICATES_AND_A_SIBLING))
    after = Counter(attributes_in(ONE_DUPLICATE_SWAPPED_FOR_THE_SIBLING))
    # What the old version compared, and why it saw nothing: neither direction of
    # the *set* difference is populated, and the totals are equal.
    assert set(after) - set(before) == set() and set(before) - set(after) == set()
    assert sum(after.values()) == sum(before.values())
    # What a multiset sees.
    assert after != before


# --- and nothing was skipped on the way ---------------------------------------

def test_every_element_opening_was_parsed() -> None:
    """A tag the regex cannot read contributes no triples, so its wires land invisibly."""
    counted = {path.name: unparsed(source_of(path)) for path, _ in BY_FILE}
    unread = {name: short for name, short in counted.items() if short}
    assert unread == {}, f"{unread} element openings could not be parsed: {ADVICE}"


def test_a_tag_the_parser_cannot_read_is_reported_rather_than_skipped() -> None:
    """Planted: injecting exactly this left all four of the old tests green."""
    assert unparsed(A_TAG_THE_PARSER_CANNOT_READ) == 1
    assert attributes_in(A_TAG_THE_PARSER_CANNOT_READ) == []


def test_each_file_contributes_the_share_the_register_allots_it() -> None:
    """Non-vacuity, per file: an unreadable component would make two empty multisets equal."""
    found = {path.name: (len(attributes_in(path.read_text(encoding="utf-8"))), expected)
             for path, expected in BY_FILE}
    short = {name: pair for name, pair in found.items() if pair[0] != pair[1]}
    assert short == {}, f"{short} (found, expected): {ADVICE}"

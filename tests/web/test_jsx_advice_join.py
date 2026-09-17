"""The advice panel finds an entry by joining `remediation.json` to `findings.json`.

`FindingList.jsx` fetches `remediation.json` when a row is opened, keys it by
`entry.finding_id`, then looks each row up by `finding.finding_id`. That is a
join across a language boundary with no compiler and no type across it, and
JavaScript answers `undefined` for a key that is not there -- so a renamed field
on either side produces a page that says "no advice was written for this
finding" about every finding, and nothing throws. On a measured run 9 of 9
findings matched; a broken join would have been 0 of 9, and would have looked
like a run that simply wrote no advice.

**Both halves are derived, not transcribed.** The documents come from their real
producers, so the field is a key of each because the serialisers put it there.
The component's own two spellings are read out of the JSX, because the accessor
sweep cannot see either: the map is built over a variable called `entry`, which
other components bind to something else entirely, and the lookup reads
`finding.finding_id` -- a field, not a record prefix.

What each of the three shapes *carries* is `test_jsx_advice_fields.py`, which
this was split from. What this cannot show: whether React reaches the lookup at
all.

No fastapi and no node: it reads the JSX as text and the records from `src/`.
"""

import re

from artifacts.names import REMEDIATION_NAME
from findings_fixtures import build_document, static_finding
from remediation_fixtures import (
    CLEAN_GUIDANCE, remediation_document, snippet, source, written_entry)

from .jsx_sweep import FRONTEND_SRC

# The key of the remediation document that holds the entries, and the field
# both documents join on. One spelling, asserted to be a key of each.
ADVICE = "advice"
JOIN_FIELD = "finding_id"

# The component that does the join, and the two halves of it as written.
THE_FILE_THAT_JOINS = "FindingList.jsx"
KEYED_BY = re.compile(r"\[\s*entry\.(\w+)\s*,\s*entry\s*\]")
LOOKED_UP_BY = re.compile(r"advice\?\.\[\s*finding\.(\w+)\s*\]")


def a_joined_pair() -> tuple[dict, dict]:
    """One findings document and the remediation document written about it.

    The findings document carries the id and the advice entry reuses it, so the
    join is a real one rather than two literals that happen to match.
    """
    findings = build_document([static_finding()])
    joined_on = findings["findings"][0][JOIN_FIELD]
    advice = remediation_document([written_entry(joined_on, CLEAN_GUIDANCE,
                                                 [snippet()], [source()])])
    return findings, advice


def _component_named(name: str):
    """One JSX file by name, insisting the page still ships it."""
    found = [path for path in sorted(FRONTEND_SRC.rglob("*.jsx")) if path.name == name]
    assert len(found) == 1, f"expected exactly one {name}, found {len(found)}"
    return found[0]


# --- the join -----------------------------------------------------------------

def test_the_field_the_panel_joins_on_is_a_key_of_an_advice_entry() -> None:
    """The map `FindingList` builds is keyed on this; a rename empties it silently."""
    _findings, advice = a_joined_pair()
    assert JOIN_FIELD in advice[ADVICE][0]


def test_the_same_field_is_a_key_of_a_finding() -> None:
    """The other half: the lookup and the key have to be the same spelling."""
    findings, _advice = a_joined_pair()
    assert JOIN_FIELD in findings["findings"][0]


def test_the_two_documents_really_join_on_it() -> None:
    """Non-vacuity: two documents that each carry the field could still carry two values."""
    findings, advice = a_joined_pair()
    keyed = {entry[JOIN_FIELD] for entry in advice[ADVICE]}
    assert {finding[JOIN_FIELD] for finding in findings["findings"]} == keyed


def test_the_component_keys_its_map_on_that_field() -> None:
    """The half the accessor sweep cannot see: the map is built over a bare `entry`."""
    assert _one_match(KEYED_BY) == JOIN_FIELD


def test_the_component_looks_each_row_up_by_the_same_field() -> None:
    """A lookup on a different field is a page that says "no advice" about every finding."""
    assert _one_match(LOOKED_UP_BY) == JOIN_FIELD


def test_the_document_it_fetches_is_the_one_the_tool_writes() -> None:
    """The join is worth nothing if the page reads a file no run produced."""
    text = _component_named(THE_FILE_THAT_JOINS).read_text(encoding="utf-8")
    assert f'"{REMEDIATION_NAME}"' in text


def _one_match(pattern: re.Pattern) -> str:
    """The single field name one join pattern finds in the joining component."""
    text = _component_named(THE_FILE_THAT_JOINS).read_text(encoding="utf-8")
    found = pattern.findall(text)
    assert len(found) == 1, f"expected one {pattern.pattern} in {THE_FILE_THAT_JOINS}, got {found}"
    return found[0]


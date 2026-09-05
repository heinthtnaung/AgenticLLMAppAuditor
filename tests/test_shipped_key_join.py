"""The grading-key fields that can weaken the join without failing anything.

`grading.matches_key` reads `llm_surface`, `surface_name` and `component` off a
key entry behind a `.get()` truthiness test, so a value no produced finding
could ever carry is not an error: the entry quietly matches nothing, the app
scores one lower, and no message says why. Two fields of this project's one
shipped key were written that way before anyone noticed -- `llm_surface` first,
then `component: "pyyaml"`, which is compared against the finding's **purl**.
An undeclared package has no purl by definition, so that one line suppressed
the true match for `DVLA-07`, the supply-chain entry the auditor reaches and
the grep baseline does not. Setting it to `null` restored it.

Two halves, and they are different claims. The first is the mechanism, over an
entry and a finding built here: a value in the wrong spelling joins nothing and
raises nothing, and an empty string widens the join instead of narrowing it.
The second holds the shipped key to what that mechanism implies.

What is deliberately not here: the join rule's own edges, which are
`tests/evaluation/test_grading.py`, and the surface-kind vocabulary, which
`test_shipped_grading_key.py` pins. Repeating either would give the suite two
copies of one rule to disagree over.
"""

from dataclasses import asdict

import pytest

from deps.package_names import PYPI, base_purl
from evaluation.grading import GUARDED_ENTRY_FIELDS, matches_key
from evaluation_fixtures import key_entry
from findings_fixtures import static_finding
from shipped_key_fixtures import shipped_entries

# Every purl starts with this, so a bare package name is not one and can match
# no finding at all. Tied to the tool's own builder by a test below rather than
# asserted as folklore.
PURL_PREFIX = "pkg:"

# The undeclared package `DVLA-07` is about, in the two spellings a key author
# might reach for: the name a human writes, and the purl the join compares.
UNDECLARED_NAME = "pyyaml"
UNDECLARED_PURL = "pkg:pypi/pyyaml@5.3.1"

# An empty string is falsy, so the join skips the field entirely: writing one
# is how an author narrows a key entry and gets the opposite.
EMPTY = ""


def produced(**overrides) -> dict:
    """The produced finding as `findings.json` holds it: a plain dict, not a record."""
    return asdict(static_finding(**overrides))


# --- The mechanism ----------------------------------------------------------

def test_the_purl_prefix_is_the_one_the_tools_own_builder_writes() -> None:
    """Guard: the constant below is the auditor's spelling, not this test's opinion."""
    assert base_purl(UNDECLARED_NAME, PYPI).startswith(PURL_PREFIX)


def test_a_component_named_by_bare_package_name_answers_nothing() -> None:
    """The `DVLA-07` trap: `component` is compared against `purl`, never against a name."""
    finding = produced(purl=UNDECLARED_PURL)
    assert not matches_key(finding, key_entry(component=UNDECLARED_NAME))


def test_the_same_finding_matches_once_the_component_is_spelled_as_a_purl() -> None:
    """Guard: everything else about that entry joins, so the name alone was the failure."""
    finding = produced(purl=UNDECLARED_PURL)
    assert matches_key(finding, key_entry(component=UNDECLARED_PURL))


def test_a_wrong_component_is_a_silent_miss_and_not_an_error() -> None:
    """Nothing raises, nothing is logged: the score simply comes out one lower.

    This is why the shipped key needs a test of its own. A malformed value here
    cannot be caught at score time, because at score time it looks exactly like
    a defect the auditor failed to find.
    """
    assert matches_key(produced(purl=UNDECLARED_PURL),
                       key_entry(component=UNDECLARED_NAME)) is False


@pytest.mark.parametrize("field", GUARDED_ENTRY_FIELDS)
def test_an_empty_string_widens_the_join_instead_of_narrowing_it(field: str) -> None:
    """A falsy value is skipped, so an author who wrote `""` constrained nothing."""
    assert matches_key(produced(), key_entry(**{field: EMPTY}))


# --- What the shipped key may hold ------------------------------------------

def test_there_are_shipped_entries_to_check() -> None:
    """The guard that stops the two loops below passing over an empty folder."""
    assert shipped_entries()


def test_no_shipped_entry_names_a_component_that_is_not_a_purl() -> None:
    """A named component must be spelled as the SBOM writes it, or it answers nothing."""
    for label, entry in shipped_entries():
        component = entry.get("component")
        assert component is None or component.startswith(PURL_PREFIX), f"{label}: {component!r}"


def test_no_shipped_entry_leaves_a_join_field_as_an_empty_string() -> None:
    """`null` says "do not compare this"; `""` says it too, and looks like it does not."""
    for label, entry in shipped_entries():
        empty = [field for field in GUARDED_ENTRY_FIELDS if entry.get(field) == EMPTY]
        assert not empty, f"{label} leaves {empty} empty, which the join ignores"

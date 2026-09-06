"""The grading-key values that weaken the join without failing anything.

`grading.matches_key` reads `llm_surface`, `surface_name` and `component` off a
key entry behind a `.get()` truthiness test, so a value no produced finding
could ever carry is not an error: the entry quietly matches nothing, the app
scores one lower, and no message says why.

It happened twice on the key this project used to ship. `llm_surface` was
written in the wrong spelling first; then `component: "pyyaml"`, which is
compared against the finding's **purl**. An undeclared package has no purl by
definition, so that one line suppressed the true match for the supply-chain
entry the auditor reached and the grep baseline did not. Setting it to `null`
restored it.

That key was removed on 2026-09-06 and the sweep over its entries went with it.
What is left is the mechanism, over an entry and a finding built here: a value
in the wrong spelling joins nothing and raises nothing, and an empty string
widens the join instead of narrowing it. Nothing catches either at score time --
a mis-spelled value looks exactly like a defect the auditor failed to find --
so a key author has to know both, which is what this file is for.

What is deliberately not here: the join rule's own edges, which are
`tests/evaluation/test_grading.py`, and the fields a key must carry, which
`grading_key_rules.py` states and the three `test_promoted_*_shipped_rules.py`
files hold a constructed key to. Repeating either would give the suite two
copies of one rule to disagree over.
"""

import pytest

from deps.package_names import PYPI, base_purl
from evaluation.grading import GUARDED_ENTRY_FIELDS, matches_key
from evaluation_fixtures import key_entry
from findings_fixtures import produced_finding

# Every purl starts with this, so a bare package name is not one and can match
# no finding at all. Tied to the tool's own builder by a test below rather than
# asserted as folklore.
PURL_PREFIX = "pkg:"

# An undeclared package, in the two spellings a key author might reach for: the
# name a human writes, and the purl the join compares.
UNDECLARED_NAME = "pyyaml"
UNDECLARED_PURL = "pkg:pypi/pyyaml@5.3.1"

# An empty string is falsy, so the join skips the field entirely: writing one
# is how an author narrows a key entry and gets the opposite.
EMPTY = ""


def test_the_purl_prefix_is_the_one_the_tools_own_builder_writes() -> None:
    """Guard: the constant below is the auditor's spelling, not this test's opinion."""
    assert base_purl(UNDECLARED_NAME, PYPI).startswith(PURL_PREFIX)


def test_a_component_named_by_bare_package_name_answers_nothing() -> None:
    """The trap: `component` is compared against `purl`, never against a name."""
    finding = produced_finding(purl=UNDECLARED_PURL)
    assert not matches_key(finding, key_entry(component=UNDECLARED_NAME))


def test_the_same_finding_matches_once_the_component_is_spelled_as_a_purl() -> None:
    """Guard: everything else about that entry joins, so the name alone was the failure."""
    finding = produced_finding(purl=UNDECLARED_PURL)
    assert matches_key(finding, key_entry(component=UNDECLARED_PURL))


def test_a_wrong_component_is_a_silent_miss_and_not_an_error() -> None:
    """Nothing raises, nothing is logged: the score simply comes out one lower.

    This is why the rule is stated here rather than left to a scoring run to
    catch. At score time a malformed value looks exactly like a defect the
    auditor failed to find, so no run can tell the two apart.
    """
    assert matches_key(produced_finding(purl=UNDECLARED_PURL),
                       key_entry(component=UNDECLARED_NAME)) is False


@pytest.mark.parametrize("field", GUARDED_ENTRY_FIELDS)
def test_an_empty_string_widens_the_join_instead_of_narrowing_it(field: str) -> None:
    """A falsy value is skipped, so an author who wrote `""` constrained nothing."""
    assert matches_key(produced_finding(), key_entry(**{field: EMPTY}))

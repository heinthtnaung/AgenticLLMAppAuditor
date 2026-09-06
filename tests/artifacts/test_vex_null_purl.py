"""A findings document holding an advisory finding with no purl, turned into statements.

`Finding` accepts a null `purl` whenever some other evidence is cited, so a
document with one is schema-valid; `to_vex_statements` grouped on
`finding["purl"]` and then sorted the keys, which raised
`TypeError: '<' not supported between instances of 'NoneType' and 'str'` --
a traceback out of `emit_vex.py` for a document that was otherwise writable.

Grouping on `finding.get("purl") or ""` removes the crash and **does not make
the statement right**, which is the second half of what is pinned here: the
empty string is not an identifier, so the statement names no subcomponent at
all, the `component_name` the finding did carry is not used instead, and two
different unversioned components under one advisory collapse into one
statement. That is a narrower defect than the crash and it is now a row in
`docs/TODO.md`'s Known defects table rather than a passing assertion pretending
it is fine.

Today's `known_advisory` cannot produce this input -- it skips a mapping entry
with no purl -- so every document here is built by hand, which is also the only
way to build one now that the corpus is gone.
"""

from advisory_fixtures import ADVISORY_ID, ADVISORY_PURL, advisory_document
from artifacts.vex import AFFECTED, advisory_findings, to_vex_statements
from vex_fixtures import reaching

# What a purl-less component is grouped under. Not an identifier: a reader
# cannot resolve it, and vexctl is handed it verbatim.
NO_SUBCOMPONENT = ""

FIRST_COMPONENT = "one-unversioned-lib"
SECOND_COMPONENT = "another-unversioned-lib"


def mixed_document() -> dict:
    """One advisory reaching two components, of which the SBOM versioned only one."""
    return advisory_document(
        reaching("ShellTool", "app/agent.py", 12),
        reaching("SearchTool", "app/tools.py", 40, purl=None,
                 component_name=FIRST_COMPONENT))


def two_unversioned_document() -> dict:
    """One advisory reaching two components, neither of which the SBOM could version."""
    return advisory_document(
        reaching("ShellTool", "app/agent.py", 12, purl=None,
                 component_name=FIRST_COMPONENT),
        reaching("SearchTool", "app/tools.py", 40, purl=None,
                 component_name=SECOND_COMPONENT))


def test_the_document_really_holds_a_finding_with_no_purl() -> None:
    """The guard on every test below: without this they would pass over ordinary input."""
    purls = [finding["purl"] for finding in advisory_findings(mixed_document())]
    assert purls.count(None) == 1
    assert purls.count(ADVISORY_PURL) == 1


def test_a_null_purl_no_longer_raises_when_the_groups_are_sorted() -> None:
    """The defect itself: sorting None against a string ended the emitter in a traceback."""
    statements = to_vex_statements(mixed_document())
    assert len(statements) == 2
    assert {statement["status"] for statement in statements} == {AFFECTED}


def test_the_versioned_component_still_gets_its_own_statement() -> None:
    """The findings the emitter could always state are unaffected by the one it could not."""
    statements = to_vex_statements(mixed_document())
    assert [statement["subcomponent"] for statement in statements] == [
        NO_SUBCOMPONENT, ADVISORY_PURL]
    assert {statement["vulnerability"] for statement in statements} == {ADVISORY_ID}


def test_the_unversioned_component_is_stated_with_no_identifier_at_all() -> None:
    """Recorded as a defect, not endorsed: an empty subcomponent identifies nothing.

    The claim degrades from "this app is affected via this component" to "this
    app is affected", which is weaker than the finding that produced it.
    """
    statement = to_vex_statements(mixed_document())[0]
    assert statement["subcomponent"] == NO_SUBCOMPONENT


def test_the_component_name_the_finding_carried_is_not_used_instead() -> None:
    """No fallback exists: the one human-readable name available is dropped."""
    statement = to_vex_statements(mixed_document())[0]
    assert FIRST_COMPONENT not in statement["subcomponent"]
    assert FIRST_COMPONENT not in statement["status_note"]


def test_two_unversioned_components_collapse_into_one_statement() -> None:
    """The sharpest cost of the empty key: the grouping can no longer tell them apart."""
    statements = to_vex_statements(two_unversioned_document())
    assert len(statements) == 1
    assert statements[0]["subcomponent"] == NO_SUBCOMPONENT


def test_the_collapsed_statement_still_names_both_reaching_surfaces() -> None:
    """What survives the collapse: the evidence, which is where a reader must start."""
    note = to_vex_statements(two_unversioned_document())[0]["status_note"]
    assert note == ("Reached by ShellTool at app/agent.py:12, "
                    "SearchTool at app/tools.py:40")

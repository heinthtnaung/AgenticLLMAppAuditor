"""The typed link from a surface to its component, and the artifact it must not change.

`ComponentRef` was named in the proposal's data model and had never been
written down: the link from a surface to its component was a dict built inline
in `mapping.py`. Naming it is a refactor, so the property that makes it safe is
that **`mapping.json` did not move**: `ComponentRef.as_entry()` produces the
same nine fields, in the same order, and the serialised document is byte for
byte what it was.

**There is no `Component` class to test.** It was written and deleted: nothing
under `src/` constructs one, so its tests were the only callers it ever had and
a class in that position is dead code. Components stay the dicts `sbom.json`
holds; `docs/PROPOSAL_COVERAGE.md` records that half as not delivered.

Both halves are asserted here, and they are not the same claim.
`mapping_to_json` writes with `sort_keys=True`, so the *file* depends only on
the key set -- the insertion order is a property of the dict callers pass
around, and a test that checked only the bytes would let the order rot.

Everything here is built in the test: one surface, one small SBOM, no repository
this project does not own. The deferred import inside `__post_init__` that keeps
`mapping` and this module from closing a circle is
`test_component_ref_imports.py` -- it needs a fresh interpreter, which this file
does not.
"""

import pytest

from artifacts.component_ref import ComponentRef
from artifacts.mapping import (
    MAPPING_REASONS,
    STDLIB,
    THIRD_PARTY,
    UNRESOLVED,
    USED_BUT_UNDECLARED,
    build_mapping,
    mapping_to_json,
)
from artifacts.surface import AGENT_DEF, Surface
from dependency_fixtures import js_sbom
from parsing.languages import PYTHON, TYPESCRIPT

# The nine fields `mapping.json` has always held, in the order it held them.
# Written out rather than read off the dataclass: reading the fields from the
# class would make the test agree with whatever the class says, which is the
# one thing it is here to check.
EXPECTED_ENTRY_KEYS = [
    "surface_id",
    "module",
    "package_root",
    "component_name",
    "ecosystem",
    "purl",
    "component_version_count",
    "reason",
    "resolved_by",
]

# One Python surface importing a package no manifest declares, so the whole
# document below is short enough to pin as text.
SURFACE = Surface(AGENT_DEF, "ChatOpenAI", "app.py", 4, PYTHON, "", "langchain_openai")
EMPTY_SBOM = {"components": []}

# The exact bytes `mapping_to_json` wrote for that surface before `ComponentRef`
# existed. This is the refactor's contract: a reader of the file cannot tell.
EXPECTED_MAPPING_JSON = """{
  "entries": [
    {
      "component_name": "langchain-openai",
      "component_version_count": 0,
      "ecosystem": null,
      "module": "langchain_openai",
      "package_root": "langchain_openai",
      "purl": null,
      "reason": "used_but_undeclared",
      "resolved_by": "normalised_name",
      "surface_id": "app.py:4:AGENT_DEF:ChatOpenAI"
    }
  ],
  "mapped_count": 0,
  "reason_counts": {
    "first_party": 0,
    "stdlib": 0,
    "third_party": 0,
    "unresolved": 0,
    "used_but_undeclared": 1
  },
  "schema_version": 2,
  "surface_count": 1,
  "undeclared_components": [
    "langchain-openai"
  ],
  "unmapped_count": 1
}
"""

# A package the recorded npm bill locks at two versions, which is what makes a
# version-less purl legitimate.
TWO_VERSION_MODULE = "@langchain/openai"
TWO_VERSION_PURL = "pkg:npm/%40langchain/openai"
TWO_VERSION_COUNT = 2


def a_reference(**overrides: object) -> ComponentRef:
    """Build a valid reference, with only the field a test is about replaced."""
    fields = {
        "surface_id": "app.py:4:AGENT_DEF:ChatOpenAI",
        "module": "langchain_openai",
        "package_root": "langchain_openai",
        "component_name": "langchain-openai",
        "ecosystem": "pypi",
        "purl": "pkg:pypi/langchain-openai@0.3.0",
        "component_version_count": 1,
        "reason": THIRD_PARTY,
        "resolved_by": "normalised_name",
    }
    return ComponentRef(**{**fields, **overrides})


# --- The artifact did not move ---------------------------------------------

def test_a_reference_produces_the_nine_mapping_fields_in_order() -> None:
    """`as_entry()` is the mapping entry, so its key order is the file's field order."""
    assert list(a_reference().as_entry()) == EXPECTED_ENTRY_KEYS


def test_a_built_mapping_entry_has_those_same_nine_fields_in_order() -> None:
    """The refactor's target: `mapping._entry` goes through `ComponentRef` now."""
    entry = build_mapping([SURFACE], EMPTY_SBOM)["entries"][0]
    assert list(entry) == EXPECTED_ENTRY_KEYS


def test_the_serialised_mapping_is_byte_for_byte_what_it_was() -> None:
    """One surface, one document, pinned as text: a reader of the file cannot tell."""
    assert mapping_to_json(build_mapping([SURFACE], EMPTY_SBOM)) == EXPECTED_MAPPING_JSON


def test_the_file_is_sorted_so_only_the_key_set_reaches_it() -> None:
    """Why the order test above is separate: `sort_keys=True` hides an order change.

    The written file lists `component_name` first and `surface_id` last, which
    is neither the dataclass's order nor the entry's. So the bytes prove the
    field *set* and nothing about the order, and the order is asserted on the
    dict instead.
    """
    written = EXPECTED_MAPPING_JSON.index('"component_name"')
    assert written < EXPECTED_MAPPING_JSON.index('"surface_id"')
    assert EXPECTED_ENTRY_KEYS.index("surface_id") < EXPECTED_ENTRY_KEYS.index("component_name")


def test_every_mapping_reason_produces_the_same_nine_fields() -> None:
    """A field that appeared only on a joined entry would break a reader of the rest."""
    for reason in MAPPING_REASONS:
        entry = a_reference(reason=reason, purl=None, component_version_count=0).as_entry()
        assert list(entry) == EXPECTED_ENTRY_KEYS, reason


# --- What a reference refuses ----------------------------------------------

def test_a_reason_outside_the_five_is_refused() -> None:
    """A dict could hold any string; the point of the dataclass is that it cannot."""
    with pytest.raises(ValueError, match="unknown mapping reason 'probably_third_party'"):
        a_reference(reason="probably_third_party")


def test_the_refusal_lists_the_reasons_that_are_allowed() -> None:
    """Whoever hits this needs to know which five, not just that theirs is not one."""
    with pytest.raises(ValueError) as raised:
        a_reference(reason="")
    for reason in MAPPING_REASONS:
        assert reason in str(raised.value)


def test_a_reference_with_no_surface_is_refused() -> None:
    """The surface id is the join key: an entry without one belongs to nothing."""
    with pytest.raises(ValueError, match="name the surface it came from"):
        a_reference(surface_id="")


def test_every_reason_the_mapping_uses_is_accepted() -> None:
    """Guards the refusal above: it must reject the unknown, not the whole vocabulary."""
    for reason in (THIRD_PARTY, STDLIB, UNRESOLVED, USED_BUT_UNDECLARED):
        assert a_reference(reason=reason, purl=None,
                           component_version_count=0).as_entry()["reason"] == reason


# --- A purl implies at least one match, not exactly one ---------------------

def test_a_purl_with_no_match_behind_it_is_refused() -> None:
    """A purl is the advisory join key, so one matching nothing would join to nothing."""
    with pytest.raises(ValueError, match="carries a purl but matched no component"):
        a_reference(component_version_count=0)


def test_a_versionless_purl_over_two_matches_is_allowed() -> None:
    """The invariant is "at least one", not "exactly one".

    An earlier draft required exactly one match and was refuted by the
    ambiguous-purl tests: when a lockfile holds several copies, `_join_purl`
    deliberately drops the version rather than naming one by sort order.
    """
    reference = a_reference(purl=TWO_VERSION_PURL, component_version_count=TWO_VERSION_COUNT)
    assert reference.as_entry()["purl"] == TWO_VERSION_PURL


def test_an_entry_with_no_purl_and_no_match_is_allowed() -> None:
    """The normal unjoined entry: most surfaces are builtins or local methods."""
    assert a_reference(purl=None, component_version_count=0).as_entry()["purl"] is None


def test_the_ambiguous_join_the_mapping_really_builds_is_accepted() -> None:
    """The invariant is tied to the code that motivates it, not just asserted about it."""
    surface = Surface(AGENT_DEF, "ChatOpenAI", "src/agent.ts", 3, TYPESCRIPT, "",
                      TWO_VERSION_MODULE)
    entry = build_mapping([surface], js_sbom())["entries"][0]
    assert entry["component_version_count"] == TWO_VERSION_COUNT
    assert entry["purl"] == TWO_VERSION_PURL

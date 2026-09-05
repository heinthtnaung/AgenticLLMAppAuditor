"""The two import-time guards that stop an AIBOM kind having no path to it.

`DATASET` and `MCP_SERVER` are decided by name tables the *detectors* own, so a
name in `DATASET_CALLS` that no data-source detector emits, or one in
`MCP_CLASSES` that no tool detector emits, is a kind that can never occur --
a coverage claim with nothing behind it. `aibom.py` refuses both at import
rather than leaving them to be discovered, which is why they are tested by
re-running the import.

The first draft of `DATASET_CALLS` named methods no detector emitted. These
guards exist because of that, so each is tested in both directions: a name
added to the table that nothing emits, and a detector that stopped emitting a
name the table still holds. Asserting only that they pass as shipped would
prove nothing about the guards themselves.

**Both dataset names are now held by two data-source tables**, since the full
name table and the leaf table match different call shapes. So the second
direction takes both tables away at once: removing one is not a removal, and a
test that expected it to fire was testing the tables rather than the guard.
That asymmetry is asserted below rather than worked around, because "the guard
reads the union of the two tables" is the property that replaced it.

Nothing is mocked. The tables are swapped, the module is re-imported, and they
are put back and re-imported in a `finally` -- so the process is left exactly
as it was found.
"""

import importlib

import pytest

from artifacts import aibom
from detectors import detector_names

# A name no detector emits and no framework publishes, used to violate a guard.
PHANTOM_DATASET_CALL = "slurp_corpus"
PHANTOM_MCP_CLASS = "ImaginaryMCPClient"

# Real names the shipped tables hold, dropped to test the other direction.
DOUBLED_DATASET_CALL = "load_from_disk"
EMITTED_MCP_CLASS = "MCPToolkit"

# A minimal world for the two tests about *how* a name is read: one dataset
# name, and one data-source table holding it in one particular spelling.
ONE_DATASET = frozenset({"load_dataset"})
DOTTED_SPELLING = {"datasets.load_dataset": "dataset loaded by name"}
UNRELATED_SPELLING = {"datasets.load_something_else": "dataset loaded by name"}
LEAF_SPELLING = {"load_dataset": "dataset loaded from disk"}
NO_CALLS: dict[str, str] = {}
NO_METHODS: dict[str, str] = {}


def reload_aibom_with(replacements: dict[str, frozenset | dict]) -> None:
    """Re-run `aibom.py`'s import-time guards with one or more name tables replaced."""
    originals = {name: getattr(detector_names, name) for name in replacements}
    for name, value in replacements.items():
        setattr(detector_names, name, value)
    try:
        importlib.reload(aibom)
    finally:
        for name, value in originals.items():
            setattr(detector_names, name, value)
        importlib.reload(aibom)


def without(table: frozenset | dict, dropped: str) -> frozenset | dict:
    """The same table with one entry removed, keeping a frozenset a frozenset."""
    if isinstance(table, dict):
        return {key: value for key, value in table.items() if key != dropped}
    return frozenset(table) - {dropped}


# --- The guards hold as shipped ---------------------------------------------

def test_the_module_imports_as_shipped() -> None:
    """Guards every refusal below: unviolated, the reload must succeed."""
    importlib.reload(aibom)
    assert aibom.DATASET in aibom.AIBOM_KINDS


def test_every_dataset_call_is_a_name_some_data_source_detector_emits() -> None:
    """The shipped table stated directly, so the guard is not the only thing asserting it."""
    emitted = ({name.split(".")[-1] for name in detector_names.DATA_SOURCE_CALLS}
               | set(detector_names.DATA_SOURCE_METHODS))
    assert detector_names.DATASET_CALLS <= emitted
    assert detector_names.DATASET_CALLS, "an empty table would satisfy the subset test vacuously"


def test_every_mcp_class_is_a_tool_class() -> None:
    """An MCP client is recorded as a tool surface first, so it must be in that table."""
    assert detector_names.MCP_CLASSES <= detector_names.TOOL_CLASSES
    assert detector_names.MCP_CLASSES, "an empty table would satisfy the subset test vacuously"


# --- The dataset guard: a name nothing emits --------------------------------

def test_a_dataset_name_no_detector_emits_is_refused_at_import() -> None:
    """A kind with no path to it is the trap this guard was written for."""
    with pytest.raises(ValueError, match="no data-source detector emits"):
        reload_aibom_with({"DATASET_CALLS":
                           detector_names.DATASET_CALLS | {PHANTOM_DATASET_CALL}})


def test_the_dataset_refusal_names_the_offending_entry() -> None:
    """Whoever added the name reads this, so it says which one has no detector."""
    with pytest.raises(ValueError, match=PHANTOM_DATASET_CALL):
        reload_aibom_with({"DATASET_CALLS":
                           detector_names.DATASET_CALLS | {PHANTOM_DATASET_CALL}})


def test_the_dataset_guard_fires_when_no_table_emits_the_name_any_more() -> None:
    """The other direction: the table stood still and every detector that emitted it moved."""
    with pytest.raises(ValueError, match=DOUBLED_DATASET_CALL):
        reload_aibom_with({
            "DATA_SOURCE_CALLS": without(detector_names.DATA_SOURCE_CALLS,
                                         DOUBLED_DATASET_CALL),
            "DATA_SOURCE_METHODS": without(detector_names.DATA_SOURCE_METHODS,
                                           DOUBLED_DATASET_CALL),
        })


def test_dropping_a_dataset_name_from_one_table_only_leaves_it_emitted() -> None:
    """`load_from_disk` is in both data-source tables, so one removal is not a removal.

    This is the honest form of "the guard reads both tables". It is not a
    weakening: the guard's question is whether *some* detector emits the name,
    and with the leaf table gone the full-name table still does.
    """
    reload_aibom_with({"DATA_SOURCE_METHODS": without(detector_names.DATA_SOURCE_METHODS,
                                                      DOUBLED_DATASET_CALL)})
    assert DOUBLED_DATASET_CALL in detector_names.DATA_SOURCE_METHODS


# --- The dataset guard: how a name is read ----------------------------------

def test_the_guard_reads_the_leaf_of_a_dotted_call_name() -> None:
    """`datasets.load_dataset` emits the leaf `load_dataset`, which is what the table names."""
    reload_aibom_with({"DATASET_CALLS": ONE_DATASET,
                       "DATA_SOURCE_CALLS": DOTTED_SPELLING,
                       "DATA_SOURCE_METHODS": NO_METHODS})
    assert aibom.DATASET in aibom.AIBOM_KINDS


def test_the_guard_fires_when_only_a_different_leaf_is_emitted() -> None:
    """Guards the test above: the leaf really is compared, not merely the dot stripped."""
    with pytest.raises(ValueError, match="load_dataset"):
        reload_aibom_with({"DATASET_CALLS": ONE_DATASET,
                           "DATA_SOURCE_CALLS": UNRELATED_SPELLING,
                           "DATA_SOURCE_METHODS": NO_METHODS})


def test_the_guard_reads_the_method_table_too() -> None:
    """A name emitted only as a leaf on a receiver still has a path to the kind."""
    reload_aibom_with({"DATASET_CALLS": ONE_DATASET,
                       "DATA_SOURCE_CALLS": NO_CALLS,
                       "DATA_SOURCE_METHODS": LEAF_SPELLING})
    assert aibom.DATASET in aibom.AIBOM_KINDS


def test_the_guard_fires_when_neither_table_holds_the_name() -> None:
    """Guards both tests above: with both tables empty there is no path at all."""
    with pytest.raises(ValueError, match="load_dataset"):
        reload_aibom_with({"DATASET_CALLS": ONE_DATASET,
                           "DATA_SOURCE_CALLS": NO_CALLS,
                           "DATA_SOURCE_METHODS": NO_METHODS})


# --- The MCP guard ----------------------------------------------------------

def test_an_mcp_class_that_is_no_tool_class_is_refused_at_import() -> None:
    """A tool surface is what an MCP server is lifted from, so it must be one first."""
    with pytest.raises(ValueError, match="no tool detector emits"):
        reload_aibom_with({"MCP_CLASSES": detector_names.MCP_CLASSES | {PHANTOM_MCP_CLASS}})


def test_the_mcp_refusal_names_the_offending_entry() -> None:
    """Same reason as the dataset one: the message is read by whoever added the name."""
    with pytest.raises(ValueError, match=PHANTOM_MCP_CLASS):
        reload_aibom_with({"MCP_CLASSES": detector_names.MCP_CLASSES | {PHANTOM_MCP_CLASS}})


def test_the_mcp_guard_fires_when_a_tool_class_is_removed() -> None:
    """Dropping `MCPToolkit` from the tool table strands it in `MCP_CLASSES`.

    One table is enough here, unlike the dataset guard above: a tool class is
    named in exactly one place, so a removal really is a removal.
    """
    with pytest.raises(ValueError, match=EMITTED_MCP_CLASS):
        reload_aibom_with({"TOOL_CLASSES": without(detector_names.TOOL_CLASSES,
                                                   EMITTED_MCP_CLASS)})


# --- The process is left as it was found ------------------------------------

def test_the_tables_and_the_module_survive_a_refused_reload() -> None:
    """A guard test that left `aibom` half-imported would poison every test after it."""
    with pytest.raises(ValueError):
        reload_aibom_with({"MCP_CLASSES": detector_names.MCP_CLASSES | {PHANTOM_MCP_CLASS}})
    assert PHANTOM_MCP_CLASS not in detector_names.MCP_CLASSES
    assert aibom.build_aibom([])["component_count"] == 0

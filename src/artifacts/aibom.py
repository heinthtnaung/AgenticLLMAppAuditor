"""Lists the AI-specific parts of an app: its models, tools, agents, datasets and MCP servers.

Derived from the surfaces already extracted rather than by reading the source
again, so every entry can be traced back to the record it came from. An entry
nobody can trace is an entry nobody can check.
"""

import json

from artifacts.surface import AGENT_DEF, DATA_SOURCE, TOOL_CALL, Surface
from detectors.detector_names import (
    DATA_SOURCE_CALLS, DATA_SOURCE_METHODS, DATASET_CALLS, MCP_CLASSES,
    MODEL_CLASSES, TOOL_CLASSES)
from detectors.detector_names_js import MODEL_CLASSES as JS_MODEL_CLASSES
from parsing.languages import PYTHON

SCHEMA_VERSION = 1

MODEL = "MODEL"
TOOL = "TOOL"
AGENT = "AGENT"
# Named in the proposal beside models, tools and agent roles. A dataset is a
# corpus the app pulls in whole; an MCP server is a process it reaches for
# tools it does not define itself. Both are AI components a reader of a bill
# of materials would expect to find, and neither was recorded before.
DATASET = "DATASET"
MCP_SERVER = "MCP_SERVER"
AIBOM_KINDS = (MODEL, TOOL, AGENT, DATASET, MCP_SERVER)

# Both new kinds read a name table the *detectors* own, so a name here that no
# detector emits would be a kind that can never occur -- a coverage claim with
# no path to it. Refused at import rather than left to be discovered.
_EMITTED_LEAVES = {name.split('.')[-1] for name in DATA_SOURCE_CALLS} | set(DATA_SOURCE_METHODS)
if not DATASET_CALLS <= _EMITTED_LEAVES:
    raise ValueError(
        f"DATASET_CALLS names {sorted(DATASET_CALLS - _EMITTED_LEAVES)}, which no "
        "data-source detector emits, so no surface could ever carry the kind")
if not MCP_CLASSES <= TOOL_CLASSES:
    raise ValueError(
        f"MCP_CLASSES names {sorted(MCP_CLASSES - TOOL_CLASSES)}, which no tool "
        "detector emits")

# Where a model's identity came from. `literal` is deliberately absent: no
# surface records a model name yet, so the value could never occur.
UNSTATED = "unstated"
NOT_APPLICABLE = "not_applicable"
MODEL_SOURCES = (UNSTATED, NOT_APPLICABLE)


def _is_model_client(surface: Surface) -> bool:
    """Say whether an agent surface is a model client rather than an agent or graph.

    Decided against the same name tables the detectors use, never by reading
    `detail`, which is documented as descriptive only and free to be reworded.
    The leading segment is enough because the detectors match on the call root.
    """
    classes = MODEL_CLASSES if surface.language == PYTHON else JS_MODEL_CLASSES
    return surface.name.split(".")[0] in classes


def _leaf(name: str) -> str:
    """The last dotted segment of a surface name, which is what the tables match on."""
    return name.split(".")[-1]


def _kind_of(surface: Surface) -> str | None:
    """Return the AIBOM kind a surface belongs to, or None if it is not one."""
    if surface.kind == DATA_SOURCE:
        # Only the loaders: a database query is a data source and not a dataset.
        return DATASET if _leaf(surface.name) in DATASET_CALLS else None
    if surface.kind == TOOL_CALL:
        return MCP_SERVER if surface.name.split(".")[0] in MCP_CLASSES else TOOL
    if surface.kind != AGENT_DEF:
        return None
    return MODEL if _is_model_client(surface) else AGENT


def _component(surface: Surface, kind: str) -> dict:
    """Build one AIBOM entry from the surface it came from."""
    return {
        "kind": kind,
        "name": surface.name,
        "surface_id": surface.id,
        "file": surface.file,
        "line": surface.line,
        "module": surface.module,
        "model_source": UNSTATED if kind == MODEL else NOT_APPLICABLE,
    }


def build_aibom(surfaces: list[Surface]) -> dict:
    """Return the AIBOM: every model, tool and agent the surfaces describe."""
    components = [
        _component(surface, kind)
        for surface in surfaces
        if (kind := _kind_of(surface)) is not None
    ]
    components.sort(key=lambda c: (c["kind"], c["file"], c["line"], c["name"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "component_count": len(components),
        "components": components,
    }


def aibom_to_json(document: dict) -> str:
    """Serialise the AIBOM to its stable on-disk form."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"

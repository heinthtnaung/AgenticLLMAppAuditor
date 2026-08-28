"""Lists the AI-specific parts of an app: its models, tools and agents.

Derived from the surfaces already extracted rather than by reading the source
again, so every entry can be traced back to the record it came from. An entry
nobody can trace is an entry nobody can check.
"""

import json

from artifacts.surface import AGENT_DEF, TOOL_CALL, Surface
from detectors.detector_names import MODEL_CLASSES
from detectors.detector_names_js import MODEL_CLASSES as JS_MODEL_CLASSES
from parsing.languages import PYTHON

SCHEMA_VERSION = 1

MODEL = "MODEL"
TOOL = "TOOL"
AGENT = "AGENT"
AIBOM_KINDS = (MODEL, TOOL, AGENT)

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


def _kind_of(surface: Surface) -> str | None:
    """Return the AIBOM kind a surface belongs to, or None if it is not one."""
    if surface.kind == TOOL_CALL:
        return TOOL
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

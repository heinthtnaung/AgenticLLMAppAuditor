"""Finds supply-chain problems in what Phase 2 already joined.

Reads `mapping.json`, never the source: the mapping already decided which
package a surface came from and why, so re-deriving it here would be a second
answer to a question one module owns.
"""

from artifacts.finding import STATIC, Finding
from artifacts.mapping import UNRESOLVED, USED_BUT_UNDECLARED
from artifacts.surface import Surface

CHECK_NAME = "undeclared_dependency"

# LLM03 in the 2025 OWASP list, where supply chain sits. It was LLM05 before.
OWASP_ID = "LLM03"

TITLE = "Package used but never declared as a direct dependency"


def _finding_for(entry: dict) -> Finding:
    """Build the finding for one surface that reached an undeclared package."""
    return Finding(
        OWASP_ID, CHECK_NAME, TITLE, STATIC,
        surface_id=entry["surface_id"],
        surface_kind=entry["surface_kind"],
        surface_name=entry["surface_name"],
        file=entry["file"],
        line=entry["line"],
        component_name=entry["component_name"],
        mapping_reason=USED_BUT_UNDECLARED,
    )


def find_undeclared_dependencies(mapping_document: dict, surfaces_by_id: dict) -> list[Finding]:
    """Report every surface whose package no manifest declares.

    Nothing in the app governs which version of such a package is installed, and
    it is invisible to an SBOM-driven advisory check. The mapping already
    distinguishes this from `unresolved`, which means the package could not be
    determined at all -- a different fact, and not a finding.
    """
    found = []
    for entry in mapping_document.get("entries", []):
        if entry["reason"] != USED_BUT_UNDECLARED or not entry.get("component_name"):
            continue
        surface = surfaces_by_id.get(entry["surface_id"])
        if surface is None:
            continue
        found.append(_finding_for({**entry, **surface}))
    return found


def unresolved_component_count(mapping_document: dict | None) -> int | None:
    """Count the surfaces whose owning component could not be determined.

    Only the `unresolved` reason: `stdlib` and `first_party` are answers, not
    gaps, and `used_but_undeclared` is already reported as a finding. None
    means there was no mapping at all, which is not the same as none unresolved.
    """
    if mapping_document is None:
        return None
    if "reason_counts" not in mapping_document:
        raise ValueError(
            "mapping document has no reason_counts; it was not built by "
            "artifacts.mapping.build_mapping and cannot be read for coverage")
    return mapping_document["reason_counts"][UNRESOLVED]


def surface_fields(surfaces: list[Surface]) -> dict[str, dict]:
    """Index the fields a finding copies from its surface, by surface id."""
    return {
        surface.id: {
            "surface_kind": surface.kind, "surface_name": surface.name,
            "file": surface.file, "line": surface.line,
        }
        for surface in surfaces
    }



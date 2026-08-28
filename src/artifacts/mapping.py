"""Joins each LLM surface to the dependency it comes from, or says why it cannot.

An unmapped surface is the normal case, not a defect: most surfaces are
builtins or methods on local variables. What matters is that the five outcomes
stay distinct, because "no package exists" and "we could not tell" are
different facts and only one of them is a finding.
"""

import builtins
import json

from artifacts.surface import Surface
from deps.component_match import NOT_RESOLVED, is_stdlib, package_root, resolve

SCHEMA_VERSION = 1

THIRD_PARTY = "third_party"
STDLIB = "stdlib"
FIRST_PARTY = "first_party"
USED_BUT_UNDECLARED = "used_but_undeclared"
UNRESOLVED = "unresolved"
MAPPING_REASONS = (THIRD_PARTY, STDLIB, FIRST_PARTY, USED_BUT_UNDECLARED, UNRESOLVED)

BUILTIN_NAMES = frozenset(dir(builtins))

# Names that resolve to the JavaScript runtime rather than to anything the app
# wrote. Python's builtins list knows nothing about these.
JS_GLOBALS = frozenset({"fetch", "process", "console", "globalThis", "Buffer",
                        "URL", "URLSearchParams", "structuredClone"})

# An import starting with either is a path alias, never a package name.
# Relative imports are not listed: both backends drop them before a surface is
# built, so `./x` never reaches here.
PATH_ALIAS_PREFIXES = ("@/", "/")


def _classify_named(surface: Surface, components: dict, local: frozenset) -> tuple[str, str, str]:
    """Decide the outcome for a surface that records an import."""
    root = package_root(surface.module, surface.language)
    if root.startswith(PATH_ALIAS_PREFIXES):
        # `@/lib/x` is a path alias, and no package can be named that, so it
        # is the app's own code however the resolver reads it.
        return FIRST_PARTY, "", NOT_RESOLVED
    if root in local:
        # Checked before the language runtime: a local module of the same name
        # shadows the stdlib at import time, so the app's own file wins.
        return FIRST_PARTY, "", NOT_RESOLVED
    if is_stdlib(root, surface.language):
        return STDLIB, "", NOT_RESOLVED
    name, how = resolve(surface.module, surface.language)
    if name in components:
        return THIRD_PARTY, name, how
    if name:
        return USED_BUT_UNDECLARED, name, how
    return UNRESOLVED, "", NOT_RESOLVED


def _classify_unnamed(surface: Surface) -> tuple[str, str, str]:
    """Decide the outcome for a surface with no import behind it.

    A dotted name is a call on an object whose type is not known here, like
    `cursor.execute` -- following it needs the dataflow analysis in Phase 3.
    A plain name is either a builtin or something the app defined itself.
    """
    root = surface.name.split(".")[0]
    if root in BUILTIN_NAMES or root in JS_GLOBALS:
        return STDLIB, "", NOT_RESOLVED
    if "." in surface.name:
        return UNRESOLVED, "", NOT_RESOLVED
    return FIRST_PARTY, "", NOT_RESOLVED


def _entry(surface: Surface, components: dict, local: frozenset) -> dict:
    """Build one mapping entry for one surface."""
    if surface.module:
        reason, name, how = _classify_named(surface, components, local)
    else:
        reason, name, how = _classify_unnamed(surface)
    component = components.get(name) if reason == THIRD_PARTY else None
    return {
        "surface_id": surface.id,
        "module": surface.module,
        "package_root": package_root(surface.module, surface.language) or None,
        "component_name": name or None,
        "ecosystem": component["ecosystem"] if component else None,
        "purl": component["purl"] if component else None,
        "reason": reason,
        "resolved_by": how,
    }


def build_mapping(surfaces: list[Surface], sbom_document: dict,
                  local_modules: frozenset = frozenset()) -> dict:
    """Return the mapping: exactly one entry per surface, each with its outcome.

    `local_modules` are the app's own top-level module names. Without them an
    import of the app's own code is indistinguishable from a dependency it
    forgot to declare, which would be a false supply-chain finding.
    """
    components = {c["name"]: c for c in sbom_document.get("components", [])}
    entries = sorted((_entry(s, components, local_modules) for s in surfaces),
                     key=lambda e: e["surface_id"])
    counts = {reason: 0 for reason in MAPPING_REASONS}
    for entry in entries:
        counts[entry["reason"]] += 1
    undeclared = sorted({
        e["component_name"] for e in entries if e["reason"] == USED_BUT_UNDECLARED
    })
    return {
        "schema_version": SCHEMA_VERSION,
        "surface_count": len(entries),
        "mapped_count": counts[THIRD_PARTY],
        "unmapped_count": len(entries) - counts[THIRD_PARTY],
        "reason_counts": counts,
        "undeclared_components": undeclared,
        "entries": entries,
    }


def mapping_to_json(document: dict) -> str:
    """Serialise the mapping to its stable on-disk form."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"

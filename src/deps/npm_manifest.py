"""Reads an npm manifest: what a JavaScript app says it depends on.

A sibling of `requirements_parser`, not an extension of it. npm states its
dependencies as JSON under two keys and pins them in a separate lockfile, which
is a different shape of fact from a requirements file's one line per package.
"""

import json
from pathlib import Path

from deps.package_names import NPM, NPM_LOCKFILES, normalise_name

MANIFEST_NAME = "package.json"

# Both keys are the app's own declarations. devDependencies are audited too: a
# vulnerable build tool is still a supply-chain risk, and it ships in the repo.
DEPENDENCY_KEYS = ("dependencies", "devDependencies")


def has_manifest(app_dir: Path) -> bool:
    """Say whether the app declares npm dependencies."""
    return (app_dir / MANIFEST_NAME).is_file()


def manifests_present(app_dir: Path) -> list[str]:
    """Return the npm manifest and any lockfile that exist, so the SBOM can say what it read."""
    found = [MANIFEST_NAME] if has_manifest(app_dir) else []
    found += [name for name in NPM_LOCKFILES if (app_dir / name).is_file()]
    return found


def read_manifest(app_dir: Path) -> dict[str, str]:
    """Map each declared package to its constraint text, empty when unconstrained.

    Fails loudly on a manifest that is not readable JSON: a JS app whose
    package.json cannot be parsed has no declarations to compare against, and
    reporting every real import as undeclared would invent findings.
    """
    manifest = app_dir / MANIFEST_NAME
    if not manifest.is_file():
        return {}
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"cannot read {MANIFEST_NAME}: {error}") from error
    if not isinstance(document, dict):
        raise ValueError(f"{MANIFEST_NAME} must hold a JSON object, got {type(document).__name__}")
    return _declared_in(document)


def _declared_in(document: dict) -> dict[str, str]:
    """Collect the declarations from every dependency key the manifest uses."""
    declared: dict[str, str] = {}
    for key in DEPENDENCY_KEYS:
        section = document.get(key) or {}
        if not isinstance(section, dict):
            raise ValueError(f"{MANIFEST_NAME}'s {key} must hold a JSON object")
        for name, constraint in section.items():
            declared[normalise_name(name, NPM)] = constraint if isinstance(constraint, str) else ""
    return declared

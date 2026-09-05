"""Shared Phase 2 test data: what the generator really reported, transcribed.

The generator output below is transcribed from Syft runs recorded against the
apps this project once pinned, so every test that uses it runs on a machine
with no Syft installed and no audited tree on disk. The one test that does
invoke Syft lives in test_syft_runner.py and skips when it is missing.

The trees it was recorded from are gone, so nothing here is re-checked against
a real manifest any more: this is fixed data now, not a transcription under
test.
"""

import json

from deps.npm_manifest import MANIFEST_NAME as NPM_MANIFEST
from deps.package_names import NPM, PYPI
from deps.requirements_parser import MANIFEST_NAME as PYPI_MANIFEST
from artifacts.sbom import build_sbom

# The two lockfile names the tests name individually, spelled once here rather
# than in each file. test_sbom_duplicates.py checks package_names still lists
# them, so a rename in the owning module fails a test instead of passing quietly.
POETRY_LOCK = "poetry.lock"
YARN_LOCK = "yarn.lock"

# The smallest package.json a test can write: one declared npm dependency.
# Two CLI test files write it -- one to run the CLI over an npm app, one to ask
# which ecosystem such a repository declares.
TINY_PACKAGE_JSON = json.dumps({"dependencies": {"@langchain/openai": "^0.3.2"}})

GENERATOR_NAME = "syft"
GENERATOR_VERSION = "1.51.0"

# A recorded requirements.txt, as name -> constraint text: five declared
# packages, two of which the generator below never reported.
PYPI_DECLARED = {
    "streamlit": "",
    "langchain": "~=0.3.25",
    "openai": "~=1.78.0",
    "langchain-litellm": "==0.2.0",
    "langchain-community": "",
}

# What Syft really reported for that app: three of the five declared packages,
# plus the manifest itself as a `file` component carrying an absolute path.
PYPI_GENERATOR_OUTPUT = {
    "components": [
        {"type": "library", "name": "langchain", "version": "0.3.25"},
        {"type": "library", "name": "langchain-litellm", "version": "0.2.0"},
        {"type": "library", "name": "openai", "version": "1.78.0"},
        {"type": "file", "name": "/home/someone/app/requirements.txt"},
    ],
}

# Declared in the manifest but never reported by the generator.
DROPPED_BY_THE_TOOL = ("langchain-community", "streamlit")

# How Syft records the file it read a component from. Spelled out as Syft
# writes it rather than built from sbom.py's LOCATION_PREFIX/LOCATION_SUFFIX: a
# fixture derived from the code under test keeps matching after that code
# changes, which is the whole failure mode here. The `0` is the first of
# possibly several locations, and the path is relative to Syft's scan root.
LOCATION_PROPERTY_NAME = "syft:location:0:path"


def located_in(path: str) -> list[dict]:
    """The generator properties saying which file a component was read from."""
    return [{"name": LOCATION_PROPERTY_NAME, "value": path}]


# What the JS sample's components carry: the generator read each of them out of
# the app's yarn.lock.
YARN_LOCK_LOCATION = located_in(f"/{YARN_LOCK}")

# Eight of the 80 library components Syft reported for the JavaScript app these
# fixtures were recorded from, each with the `purl` Syft wrote for it. Between
# them they cover every shape an npm component can take: a scoped name, an
# unscoped one, a name reported at two versions and a name reported at three.
# The other 72 differ from these only in their text.
#
# Each carries the generator's own location evidence, because that -- not the
# presence of yarn.lock in the directory -- is what earns `locked` since
# 2026-09-05. Before that fix `from_lockfile` was one document-wide boolean, so
# these components reached `locked` with no properties at all; a fixture that
# still had none would prove `locked` unreachable rather than prove it right.
JS_GENERATOR_SAMPLE = {
    "components": [
        {"type": "library", "name": "@langchain/community", "version": "0.3.3",
         "purl": "pkg:npm/%40langchain/community@0.3.3",
         "properties": list(YARN_LOCK_LOCATION)},
        {"type": "library", "name": "@langchain/langgraph", "version": "0.2.8",
         "purl": "pkg:npm/%40langchain/langgraph@0.2.8",
         "properties": list(YARN_LOCK_LOCATION)},
        {"type": "library", "name": "@langchain/openai", "version": "0.3.0",
         "purl": "pkg:npm/%40langchain/openai@0.3.0",
         "properties": list(YARN_LOCK_LOCATION)},
        {"type": "library", "name": "@langchain/openai", "version": "0.3.2",
         "purl": "pkg:npm/%40langchain/openai@0.3.2",
         "properties": list(YARN_LOCK_LOCATION)},
        {"type": "library", "name": "zod", "version": "3.23.8",
         "purl": "pkg:npm/zod@3.23.8",
         "properties": list(YARN_LOCK_LOCATION)},
        {"type": "library", "name": "langsmith", "version": "0.1.48",
         "purl": "pkg:npm/langsmith@0.1.48",
         "properties": list(YARN_LOCK_LOCATION)},
        {"type": "library", "name": "langsmith", "version": "0.1.55",
         "purl": "pkg:npm/langsmith@0.1.55",
         "properties": list(YARN_LOCK_LOCATION)},
        {"type": "library", "name": "langsmith", "version": "0.1.61",
         "purl": "pkg:npm/langsmith@0.1.61",
         "properties": list(YARN_LOCK_LOCATION)},
    ],
}

# The first component above, and the PURL spelling of its name. Written out
# rather than derived: asserting an encoding against an encoder call would pass
# even if that call encoded nothing.
SCOPED_NAME = "@langchain/community"
SCOPED_PURL_NAME = "%40langchain/community"

# A recorded package.json, as name -> constraint: nine declared packages, two
# of which the lockfile below never pinned.
JS_DECLARED = {
    "@langchain/community": "^0.3.3",
    "@langchain/core": "^0.3.3",
    "@langchain/langgraph": "^0.2.8",
    "@langchain/openai": "^0.3.2",
    "@tsconfig/recommended": "^1.0.7",
    "langsmith": "^0.1.55",
    "typescript": "^5.5.4",
    "zod": "^3.23.8",
    "zod-to-json-schema": "^3.23.2",
}

# What the JS app ships: one manifest that declares, one lockfile that pins.
JS_MANIFESTS = [NPM_MANIFEST, YARN_LOCK]

# Declared in package.json but absent from yarn.lock, so no version was locked.
JS_NOT_IN_THE_LOCKFILE = ("@tsconfig/recommended", "typescript")


def pypi_sbom() -> dict:
    """Build the recorded Python app's SBOM from the recorded generator output."""
    return build_sbom(
        PYPI_GENERATOR_OUTPUT, PYPI_DECLARED, GENERATOR_NAME,
        GENERATOR_VERSION, [PYPI_MANIFEST],
        version_guessing_enabled=True, ecosystem=PYPI,
    )


def js_sbom() -> dict:
    """Build the recorded JavaScript app's SBOM from the recorded lockfile scan sample."""
    return build_sbom(
        JS_GENERATOR_SAMPLE, JS_DECLARED, GENERATOR_NAME,
        GENERATOR_VERSION, JS_MANIFESTS,
        version_guessing_enabled=True, ecosystem=NPM,
    )


def string_values(value: object) -> list[str]:
    """Return every string anywhere inside a JSON-shaped object."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [found for item in value.values() for found in string_values(item)]
    if isinstance(value, list):
        return [found for item in value for found in string_values(item)]
    return []

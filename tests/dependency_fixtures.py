"""Shared Phase 2 test data: what the generator really reported for the corpus apps.

The generator output below is transcribed from recorded Syft runs, so every
test that uses it runs on a machine with no Syft installed. The one test that
does invoke Syft lives in test_syft_runner.py and skips when it is missing.
"""

import json

from conftest import app_path, require_corpus
from parsing.extractor import extract_repo
from deps.npm_manifest import MANIFEST_NAME as NPM_MANIFEST
from deps.package_names import NPM, PYPI
from deps.requirements_parser import MANIFEST_NAME as PYPI_MANIFEST
from artifacts.sbom import build_sbom
from artifacts.surface import Surface

SUPPORT_AGENT = "vuln-app-1-support-agent"
LANGGRAPHJS_STARTER = "oss-app-langgraphjs-starter"

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

# What corpus/<app>/requirements.txt declares: name -> constraint text.
# test_requirements_parser.py checks the real file still says exactly this.
CORPUS_DECLARED = {
    "streamlit": "",
    "langchain": "~=0.3.25",
    "openai": "~=1.78.0",
    "langchain-litellm": "==0.2.0",
    "langchain-community": "",
}

# What Syft really reported for that app: three of the five declared packages,
# plus the manifest itself as a `file` component carrying an absolute path.
CORPUS_GENERATOR_OUTPUT = {
    "components": [
        {"type": "library", "name": "langchain", "version": "0.3.25"},
        {"type": "library", "name": "langchain-litellm", "version": "0.2.0"},
        {"type": "library", "name": "openai", "version": "1.78.0"},
        {"type": "file", "name": "/home/someone/app/requirements.txt"},
    ],
}

# Declared in the manifest but never reported by the generator.
DROPPED_BY_THE_TOOL = ("langchain-community", "streamlit")

# Eight of the 80 library components Syft reported for the JS corpus app
# (oss-app-langgraphjs-starter), each with the `purl` Syft wrote for it. Between
# them they cover every shape an npm component can take: a scoped name, an
# unscoped one, a name reported at two versions and a name reported at three.
# The other 72 differ from these only in their text.
JS_GENERATOR_SAMPLE = {
    "components": [
        {"type": "library", "name": "@langchain/community", "version": "0.3.3",
         "purl": "pkg:npm/%40langchain/community@0.3.3"},
        {"type": "library", "name": "@langchain/langgraph", "version": "0.2.8",
         "purl": "pkg:npm/%40langchain/langgraph@0.2.8"},
        {"type": "library", "name": "@langchain/openai", "version": "0.3.0",
         "purl": "pkg:npm/%40langchain/openai@0.3.0"},
        {"type": "library", "name": "@langchain/openai", "version": "0.3.2",
         "purl": "pkg:npm/%40langchain/openai@0.3.2"},
        {"type": "library", "name": "zod", "version": "3.23.8",
         "purl": "pkg:npm/zod@3.23.8"},
        {"type": "library", "name": "langsmith", "version": "0.1.48",
         "purl": "pkg:npm/langsmith@0.1.48"},
        {"type": "library", "name": "langsmith", "version": "0.1.55",
         "purl": "pkg:npm/langsmith@0.1.55"},
        {"type": "library", "name": "langsmith", "version": "0.1.61",
         "purl": "pkg:npm/langsmith@0.1.61"},
    ],
}

# The first component above, and the PURL spelling of its name. Written out
# rather than derived: asserting an encoding against an encoder call would pass
# even if that call encoded nothing.
SCOPED_NAME = "@langchain/community"
SCOPED_PURL_NAME = "%40langchain/community"

# What corpus/oss-app-langgraphjs-starter/package.json declares: name -> constraint.
# test_npm_manifest.py checks the real file still says exactly this.
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


def corpus_sbom() -> dict:
    """Build the corpus app's SBOM from the recorded generator output."""
    return build_sbom(
        CORPUS_GENERATOR_OUTPUT, CORPUS_DECLARED, GENERATOR_NAME,
        GENERATOR_VERSION, [PYPI_MANIFEST],
        version_guessing_enabled=True, ecosystem=PYPI,
    )


def js_sbom() -> dict:
    """Build the JS corpus app's SBOM from the recorded sample of its lockfile scan."""
    return build_sbom(
        JS_GENERATOR_SAMPLE, JS_DECLARED, GENERATOR_NAME,
        GENERATOR_VERSION, JS_MANIFESTS,
        version_guessing_enabled=True, ecosystem=NPM,
    )


def js_surfaces() -> list[Surface]:
    """Extract the JS corpus app's surfaces, skipping when it is not downloaded."""
    require_corpus(LANGGRAPHJS_STARTER)
    return extract_repo(str(app_path(LANGGRAPHJS_STARTER))).surfaces


def corpus_surfaces() -> list[Surface]:
    """Extract the corpus app's surfaces, skipping when it is not downloaded."""
    require_corpus(SUPPORT_AGENT)
    return extract_repo(str(app_path(SUPPORT_AGENT))).surfaces


def string_values(value: object) -> list[str]:
    """Return every string anywhere inside a JSON-shaped object."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [found for item in value.values() for found in string_values(item)]
    if isinstance(value, list):
        return [found for item in value for found in string_values(item)]
    return []

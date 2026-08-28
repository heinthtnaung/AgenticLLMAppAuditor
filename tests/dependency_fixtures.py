"""Shared Phase 2 test data: what the generator really reported for the corpus app.

The generator output below is transcribed from a recorded Syft run, so every
test that uses it runs on a machine with no Syft installed. The one test that
does invoke Syft lives in test_syft_runner.py and skips when it is missing.
"""

from conftest import app_path, require_corpus
from parsing.extractor import extract_repo
from deps.requirements_parser import MANIFEST_NAME
from artifacts.sbom import build_sbom
from artifacts.surface import Surface

SUPPORT_AGENT = "vuln-app-1-support-agent"

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


def corpus_sbom() -> dict:
    """Build the corpus app's SBOM from the recorded generator output."""
    return build_sbom(
        CORPUS_GENERATOR_OUTPUT, CORPUS_DECLARED, GENERATOR_NAME,
        GENERATOR_VERSION, [MANIFEST_NAME], True,
    )


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

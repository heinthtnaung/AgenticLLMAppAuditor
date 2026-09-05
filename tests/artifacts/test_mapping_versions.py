"""Which installed copy a surface joins to, when the lockfile holds several.

A surface's import cannot say which copy it loads: that needs the lockfile's
resolution tree and semver satisfaction, which this project does not do. So an
ambiguous join drops the version from the purl rather than picking one by sort
order -- a guess in the advisory key is the failure `version_source` exists to
stop, reached by another route.
"""

from artifacts.mapping import FIRST_PARTY, THIRD_PARTY, USED_BUT_UNDECLARED, build_mapping
from artifacts.sbom import build_sbom
from artifacts.surface import AGENT_DEF, DATA_SOURCE, Surface
from dependency_fixtures import (
    GENERATOR_NAME,
    GENERATOR_VERSION,
    NPM_MANIFEST,
    POETRY_LOCK,
    PYPI_MANIFEST,
    YARN_LOCK,
    pypi_sbom,
    js_sbom,
)
from deps.package_names import NPM, PYPI
from parsing.languages import PYTHON, TYPESCRIPT
from surface_fixtures import JS_SURFACES, LOCAL_MODULES, PYTHON_SURFACES

# The three join shapes the recorded npm bill holds.
ONE_VERSION_MODULE = "@langchain/langgraph"
TWO_VERSION_MODULE = "@langchain/openai"
THREE_VERSION_MODULE = "langsmith"

# Measured on `JS_SURFACES`: three declared npm imports and one prompt string
# the app wrote itself.
EXPECTED_JS_THIRD_PARTY = 3
EXPECTED_JS_FIRST_PARTY = 1

# A name that exists in both ecosystems, used to show a cross-ecosystem miss.
SHARED_NAME = "langsmith"


def js_entry_for(module: str) -> dict:
    """Map a single TypeScript agent surface against a recorded npm SBOM."""
    surface = Surface(AGENT_DEF, "Thing", "src/agent.ts", 3, TYPESCRIPT, "", module)
    return build_mapping([surface], js_sbom())["entries"][0]


def one_package_sbom(ecosystem: str) -> dict:
    """Build an SBOM holding a single locked package named `langsmith`."""
    generator_output = {"components": [
        {"type": "library", "name": SHARED_NAME, "version": "0.1.61"},
    ]}
    if ecosystem == PYPI:
        manifests = [PYPI_MANIFEST, POETRY_LOCK]
    else:
        manifests = [NPM_MANIFEST, YARN_LOCK]
    return build_sbom(generator_output, {SHARED_NAME: ""}, GENERATOR_NAME,
                      GENERATOR_VERSION, manifests,
                      version_guessing_enabled=True, ecosystem=ecosystem)


def entry_against(sbom_ecosystem: str, language: str) -> dict:
    """Map one surface in `language` against an SBOM built for `sbom_ecosystem`."""
    surface = Surface(DATA_SOURCE, "Client", "app.ts", 4, language, "", SHARED_NAME)
    return build_mapping([surface], one_package_sbom(sbom_ecosystem))["entries"][0]


def test_one_installed_version_keeps_it_in_the_join_purl() -> None:
    """@langchain/langgraph is locked once, so the advisory key may state the version."""
    entry = js_entry_for(ONE_VERSION_MODULE)
    assert entry["component_version_count"] == 1
    assert entry["purl"] == "pkg:npm/%40langchain/langgraph@0.2.8"


def test_two_installed_versions_drop_the_version_from_the_join_purl() -> None:
    """@langchain/openai is locked at 0.3.0 and 0.3.2; naming either would be a guess."""
    entry = js_entry_for(TWO_VERSION_MODULE)
    assert entry["component_version_count"] == 2
    assert entry["purl"] == "pkg:npm/%40langchain/openai"


def test_three_installed_versions_drop_the_version_too() -> None:
    """The rule is "more than one", not "exactly two"."""
    entry = js_entry_for(THREE_VERSION_MODULE)
    assert entry["component_version_count"] == 3
    assert entry["purl"] == "pkg:npm/langsmith"


def test_the_ambiguous_purl_still_names_the_package() -> None:
    """Dropping the version must not drop the join: the package is still identified."""
    entry = js_entry_for(TWO_VERSION_MODULE)
    assert entry["reason"] == THIRD_PARTY
    assert entry["component_name"] == TWO_VERSION_MODULE


def test_an_unmapped_surface_counts_no_component_versions() -> None:
    """Nothing was joined, so the count is 0 rather than absent or null."""
    surface = Surface(AGENT_DEF, "helper", "src/agent.ts", 3, TYPESCRIPT, "", "")
    entry = build_mapping([surface], js_sbom())["entries"][0]
    assert entry["component_version_count"] == 0
    assert entry["purl"] is None


def test_every_entry_states_a_component_version_count() -> None:
    """The field is required, so a reader can always tell an ambiguous join from a sure one."""
    entries = build_mapping(PYTHON_SURFACES, pypi_sbom(), LOCAL_MODULES)["entries"]
    assert entries
    for entry in entries:
        assert isinstance(entry["component_version_count"], int), entry


def test_no_entry_against_a_singly_locked_bill_is_ambiguous() -> None:
    """The recorded PyPI bill locks one copy of everything, so no join can be ambiguous."""
    counts = [e["component_version_count"]
              for e in build_mapping(PYTHON_SURFACES, pypi_sbom(), LOCAL_MODULES)["entries"]]
    assert max(counts) == 1


def test_a_pypi_component_does_not_join_a_typescript_surface() -> None:
    """Synthetic: a PyPI and an npm package can share a name and be unrelated software."""
    entry = entry_against(PYPI, TYPESCRIPT)
    assert entry["reason"] == USED_BUT_UNDECLARED
    assert entry["purl"] is None


def test_an_npm_component_does_not_join_a_python_surface() -> None:
    """The mirror image, so the check is a matching ecosystem and not a preferred one."""
    entry = entry_against(NPM, PYTHON)
    assert entry["reason"] == USED_BUT_UNDECLARED
    assert entry["purl"] is None


def test_the_same_name_joins_when_the_ecosystems_agree() -> None:
    """Guards the two above: the name really does match, only the ecosystem differed."""
    assert entry_against(NPM, TYPESCRIPT)["reason"] == THIRD_PARTY
    assert entry_against(PYPI, PYTHON)["reason"] == THIRD_PARTY


def test_a_joined_entry_records_the_ecosystem_it_joined_in() -> None:
    """The entry shows the working, so a cross-ecosystem join could not hide."""
    assert entry_against(NPM, TYPESCRIPT)["ecosystem"] == NPM
    assert entry_against(PYPI, PYTHON)["ecosystem"] == PYPI


def js_mapping() -> dict:
    """Map the written TypeScript surfaces against the recorded npm SBOM."""
    return build_mapping(JS_SURFACES, js_sbom())


def test_three_of_the_four_js_surfaces_join_a_declared_package() -> None:
    """Three come from declared npm packages; the prompt string comes from the app itself."""
    counts = js_mapping()["reason_counts"]
    assert counts[THIRD_PARTY] == EXPECTED_JS_THIRD_PARTY
    assert counts[FIRST_PARTY] == EXPECTED_JS_FIRST_PARTY


def test_the_chat_model_surface_gets_the_ambiguous_purl_in_a_whole_document() -> None:
    """Two copies of @langchain/openai are locked, so the whole mapping drops the version too."""
    entry = next(e for e in js_mapping()["entries"]
                 if e["surface_id"] == "src/agent.ts:20:AGENT_DEF:ChatOpenAI")
    assert entry["component_version_count"] == 2
    assert entry["purl"] == "pkg:npm/%40langchain/openai"


def test_the_graph_surface_keeps_its_version_in_a_whole_document() -> None:
    """@langchain/langgraph is locked once, so this entry may still state the version."""
    entry = next(e for e in js_mapping()["entries"]
                 if e["surface_id"] == "src/agent.ts:51:AGENT_DEF:StateGraph")
    assert entry["component_version_count"] == 1
    assert entry["purl"] == "pkg:npm/%40langchain/langgraph@0.2.8"

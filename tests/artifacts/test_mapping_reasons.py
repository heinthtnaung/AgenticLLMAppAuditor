"""The five mapping outcomes, one at a time.

They must stay distinct: "no package exists for this" and "we could not tell"
are different facts, and only one of them is a supply-chain finding.
"""

from artifacts.mapping import (
    FIRST_PARTY,
    STDLIB,
    THIRD_PARTY,
    UNRESOLVED,
    USED_BUT_UNDECLARED,
    build_mapping,
)
from artifacts.surface import AGENT_DEF, DATA_SOURCE, Surface
from conftest import CORPUS_DIR
from dependency_fixtures import SUPPORT_AGENT, corpus_sbom, corpus_surfaces
from deps.component_match import BY_ALIAS_TABLE, BY_NORMALISED_NAME, NOT_RESOLVED
from parsing.languages import PYTHON
from parsing.repo_loader import local_module_names

def corpus_local_modules() -> frozenset:
    """The corpus app's own top-level module names, read from the app itself."""
    return local_module_names(str(CORPUS_DIR / SUPPORT_AGENT))


def entry_for(name: str, module: str, local: frozenset = frozenset()) -> dict:
    """Map a single Python data-source surface and return its one entry."""
    surface = Surface(DATA_SOURCE, name, "app.py", 7, PYTHON, "", module)
    return build_mapping([surface], corpus_sbom(), local)["entries"][0]


def corpus_entry(surface_id: str) -> dict:
    """Return the corpus app's mapping entry for one surface id."""
    mapping = build_mapping(corpus_surfaces(), corpus_sbom(), corpus_local_modules())
    return next(e for e in mapping["entries"] if e["surface_id"] == surface_id)


def test_third_party_names_the_declared_package_and_its_purl() -> None:
    """An import of a declared dependency is mapped, with the package's purl."""
    entry = entry_for("ChatLiteLLM", "langchain_litellm")
    assert entry["reason"] == THIRD_PARTY
    assert entry["component_name"] == "langchain-litellm"
    assert entry["purl"] == "pkg:pypi/langchain-litellm@0.2.0"
    assert entry["resolved_by"] == BY_NORMALISED_NAME


def test_stdlib_names_no_package_at_all() -> None:
    """`os` ships with Python, so there is nothing to join and nothing missing."""
    entry = entry_for("os.getenv", "os")
    assert entry["reason"] == STDLIB
    assert entry["component_name"] is None
    assert entry["purl"] is None


def test_first_party_names_no_package_at_all() -> None:
    """The app's own module is not a dependency, so no component is named."""
    entry = entry_for("read_config", "utils", corpus_local_modules())
    assert entry["reason"] == FIRST_PARTY
    assert entry["component_name"] is None
    assert entry["purl"] is None


def test_used_but_undeclared_names_the_package_but_gives_no_purl() -> None:
    """The finding: a real package, resolved by name, that the SBOM never listed."""
    entry = entry_for("yaml.load", "yaml")
    assert entry["reason"] == USED_BUT_UNDECLARED
    assert entry["component_name"] == "pyyaml"
    assert entry["resolved_by"] == BY_ALIAS_TABLE
    assert entry["purl"] is None


def test_unresolved_says_it_could_not_tell() -> None:
    """A method on an unknown object is honestly unresolved, not a missing package."""
    entry = entry_for("cursor.execute", "")
    assert entry["reason"] == UNRESOLVED
    assert entry["component_name"] is None
    assert entry["resolved_by"] == NOT_RESOLVED


def test_the_package_root_is_recorded_for_an_imported_surface() -> None:
    """The entry shows the working: which top-level module the decision was made on."""
    assert entry_for("ChatOpenAI", "langchain.chat_models")["package_root"] == "langchain"


def test_a_surface_with_no_module_records_no_package_root() -> None:
    """Nothing was imported, so there is no root to report."""
    assert entry_for("cursor.execute", "")["package_root"] is None


def test_the_corpus_model_client_maps_to_langchain_litellm() -> None:
    """main.py:63 builds ChatLiteLLM, which comes from the pinned langchain-litellm."""
    entry = corpus_entry("main.py:63:AGENT_DEF:ChatLiteLLM")
    assert entry["reason"] == THIRD_PARTY
    assert entry["purl"] == "pkg:pypi/langchain-litellm@0.2.0"


def test_the_corpus_yaml_load_is_the_undeclared_finding() -> None:
    """utils.py:75 calls yaml.load, and PyYAML appears in no manifest."""
    entry = corpus_entry("utils.py:75:DATA_SOURCE:yaml.load")
    assert entry["reason"] == USED_BUT_UNDECLARED
    assert entry["component_name"] == "pyyaml"


def test_the_corpus_getenv_is_stdlib() -> None:
    """utils.py:79 calls os.getenv, which no package ships."""
    assert corpus_entry("utils.py:79:DATA_SOURCE:os.getenv")["reason"] == STDLIB


def test_an_agent_surface_maps_the_same_way_as_a_data_source() -> None:
    """The outcome depends on the import, not on which detector found the surface."""
    surface = Surface(AGENT_DEF, "AgentExecutor.from_agent_and_tools", "app.py", 9,
                      PYTHON, "", "langchain.agents")
    entry = build_mapping([surface], corpus_sbom())["entries"][0]
    assert entry["reason"] == THIRD_PARTY
    assert entry["component_name"] == "langchain"

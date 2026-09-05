"""The five mapping outcomes, one at a time.

They must stay distinct: "no package exists for this" and "we could not tell"
are different facts, and only one of them is a supply-chain finding.

Every surface here is written by the test rather than extracted from a pinned
app, so each outcome is reached by exactly one named import and nothing else --
at the cost of never meeting an import shape its author did not think of.
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
from dependency_fixtures import pypi_sbom
from deps.component_match import BY_ALIAS_TABLE, BY_NORMALISED_NAME, NOT_RESOLVED
from parsing.languages import PYTHON

# The audited app's own top-level module, which is what makes `utils` first-party.
LOCAL_MODULES = frozenset({"utils"})


def entry_for(name: str, module: str, local: frozenset = frozenset()) -> dict:
    """Map a single Python data-source surface and return its one entry."""
    surface = Surface(DATA_SOURCE, name, "app.py", 7, PYTHON, "", module)
    return build_mapping([surface], pypi_sbom(), local)["entries"][0]


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
    entry = entry_for("read_config", "utils", LOCAL_MODULES)
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


def test_a_local_module_shadows_a_package_of_the_same_name() -> None:
    """A first-party module wins over a package: that is what import really does."""
    assert entry_for("load", "yaml", frozenset({"yaml"}))["reason"] == FIRST_PARTY


def test_an_agent_surface_maps_the_same_way_as_a_data_source() -> None:
    """The outcome depends on the import, not on which detector found the surface."""
    surface = Surface(AGENT_DEF, "AgentExecutor.from_agent_and_tools", "app.py", 9,
                      PYTHON, "", "langchain.agents")
    entry = build_mapping([surface], pypi_sbom())["entries"][0]
    assert entry["reason"] == THIRD_PARTY
    assert entry["component_name"] == "langchain"

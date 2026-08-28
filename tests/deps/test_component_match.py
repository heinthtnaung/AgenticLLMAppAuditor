"""Turning an import name into the distribution that ships it.

`import yaml` comes from PyYAML, and getting that wrong produces a mapping that
looks complete and is not.
"""

from deps.component_match import (
    BY_ALIAS_TABLE,
    BY_NORMALISED_NAME,
    NOT_RESOLVED,
    is_stdlib,
    package_root,
    resolve,
)
from parsing.languages import JAVASCRIPT, PYTHON, TYPESCRIPT


def test_package_root_of_a_dotted_python_module() -> None:
    """A Python submodule belongs to its top-level package."""
    assert package_root("langchain.agents.loading", PYTHON) == "langchain"


def test_package_root_of_a_scoped_npm_module() -> None:
    """A scoped npm package is two segments, not one: `@scope/name`."""
    assert package_root("@langchain/langgraph/prebuilt", TYPESCRIPT) == "@langchain/langgraph"


def test_package_root_of_a_plain_npm_module() -> None:
    """An unscoped npm deep import belongs to its first segment."""
    assert package_root("express/lib/router", JAVASCRIPT) == "express"


def test_package_root_of_no_module() -> None:
    """A surface with no import behind it has no package root."""
    assert package_root("", PYTHON) == ""


def test_resolves_an_aliased_import() -> None:
    """`yaml` is shipped by PyYAML, and the alias table is what says so."""
    assert resolve("yaml", PYTHON) == ("pyyaml", BY_ALIAS_TABLE)


def test_resolves_a_submodule_to_its_distribution() -> None:
    """`langchain.agents` is the langchain distribution."""
    assert resolve("langchain.agents", PYTHON) == ("langchain", BY_NORMALISED_NAME)


def test_resolves_an_underscored_import_to_its_hyphenated_distribution() -> None:
    """`langchain_litellm` imports what `langchain-litellm` installs."""
    assert resolve("langchain_litellm", PYTHON) == ("langchain-litellm", BY_NORMALISED_NAME)


def test_resolves_a_scoped_npm_deep_import() -> None:
    """A TypeScript deep import resolves to the scoped package, not the subpath."""
    assert resolve("@langchain/langgraph/prebuilt", TYPESCRIPT) == (
        "@langchain/langgraph", BY_NORMALISED_NAME,
    )


def test_resolves_a_plain_npm_deep_import() -> None:
    """`express/lib/x` resolves to express."""
    assert resolve("express/lib/x", JAVASCRIPT) == ("express", BY_NORMALISED_NAME)


def test_resolving_nothing_says_so_rather_than_guessing() -> None:
    """An empty module resolves to no name, and records that it resolved nothing."""
    assert resolve("", PYTHON) == ("", NOT_RESOLVED)


def test_package_root_strips_the_node_prefix() -> None:
    """`node:fs/promises` is the `fs` builtin written the explicit way."""
    assert package_root("node:fs/promises", TYPESCRIPT) == "fs"


def test_stdlib_module_is_recognised() -> None:
    """`os` ships with the runtime, so no distribution exists for it."""
    assert is_stdlib("os", PYTHON) is True


def test_pyyaml_import_is_not_stdlib() -> None:
    """`yaml` is PyYAML, a third-party package, and must never read as stdlib.

    Calling it stdlib would silently drop a real dependency from the mapping.
    """
    assert is_stdlib("yaml", PYTHON) is False


def test_empty_root_is_not_stdlib() -> None:
    """No module name is not the same as a runtime module."""
    assert is_stdlib("", PYTHON) is False


def test_node_builtin_is_stdlib_in_typescript() -> None:
    """`fs` is part of the Node runtime, so no package could be missing for it."""
    assert is_stdlib("fs", TYPESCRIPT) is True


def test_node_builtin_is_not_stdlib_in_python() -> None:
    """`fs` means nothing to Python, so the answer depends on the language asked about.

    Asking Python's list about Node builtins is what turned every `fs` import
    into a package the app had supposedly failed to declare.
    """
    assert is_stdlib("fs", PYTHON) is False

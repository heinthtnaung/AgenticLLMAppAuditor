"""Guards on the installed command: it resolves, and it installs nothing else."""

import importlib
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    # Python 3.10 has no tomllib, and pytest depends on tomli there: the same
    # parser under its older name, so the suite keeps the README's 3.10 claim.
    import tomli as tomllib

from cli.arguments import PROGRAM

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
COMMENT = "#"


def declared_project() -> dict:
    """Read the `[project]` table the installer builds the command from."""
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)["project"]


def resolved(target: str) -> object:
    """Import what a `module:attribute` script target names, as the installed wrapper does."""
    module_name, _, attribute = target.partition(":")
    return getattr(importlib.import_module(module_name), attribute)


def pinned_requirements() -> list[str]:
    """Give the requirement lines of requirements.txt, without its comments."""
    lines = REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith(COMMENT)]


def test_every_declared_command_resolves_to_a_callable():
    # Renaming `cli.main.main` would otherwise pass the suite and break only the
    # installed command, the first time somebody typed it.
    scripts = declared_project()["scripts"]
    assert scripts
    assert all(callable(resolved(target)) for target in scripts.values())


def test_the_command_is_installed_under_the_name_its_help_prints():
    assert list(declared_project()["scripts"]) == [PROGRAM]


def test_the_runtime_depends_on_nothing_outside_the_standard_library():
    assert declared_project()["dependencies"] == []


def test_the_development_extra_pins_what_requirements_pins():
    assert declared_project()["optional-dependencies"]["dev"] == pinned_requirements()

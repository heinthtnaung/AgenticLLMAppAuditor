"""Guards on the installed command: it resolves and installs nothing else, and ships its assets.

The report reads its stylesheet and script from `report/assets/` at render time;
an install without the package-data entry has no assets folder, so `report.css`
raises FileNotFoundError and the tool exits. So the shipped list is held to the
files that actually exist, alongside the guards on the command itself.
"""

import importlib
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    # Python 3.10 has no tomllib, and pytest depends on tomli there: the same
    # parser under its older name, so the suite keeps the 3.10 minimum that
    # `README.md` and `docs/SETUP.md` state.
    import tomli as tomllib

from cli.arguments import PROGRAM

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
ASSETS = PROJECT_ROOT / "src" / "report" / "assets"
COMMENT = "#"


def declared_project() -> dict:
    """Read the `[project]` table the installer builds the command from."""
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)["project"]


def declared_package_data() -> list[str]:
    """Read the report package's shipped data files from pyproject.toml."""
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)["tool"]["setuptools"]["package-data"]["report"]


def declared_ruff() -> dict:
    """Read the `[tool.ruff]` table that turns on import order and names the source roots."""
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)["tool"]["ruff"]


def assets_on_disk() -> set[str]:
    """Give every asset file under src/report/assets, as pyproject names it."""
    return {f"assets/{one.name}" for one in ASSETS.iterdir() if one.is_file()}


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


def test_every_asset_on_disk_is_shipped_and_nothing_is_shipped_that_is_missing():
    assert set(declared_package_data()) == assets_on_disk()


def test_the_shipped_list_names_each_file_once():
    shipped = declared_package_data()
    assert len(shipped) == len(set(shipped))


def test_the_lint_config_enforces_import_order():
    # I is isort; without it `ruff check` passes a mis-ordered import.
    assert "I" in declared_ruff()["lint"]["extend-select"]


def test_the_sort_settings_keep_sorted_files_short():
    # Without both, a re-sort wraps to one name per line and pushes files past 200.
    ruff = declared_ruff()
    assert ruff["line-length"] == 100
    assert ruff["lint"]["isort"]["split-on-trailing-comma"] is False


def test_the_source_roots_make_the_test_helpers_first_party():
    # So report_samples and its siblings group with cli and report, not third-party.
    roots = set(declared_ruff()["src"])
    assert "src" in roots
    assert {"tests/report", "tests/cli", "measurements"} <= roots

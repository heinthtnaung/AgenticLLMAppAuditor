"""Reading package.json: what a JavaScript app claims to depend on.

The npm half of the SBOM's evidence. A key read wrongly here becomes a
component that is missing or misnamed everywhere downstream, and a manifest
read as empty would report every real import as undeclared -- a whole set of
invented supply-chain findings.
"""

import json
from pathlib import Path

import pytest

from conftest import app_path, require_corpus
from dependency_fixtures import JS_DECLARED, JS_MANIFESTS, LANGGRAPHJS_STARTER
from deps.npm_manifest import (
    DEPENDENCY_KEYS,
    MANIFEST_NAME,
    has_manifest,
    manifests_present,
    read_manifest,
)

# A manifest using both dependency keys, since devDependencies are audited too.
BOTH_KEYS = {
    "name": "demo",
    "dependencies": {"zod": "^3.23.8"},
    "devDependencies": {"typescript": "^5.5.4"},
}

LOCKFILE_NAME = "yarn.lock"


def write_manifest(app_dir: Path, document: object) -> Path:
    """Write a package.json holding the given JSON document."""
    path = app_dir / MANIFEST_NAME
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_both_dependency_keys_are_read() -> None:
    """The module reads exactly the two keys an npm app declares under."""
    assert DEPENDENCY_KEYS == ("dependencies", "devDependencies")


def test_a_manifest_declaring_both_kinds_yields_both(tmp_path: Path) -> None:
    """A dev dependency is a supply-chain risk too, so it is not dropped."""
    write_manifest(tmp_path, BOTH_KEYS)
    assert read_manifest(tmp_path) == {"zod": "^3.23.8", "typescript": "^5.5.4"}


def test_a_manifest_with_only_dev_dependencies_still_declares(tmp_path: Path) -> None:
    """Missing `dependencies` is normal; it must not be read as an empty manifest."""
    write_manifest(tmp_path, {"devDependencies": {"typescript": "^5.5.4"}})
    assert read_manifest(tmp_path) == {"typescript": "^5.5.4"}


def test_a_missing_manifest_declares_nothing(tmp_path: Path) -> None:
    """An app with no package.json declares nothing; that is a fact, not an error."""
    assert read_manifest(tmp_path) == {}


def test_an_empty_manifest_declares_nothing(tmp_path: Path) -> None:
    """A package.json with no dependency keys is an answer, not a failure."""
    write_manifest(tmp_path, {"name": "demo"})
    assert read_manifest(tmp_path) == {}


def test_names_are_normalised_as_they_are_read(tmp_path: Path) -> None:
    """npm names are case-insensitive, so the join key is lowercased on the way in."""
    write_manifest(tmp_path, {"dependencies": {"Zod": "^3.23.8"}})
    assert read_manifest(tmp_path) == {"zod": "^3.23.8"}


def test_a_scoped_name_keeps_its_at_sign(tmp_path: Path) -> None:
    """The scope is part of the package's identity; encoding it belongs to the purl."""
    write_manifest(tmp_path, {"dependencies": {"@langchain/core": "^0.3.3"}})
    assert read_manifest(tmp_path) == {"@langchain/core": "^0.3.3"}


def test_a_non_string_constraint_becomes_an_empty_one(tmp_path: Path) -> None:
    """A malformed constraint declares the package and nothing about its version."""
    write_manifest(tmp_path, {"dependencies": {"zod": None}})
    assert read_manifest(tmp_path) == {"zod": ""}


def test_malformed_json_is_refused(tmp_path: Path) -> None:
    """A package.json that will not parse must fail loudly, not read as empty."""
    (tmp_path / MANIFEST_NAME).write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_manifest(tmp_path)


def test_the_malformed_json_error_names_the_file(tmp_path: Path) -> None:
    """The message says which file to go and look at."""
    (tmp_path / MANIFEST_NAME).write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError) as error:
        read_manifest(tmp_path)
    assert MANIFEST_NAME in str(error.value)


def test_a_manifest_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    """Valid JSON of the wrong shape is still unreadable as a manifest."""
    write_manifest(tmp_path, ["zod"])
    with pytest.raises(ValueError):
        read_manifest(tmp_path)


def test_a_dependency_section_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    """`"dependencies": []` names no packages, and reading it as none would hide that."""
    write_manifest(tmp_path, {"dependencies": ["zod"]})
    with pytest.raises(ValueError) as error:
        read_manifest(tmp_path)
    assert "dependencies" in str(error.value)


def test_no_manifest_present_is_an_empty_list(tmp_path: Path) -> None:
    """An app with no package.json read no manifest, and the SBOM must say so."""
    assert manifests_present(tmp_path) == []
    assert has_manifest(tmp_path) is False


def test_a_manifest_present_is_named(tmp_path: Path) -> None:
    """The SBOM records what it read, which is what `declared_in` cites."""
    write_manifest(tmp_path, BOTH_KEYS)
    assert manifests_present(tmp_path) == [MANIFEST_NAME]
    assert has_manifest(tmp_path) is True


def test_a_lockfile_beside_the_manifest_is_recorded_too(tmp_path: Path) -> None:
    """yarn.lock is what makes a version `locked`, so the document must say it was read."""
    write_manifest(tmp_path, BOTH_KEYS)
    (tmp_path / LOCKFILE_NAME).write_text("# lockfile\n", encoding="utf-8")
    assert manifests_present(tmp_path) == [MANIFEST_NAME, LOCKFILE_NAME]


def test_a_lockfile_with_no_manifest_is_still_recorded(tmp_path: Path) -> None:
    """A lockfile without its manifest is odd, but it was read and must be reported."""
    (tmp_path / LOCKFILE_NAME).write_text("# lockfile\n", encoding="utf-8")
    assert manifests_present(tmp_path) == [LOCKFILE_NAME]


def test_a_directory_named_like_the_manifest_is_not_one(tmp_path: Path) -> None:
    """Only a file counts, or a stray directory would be reported as a manifest read."""
    (tmp_path / MANIFEST_NAME).mkdir()
    assert has_manifest(tmp_path) is False
    assert manifests_present(tmp_path) == []


def test_the_corpus_manifest_matches_the_recorded_fixture() -> None:
    """The real package.json still says what dependency_fixtures claims it says.

    This is what stops the recorded generator sample used by the other npm
    tests from drifting away from the app it is supposed to describe.
    """
    require_corpus(LANGGRAPHJS_STARTER)
    assert read_manifest(app_path(LANGGRAPHJS_STARTER)) == JS_DECLARED


def test_the_corpus_app_ships_a_manifest_and_a_lockfile() -> None:
    """Both files exist, which is why the JS app is the fixture that exercises `locked`."""
    require_corpus(LANGGRAPHJS_STARTER)
    assert manifests_present(app_path(LANGGRAPHJS_STARTER)) == JS_MANIFESTS

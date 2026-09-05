"""Reading a requirements file: what the app claims to depend on.

The manifest is one half of the SBOM's evidence, so a line read wrongly here
becomes a component that is missing or misnamed everywhere downstream.
"""

from pathlib import Path

from dependency_fixtures import PYPI_DECLARED
from deps.package_names import PYPI, normalise_name
from deps.requirements_parser import (
    MANIFEST_NAME,
    manifests_present,
    parse_line,
    read_requirements,
)


def test_splits_a_name_from_its_constraint() -> None:
    """A constrained requirement yields the name and the constraint separately."""
    assert parse_line("langchain~=0.3.25") == ("langchain", "~=0.3.25")


def test_exact_pin_keeps_its_operator() -> None:
    """The `==` is part of the constraint, since it is what makes a version a fact."""
    assert parse_line("langchain-litellm==0.2.0") == ("langchain-litellm", "==0.2.0")


def test_bare_name_has_an_empty_constraint() -> None:
    """An unconstrained requirement declares a package and nothing about its version."""
    assert parse_line("streamlit") == ("streamlit", "")


def test_comment_line_declares_nothing() -> None:
    """A whole-line comment is not a requirement."""
    assert parse_line("# pinned by the security review") is None


def test_blank_line_declares_nothing() -> None:
    """Blank and whitespace-only lines are skipped."""
    assert parse_line("   ") is None


def test_include_of_another_file_is_skipped() -> None:
    """`-r other.txt` names a file, not a package."""
    assert parse_line("-r other.txt") is None


def test_index_url_option_is_skipped() -> None:
    """pip's own options declare no dependency."""
    assert parse_line("--index-url https://example.invalid/simple") is None


def test_inline_comment_is_stripped() -> None:
    """Everything after a `#` is commentary, not part of the constraint."""
    assert parse_line("requests==2.31.0  # bumped for CVE-2023-32681") == (
        "requests", "==2.31.0",
    )


def test_environment_marker_is_stripped() -> None:
    """A `;` marker says when the requirement applies, not which version it is."""
    assert parse_line('tomli>=2.0 ; python_version<"3.11"') == ("tomli", ">=2.0")


def test_direct_url_requirement_is_skipped() -> None:
    """A URL requirement has no PyPI name to normalise, so it declares nothing here."""
    assert parse_line("https://example.invalid/pkg.tar.gz") is None


def test_normalise_name_lowercases() -> None:
    """PEP 503 names are lowercase, so `PyYAML` and `pyyaml` are one package."""
    assert normalise_name("PyYAML", PYPI) == "pyyaml"


def test_normalise_name_collapses_separators() -> None:
    """Underscores and dots become hyphens, so the import name joins the manifest name."""
    assert normalise_name("langchain_litellm", PYPI) == "langchain-litellm"
    assert normalise_name("ruamel.yaml", PYPI) == "ruamel-yaml"


def test_parsed_names_are_normalised() -> None:
    """A line is normalised as it is read, so no caller has to remember to."""
    assert parse_line("PyYAML==6.0.1") == ("pyyaml", "==6.0.1")


def test_reads_a_whole_manifest(tmp_path: Path) -> None:
    """A mixed file yields only its real requirements, keyed by normalised name."""
    (tmp_path / MANIFEST_NAME).write_text(
        "# deps\n\nPyYAML==6.0.1\n-r dev.txt\nstreamlit\n", encoding="utf-8",
    )
    assert read_requirements(tmp_path) == {"pyyaml": "==6.0.1", "streamlit": ""}


def test_missing_manifest_declares_nothing(tmp_path: Path) -> None:
    """An app with no requirements.txt declares nothing; that is a fact, not an error."""
    assert read_requirements(tmp_path) == {}


def test_a_written_manifest_reads_back_as_the_recorded_fixture(tmp_path: Path) -> None:
    """The recorded declaration set still round-trips through the parser it describes.

    This used to read the pinned app's own requirements.txt, which is what kept
    `PYPI_DECLARED` honest. That app is gone, so this can only prove the
    parser and the fixture agree on the *format* -- not that either matches any
    real application.
    """
    lines = [f"{name}{constraint}" for name, constraint in PYPI_DECLARED.items()]
    (tmp_path / MANIFEST_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert read_requirements(tmp_path) == PYPI_DECLARED


def test_no_manifest_present_is_an_empty_list(tmp_path: Path) -> None:
    """An app with no requirements.txt read no manifest, and the SBOM must say so."""
    assert manifests_present(tmp_path) == []


def test_a_manifest_present_is_named(tmp_path: Path) -> None:
    """The SBOM records the manifest by name, which is what `declared_in` cites."""
    (tmp_path / MANIFEST_NAME).write_text("streamlit\n", encoding="utf-8")
    assert manifests_present(tmp_path) == [MANIFEST_NAME]


def test_a_directory_named_like_the_manifest_is_not_one(tmp_path: Path) -> None:
    """Only a file counts, or a stray directory would be reported as a manifest read."""
    (tmp_path / MANIFEST_NAME).mkdir()
    assert manifests_present(tmp_path) == []

"""Two runs over the same app must produce byte-identical artifacts.

This is why the generator's own output is not stored: it carries a random
serialNumber, a timestamp and absolute paths, so a diff between two runs would
show change where nothing changed, and a real change would be lost in it.
"""

import json

from artifacts.aibom import aibom_to_json, build_aibom
from artifacts.mapping import build_mapping, mapping_to_json
from artifacts.cyclonedx import to_cyclonedx
from artifacts.sbom import sbom_to_json
from conftest import CORPUS_DIR, scan_to_json
from dependency_fixtures import (
    CORPUS_GENERATOR_OUTPUT,
    SUPPORT_AGENT,
    corpus_sbom,
    corpus_surfaces,
    string_values,
)
from parsing.repo_loader import local_module_names

# Fields a generator adds that would differ between two runs of the same app.
VOLATILE_SUBSTRINGS = ("timestamp", "serialNumber")


def corpus_mapping() -> dict:
    """Map the corpus app's surfaces, telling the join which modules are its own."""
    local = local_module_names(str(CORPUS_DIR / SUPPORT_AGENT))
    return build_mapping(corpus_surfaces(), corpus_sbom(), local)


def artifact_texts() -> dict[str, str]:
    """Serialise every artifact once, keyed by file name.

    surfaces.json is included because it now carries parser output, which is
    where an absolute path would leak in from.
    """
    surfaces = corpus_surfaces()
    return {
        "surfaces.json": scan_to_json(str(CORPUS_DIR / SUPPORT_AGENT)),
        "sbom.json": sbom_to_json(corpus_sbom()),
        "aibom.json": aibom_to_json(build_aibom(surfaces)),
        "mapping.json": mapping_to_json(corpus_mapping()),
    }


def test_the_sbom_is_byte_identical_across_two_builds() -> None:
    """Same generator output and same manifest, same bytes."""
    assert sbom_to_json(corpus_sbom()) == sbom_to_json(corpus_sbom())


def test_the_aibom_is_byte_identical_across_two_builds() -> None:
    """Same surfaces, same bytes."""
    surfaces = corpus_surfaces()
    assert aibom_to_json(build_aibom(surfaces)) == aibom_to_json(build_aibom(surfaces))


def test_the_mapping_is_byte_identical_across_two_builds() -> None:
    """Same surfaces and same SBOM, same bytes."""
    assert mapping_to_json(corpus_mapping()) == mapping_to_json(corpus_mapping())


def test_the_aibom_does_not_depend_on_the_order_surfaces_arrive_in() -> None:
    """File-walk order must not reach the artifact, or two machines would differ."""
    surfaces = corpus_surfaces()
    reversed_surfaces = list(reversed(surfaces))
    assert aibom_to_json(build_aibom(surfaces)) == aibom_to_json(build_aibom(reversed_surfaces))


def test_the_mapping_does_not_depend_on_the_order_surfaces_arrive_in() -> None:
    """Entries are sorted by surface id, so the input order cannot show through."""
    surfaces = corpus_surfaces()
    sbom = corpus_sbom()
    first = mapping_to_json(build_mapping(surfaces, sbom))
    second = mapping_to_json(build_mapping(list(reversed(surfaces)), sbom))
    assert first == second


def test_no_artifact_contains_an_absolute_path() -> None:
    """An absolute path is this machine's layout, which no artifact may record.

    The recorded Syft output names the manifest by absolute path, so this is a
    live risk rather than a hypothetical one.
    """
    for name, text in artifact_texts().items():
        absolute = [value for value in string_values(json.loads(text))
                    if value.startswith("/")]
        assert absolute == [], (name, absolute)


def test_no_artifact_contains_a_volatile_generator_field() -> None:
    """A timestamp or serialNumber would make every run differ from the last."""
    for name, text in artifact_texts().items():
        for substring in VOLATILE_SUBSTRINGS:
            assert substring not in text, (name, substring)


def test_every_artifact_ends_with_exactly_one_newline() -> None:
    """A stable trailing newline keeps the files diff-friendly."""
    for name, text in artifact_texts().items():
        assert text.endswith("\n") and not text.endswith("\n\n"), name


def test_the_standard_bill_names_no_absolute_path() -> None:
    """It must describe the app, not the machine that scanned it.

    The generator emits a component for the manifest it read, named by its
    absolute path. Left in, the file would only ever reproduce on one machine,
    which defeats the point of publishing a standard format.
    """
    text = sbom_to_json(to_cyclonedx(dict(CORPUS_GENERATOR_OUTPUT)))
    assert "/home/" not in text
    assert not any(c in text for c in ("serialNumber", "timestamp"))

"""Two runs over the same app must produce byte-identical artifacts.

This is why the generator's own output is not stored: it carries a random
serialNumber, a timestamp and absolute paths, so a diff between two runs would
show change where nothing changed, and a real change would be lost in it.

**The audited tree is written by the test**, by `mixed_app_fixtures`, since the
pinned app it used to run over was removed -- so its inputs were chosen by the
same author as the code, and it holds no oversized file, no non-UTF-8 source
and no unforeseen code shape. The absolute-path check keeps its teeth anyway:
the recorded generator output names a manifest by absolute path, and the tree
itself sits under `tmp_path`, so a leaked path would be visible in both
directions.
"""

import json
from pathlib import Path

from artifacts.aibom import aibom_to_json, build_aibom
from artifacts.findings_document import findings_to_json
from artifacts.sarif import sarif_to_json, to_sarif
from artifacts.mapping import build_mapping, mapping_to_json
from artifacts.cyclonedx import to_cyclonedx
from artifacts.sbom import sbom_to_json
from checks.run_checks import build_findings
from conftest import scan_to_json
from dependency_fixtures import PYPI_GENERATOR_OUTPUT, pypi_sbom, string_values
from mixed_app_fixtures import MIXED_APP_FINDINGS, MIXED_APP_SURFACES, write_mixed_app
from parsing.extractor import extract_repo
from parsing.repo_loader import local_module_names

# Fields a generator adds that would differ between two runs of the same app.
VOLATILE_SUBSTRINGS = ("timestamp", "serialNumber")


def app_surfaces(repo: Path) -> list:
    """Extract the written app's surfaces, asserting it yielded the expected number."""
    surfaces = extract_repo(str(repo)).surfaces
    assert len(surfaces) == MIXED_APP_SURFACES, "an empty scan cannot prove determinism"
    return surfaces


def app_mapping(repo: Path) -> dict:
    """Map the written app's surfaces, telling the join which modules are its own."""
    return build_mapping(app_surfaces(repo), pypi_sbom(), local_module_names(str(repo)))


def app_findings(repo: Path) -> dict:
    """Run the static checks over the written app's surfaces and its mapping.

    The planner document is dropped: it holds one run's check order, which is
    deliberately not part of the byte-identical claim these tests make about
    findings.json. `tests/checks/test_planner_wiring.py` owns it.
    """
    document, _planner_document = build_findings(
        str(repo), app_surfaces(repo), app_mapping(repo))
    assert document["finding_count"] == MIXED_APP_FINDINGS, "a silent run proves nothing"
    return document


def artifact_texts(repo: Path) -> dict[str, str]:
    """Serialise every artifact once, keyed by file name.

    surfaces.json is included because it now carries parser output, which is
    where an absolute path would leak in from. findings.json joins on the
    strongest terms available: today's runs record `model_run.status:
    disabled`, so neither exempt field carries anything and the whole file is
    under the comparison like every other artifact.
    """
    surfaces = app_surfaces(repo)
    return {
        "surfaces.json": scan_to_json(str(repo)),
        "sbom.json": sbom_to_json(pypi_sbom()),
        "aibom.json": aibom_to_json(build_aibom(surfaces)),
        "mapping.json": mapping_to_json(app_mapping(repo)),
        "findings.json": findings_to_json(app_findings(repo)),
        # The standard-format copy joins on the same terms: it drops the one
        # model-authored field, so nothing in it is exempt.
        "findings.sarif.json": sarif_to_json(to_sarif(app_findings(repo))),
    }


def test_the_sbom_is_byte_identical_across_two_builds() -> None:
    """Same generator output and same manifest, same bytes."""
    assert sbom_to_json(pypi_sbom()) == sbom_to_json(pypi_sbom())


def test_the_aibom_is_byte_identical_across_two_builds(tmp_path) -> None:
    """Same surfaces, same bytes."""
    surfaces = app_surfaces(write_mixed_app(tmp_path))
    assert aibom_to_json(build_aibom(surfaces)) == aibom_to_json(build_aibom(surfaces))


def test_the_mapping_is_byte_identical_across_two_builds(tmp_path) -> None:
    """Same surfaces and same SBOM, same bytes."""
    repo = write_mixed_app(tmp_path)
    assert mapping_to_json(app_mapping(repo)) == mapping_to_json(app_mapping(repo))


def test_the_findings_are_byte_identical_across_two_builds(tmp_path) -> None:
    """Same surfaces and same mapping, same bytes: no model wrote any of this run."""
    repo = write_mixed_app(tmp_path)
    assert findings_to_json(app_findings(repo)) == findings_to_json(app_findings(repo))


def test_the_aibom_does_not_depend_on_the_order_surfaces_arrive_in(tmp_path) -> None:
    """File-walk order must not reach the artifact, or two machines would differ."""
    surfaces = app_surfaces(write_mixed_app(tmp_path))
    reversed_surfaces = list(reversed(surfaces))
    assert aibom_to_json(build_aibom(surfaces)) == aibom_to_json(build_aibom(reversed_surfaces))


def test_the_mapping_does_not_depend_on_the_order_surfaces_arrive_in(tmp_path) -> None:
    """Entries are sorted by surface id, so the input order cannot show through."""
    surfaces = app_surfaces(write_mixed_app(tmp_path))
    sbom = pypi_sbom()
    first = mapping_to_json(build_mapping(surfaces, sbom))
    second = mapping_to_json(build_mapping(list(reversed(surfaces)), sbom))
    assert first == second


def test_no_artifact_contains_an_absolute_path(tmp_path) -> None:
    """An absolute path is this machine's layout, which no artifact may record.

    The recorded Syft output names the manifest by absolute path, and the
    audited tree itself lives under `tmp_path`, so this is a live risk rather
    than a hypothetical one.
    """
    for name, text in artifact_texts(write_mixed_app(tmp_path)).items():
        absolute = [value for value in string_values(json.loads(text))
                    if value.startswith("/")]
        assert absolute == [], (name, absolute)


def test_no_artifact_names_the_directory_the_scan_ran_in(tmp_path) -> None:
    """The tree sits at a fresh path on every run, so recording it would break determinism."""
    repo = write_mixed_app(tmp_path)
    for name, text in artifact_texts(repo).items():
        assert str(repo) not in text, name


def test_no_artifact_contains_a_volatile_generator_field(tmp_path) -> None:
    """A timestamp or serialNumber would make every run differ from the last."""
    for name, text in artifact_texts(write_mixed_app(tmp_path)).items():
        for substring in VOLATILE_SUBSTRINGS:
            assert substring not in text, (name, substring)


def test_every_artifact_ends_with_exactly_one_newline(tmp_path) -> None:
    """A stable trailing newline keeps the files diff-friendly."""
    for name, text in artifact_texts(write_mixed_app(tmp_path)).items():
        assert text.endswith("\n") and not text.endswith("\n\n"), name


def test_the_standard_bill_names_no_absolute_path() -> None:
    """It must describe the app, not the machine that scanned it.

    The generator emits a component for the manifest it read, named by its
    absolute path. Left in, the file would only ever reproduce on one machine,
    which defeats the point of publishing a standard format.
    """
    text = sbom_to_json(to_cyclonedx(dict(PYPI_GENERATOR_OUTPUT)))
    assert "/home/" not in text
    assert not any(c in text for c in ("serialNumber", "timestamp"))

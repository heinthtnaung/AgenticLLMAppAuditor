"""Guards on reading a Syft report: the components, their order, and what is refused."""

import pytest

from deps import syft_runner
from deps.scanner import ScannerFailed, ScannerUnavailable
from deps.syft_runner import (
    Component,
    build_command,
    is_available,
    read_components,
    scan_directory,
)
from samples import DJANGO_PURL, NOT_PATHS, load, syft_artifact, syft_report_of

# Captured from Syft 1.52.0 over a directory holding one requirements.txt. The
# artifacts are in the order it emitted them, which is not sorted order.
REPORT = "syft_report.json"
REPORT_WITH_NO_ARTIFACTS = "syft_report_no_artifacts.json"


def test_a_well_formed_report_gives_every_component():
    components = read_components(load(REPORT))
    assert [component.name for component in components] == ["django", "pyyaml", "requests"]


def test_a_component_carries_what_identifies_it():
    django = read_components(load(REPORT))[0]
    assert django == Component(
        name="django",
        version="2.2.0",
        purl=DJANGO_PURL,
        ecosystem="python",
        locations=("/requirements.txt",),
    )


def test_components_come_back_sorted_rather_than_in_scan_order():
    # The saved report lists pyyaml first; two runs over one tree must not differ
    # because a cataloger reported in another order.
    scanned = [entry["name"] for entry in load(REPORT)["artifacts"]]
    assert scanned != sorted(scanned)
    components = read_components(load(REPORT))
    assert [component.name for component in components] == sorted(scanned)


def test_one_component_declared_in_two_places_sorts_by_where_it_was_found():
    # Same name, same version, same purl: all that is left to order them by is the
    # manifest each was found in, and scan order is not an order.
    components = read_components(
        syft_report_of(
            syft_artifact(locations=[{"path": "/tools/requirements.txt"}]),
            syft_artifact(locations=[{"path": "/requirements.txt"}]),
        )
    )
    assert [component.locations for component in components] == [
        ("/requirements.txt",),
        ("/tools/requirements.txt",),
    ]


def test_a_report_with_no_artifacts_gives_no_components():
    assert read_components(load(REPORT_WITH_NO_ARTIFACTS)) == ()


def test_a_component_syft_could_not_version_is_kept_rather_than_refused():
    # An empty version is what Syft says about a component it found but could not
    # version. It is the tool's answer, not a broken report.
    components = read_components(syft_report_of(syft_artifact(version="")))
    assert components[0].version == ""
    assert components[0].purl == DJANGO_PURL


def test_a_component_with_no_purl_is_refused_by_name():
    with pytest.raises(ScannerFailed, match="'django' is missing purl"):
        read_components(syft_report_of(syft_artifact(purl="")))


def test_a_component_with_no_name_is_refused():
    with pytest.raises(ScannerFailed, match="missing name"):
        read_components(syft_report_of(syft_artifact(name="")))


def test_locations_are_sorted_and_carry_no_repeats():
    repeated = syft_artifact(
        locations=[
            {"path": "/tools/requirements.txt"},
            {"path": "/requirements.txt"},
            {"path": "/tools/requirements.txt"},
        ]
    )
    assert read_components(syft_report_of(repeated))[0].locations == (
        "/requirements.txt",
        "/tools/requirements.txt",
    )


@pytest.mark.parametrize("report", [[], "artifacts", {}, {"artifacts": None}])
def test_a_document_that_is_not_a_syft_report_is_refused(report):
    with pytest.raises(ScannerFailed, match="must be a JSON object carrying an 'artifacts' list"):
        read_components(report)


def test_an_artifact_that_is_not_an_object_is_refused():
    with pytest.raises(ScannerFailed, match="must be a JSON object"):
        read_components(syft_report_of("django"))


def test_the_command_scans_the_directory_as_a_directory(tmp_path):
    command = build_command(tmp_path)
    assert command[0] == "syft"
    assert f"dir:{tmp_path}" in command
    assert command[-2:] == ["-o", "syft-json"]


def test_availability_is_read_from_the_path(monkeypatch):
    monkeypatch.setattr(syft_runner.shutil, "which", lambda name: None)
    assert is_available() is False
    monkeypatch.setattr(syft_runner.shutil, "which", lambda name: "/usr/bin/syft")
    assert is_available() is True


def test_an_absent_syft_is_reported_rather_than_crashing_out_of_nowhere(monkeypatch, tmp_path):
    monkeypatch.setattr(syft_runner.shutil, "which", lambda name: None)
    with pytest.raises(ScannerUnavailable, match="not installed"):
        scan_directory(tmp_path)


def test_a_directory_that_is_not_there_is_refused_before_syft_is_reached(tmp_path):
    with pytest.raises(ValueError, match="is not a directory to scan"):
        scan_directory(tmp_path / "absent")


def test_a_directory_given_as_a_string_scans_what_the_path_scans(monkeypatch, tmp_path):
    # A directory named on a command line reaches here as a string. It must scan,
    # and Syft must be handed the command the Path would have built.
    commands = []

    def record(command):
        """Stand in for Syft, keeping the command line and answering with one artifact."""
        commands.append(command)
        return syft_report_of(syft_artifact())

    monkeypatch.setattr(syft_runner, "run_json_scanner", record)
    scanned = scan_directory(f"{tmp_path}/")
    assert [component.name for component in scanned] == ["django"]
    assert scanned == scan_directory(tmp_path)
    assert commands[0] == commands[1]


@pytest.mark.parametrize("value, named", NOT_PATHS)
def test_a_directory_that_is_no_kind_of_path_is_refused_by_its_type(value, named):
    with pytest.raises(TypeError, match=f"must be a str or a Path, not {named}"):
        scan_directory(value)

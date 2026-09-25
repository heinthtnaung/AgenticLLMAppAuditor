"""Guards on reading a Syft report: the components, their order, and what cannot be joined."""

import pytest

from deps.scanner import ScannerFailed
from deps.syft_report import Component, UnidentifiedArtifact, read_catalogue
from samples import DJANGO_PURL, load, syft_artifact, syft_report_of

# Captured from Syft 1.52.0 over a directory holding one requirements.txt. The
# artifacts are in the order it emitted them, which is not sorted order.
REPORT = "syft_report.json"
REPORT_WITH_NO_ARTIFACTS = "syft_report_no_artifacts.json"


def read_components(report):
    """Read only the joinable half of a catalogue, which most of these tests are about."""
    return read_catalogue(report).components



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
    assert read_catalogue(load(REPORT_WITH_NO_ARTIFACTS)).components == ()


def test_a_component_syft_could_not_version_is_kept_rather_than_refused():
    # An empty version is what Syft says about a component it found but could not
    # version. It is the tool's answer, not a broken report.
    components = read_components(syft_report_of(syft_artifact(version="")))
    assert components[0].version == ""
    assert components[0].purl == DJANGO_PURL


def test_an_artifact_with_no_purl_is_collected_rather_than_refusing_the_scan():
    # A workflow calling `./local-action` has no package identity by nature, and
    # no advisory database could ever carry a purl for it. Refusing the whole
    # scan over something nothing could join to turns a non-issue into a total
    # failure, and larger repositories do this constantly.
    catalogue = read_catalogue(
        syft_report_of(syft_artifact(), syft_artifact(name="./local-action", purl=""))
    )
    assert [one.name for one in catalogue.components] == ["django"]
    assert catalogue.unidentified == (
        UnidentifiedArtifact("./local-action", "python", ("/requirements.txt",)),
    )


def test_an_artifact_with_no_purl_is_spotted_by_the_missing_purl_and_not_its_type():
    # `github-action-workflow` is the shape found today; the next cataloguer will
    # have another, and the rule is the same for all of them.
    odd = syft_artifact(name="mystery", type="something-new", purl="")
    catalogue = read_catalogue(syft_report_of(syft_artifact(), odd))
    assert [one.name for one in catalogue.unidentified] == ["mystery"]


def test_an_unidentifiable_artifact_with_no_name_is_still_carried():
    catalogue = read_catalogue(syft_report_of(syft_artifact(), syft_artifact(name="", purl="")))
    assert [one.name for one in catalogue.unidentified] == ["<unnamed>"]


def test_a_scan_that_identified_nothing_at_all_is_still_loud():
    # Not a repository with no packages: artifacts found and not one identified.
    # A Syft that stripped every purl would look exactly like this, and must not
    # read as a clean scan -- though a real repository can too, pinned below.
    nothing_joinable = syft_report_of(syft_artifact(purl=""), syft_artifact(name="o", purl=""))
    with pytest.raises(ScannerFailed, match="catalogued 2 artifacts and identified none"):
        read_catalogue(nothing_joinable)


def test_a_rust_crate_with_no_dependencies_is_refused_although_nothing_went_wrong():
    # Accepted: the one artifact Syft 1.52 catalogues from such a crate's Cargo.lock
    # is the crate itself, measured with no purl, because it has no `source`. The
    # run exits 2 on it. Telling it apart from a failed cataloguer turns this red.
    lone_crate = syft_artifact(
        name="lone", version="0.1.0", type="rust-crate", purl="",
        locations=[{"path": "/Cargo.lock", "accessPath": "/Cargo.lock"}],
    )
    with pytest.raises(ScannerFailed, match="catalogued 1 artifact and identified none"):
        read_catalogue(syft_report_of(lone_crate))


def test_a_repository_with_no_packages_is_not_a_failure():
    assert read_catalogue(syft_report_of()) == read_catalogue(load(REPORT_WITH_NO_ARTIFACTS))


def test_unidentified_artifacts_come_back_sorted():
    out_of_order = (syft_artifact(name="zebra", purl=""), syft_artifact(name="apple", purl=""))
    catalogue = read_catalogue(syft_report_of(syft_artifact(), *out_of_order))
    assert [one.name for one in catalogue.unidentified] == ["apple", "zebra"]


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
        read_catalogue(report)


def test_an_artifact_that_is_not_an_object_is_refused():
    with pytest.raises(ScannerFailed, match="must be a JSON object"):
        read_catalogue(syft_report_of("django"))

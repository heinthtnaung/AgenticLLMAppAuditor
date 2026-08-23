"""The expected_surfaces grading key: every one is found, and clean apps gain no extras."""

import pytest
from conftest import CORPUS_APPS, app_is_present, CORPUS_DIR, ground_truth, require_corpus
from extractor import extract_repo
from surface import Surface

# An expected surface's line may point at any line of a multi-line construct.
LINE_TOLERANCE = 3


def _expected_surface_cases() -> list:
    """Build one pytest case per expected_surfaces record across every corpus app."""
    cases = []
    for app in CORPUS_APPS:
        records = ground_truth(app)["expected_surfaces"]
        cases.extend(pytest.param(app, r, id=f"{app}-{r['id']}") for r in records)
    return cases


EXPECTED_SURFACE_CASES = _expected_surface_cases()


def _identity(record: dict) -> tuple[str, str, str]:
    """Return the (file, kind, name) triple that identifies one expected surface."""
    return (record["file"], record["kind"], record["name"])


def _surface_identity(surface: Surface) -> tuple[str, str, str]:
    """Return the same triple for an extracted surface, so the two sets are comparable."""
    return (surface.file, surface.kind, surface.name)


@pytest.fixture(scope="module")
def extracted() -> dict:
    """Extract every corpus app once and share the result across the tests."""
    return {
        app: extract_repo(str(CORPUS_DIR / app))
        for app in CORPUS_APPS
        if app_is_present(app)
    }


@pytest.mark.parametrize("app, record", EXPECTED_SURFACE_CASES)
def test_expected_surface_is_extracted(extracted: dict, app: str, record: dict) -> None:
    """Each expected surface is produced with its exact file, kind and name, at the right line."""
    require_corpus(app)
    lines = [
        surface.line
        for surface in extracted[app]
        if _surface_identity(surface) == _identity(record)
    ]
    assert lines, (
        f"{record['id']}: no {record['kind']} named {record['name']!r} extracted from "
        f"{app}/{record['file']} (expected around line {record['line']})"
    )
    assert any(abs(line - record["line"]) <= LINE_TOLERANCE for line in lines), (
        f"{record['id']}: {record['name']!r} extracted at lines {lines}, "
        f"expected within {LINE_TOLERANCE} of line {record['line']}"
    )


@pytest.mark.parametrize("app, record", EXPECTED_SURFACE_CASES)
def test_expected_surface_module_matches(extracted: dict, app: str, record: dict) -> None:
    """The expected surface's module is resolved, so Phase 2 can map it to an SBOM component."""
    require_corpus(app)
    modules = {
        surface.module
        for surface in extracted[app]
        if _surface_identity(surface) == _identity(record)
    }
    assert record["module"] in modules, (
        f"{record['id']}: expected module {record['module']!r} for {record['name']!r}, "
        f"extracted {sorted(modules)}"
    )


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_no_unexpected_surface_when_complete(extracted: dict, app: str) -> None:
    """Where the grading key claims to list every surface, the extractor invents none."""
    require_corpus(app)
    truth = ground_truth(app)
    if not truth["expected_surfaces_complete"]:
        pytest.skip(f"{app} ground truth does not claim a complete surface list")
    expected = {_identity(record) for record in truth["expected_surfaces"]}
    found = {_surface_identity(surface) for surface in extracted[app]}
    assert found == expected, (
        f"{app}: false positives {sorted(found - expected)}, missed {sorted(expected - found)}"
    )

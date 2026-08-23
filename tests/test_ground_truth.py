"""Integrity checks on the grading key: each app's ground_truth.json must stay true."""

import pytest
from conftest import CORPUS_DIR, DEMO_APPS, ground_truth, manifest
from surface import SURFACE_KINDS

# The OWASP subset this project audits, plus the auditability risk it adds.
ALLOWED_OWASP_IDS = frozenset({"LLM01", "LLM02", "LLM05", "LLM06", "AUDITABILITY"})

# code_anchor stores the first 60 characters of the trimmed source line.
ANCHOR_LENGTH = 60


def _all_findings() -> list:
    """Build one pytest case per finding across both demo apps."""
    cases = []
    for app in DEMO_APPS:
        findings = ground_truth(app)["findings"]
        cases.extend(pytest.param(app, f, id=f"{app}-{f['id']}") for f in findings)
    return cases


ALL_FINDING_CASES = _all_findings()


@pytest.mark.parametrize("app", DEMO_APPS)
def test_app_name_matches_manifest(app: str) -> None:
    """The ground truth names the same app as the manifest beside it."""
    assert ground_truth(app)["app"] == manifest(app)["name"] == app


@pytest.mark.parametrize("app", DEMO_APPS)
def test_upstream_commit_matches_manifest(app: str) -> None:
    """The ground truth was written against the commit the manifest pins."""
    assert ground_truth(app)["upstream_commit"] == manifest(app)["upstream_commit"]


@pytest.mark.parametrize("app", DEMO_APPS)
def test_finding_count_matches_findings(app: str) -> None:
    """finding_count is the real number of findings, not a stale total."""
    truth = ground_truth(app)
    assert truth["finding_count"] == len(truth["findings"])


@pytest.mark.parametrize("app", DEMO_APPS)
def test_finding_ids_are_unique(app: str) -> None:
    """Every finding id appears once, so a finding can be referred to unambiguously."""
    ids = [finding["id"] for finding in ground_truth(app)["findings"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("app, finding", ALL_FINDING_CASES)
def test_owasp_id_is_in_the_audited_subset(app: str, finding: dict) -> None:
    """Each finding maps to a risk this project claims to cover."""
    assert finding["owasp_id"] in ALLOWED_OWASP_IDS


@pytest.mark.parametrize("app, finding", ALL_FINDING_CASES)
def test_llm_surface_is_null_or_a_known_kind(app: str, finding: dict) -> None:
    """A finding's llm_surface is either absent or one of the four surface kinds."""
    assert finding["llm_surface"] is None or finding["llm_surface"] in SURFACE_KINDS


@pytest.mark.parametrize("app, finding", ALL_FINDING_CASES)
def test_code_anchor_still_matches_the_source_line(app: str, finding: dict) -> None:
    """The anchored source line has not drifted away from the recorded line number."""
    path = CORPUS_DIR / app / finding["file"]
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= finding["line"], f"{finding['id']}: {path} has no line {finding['line']}"
    actual = lines[finding["line"] - 1].strip()
    assert actual.startswith(finding["code_anchor"]), (
        f"{finding['id']}: {finding['file']}:{finding['line']} drifted.\n"
        f"  anchor: {finding['code_anchor']!r}\n"
        f"  actual: {actual[:ANCHOR_LENGTH]!r}"
    )

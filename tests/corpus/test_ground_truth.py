"""Integrity checks on the grading key: each app's ground_truth.json must stay true."""

import pytest
from conftest import CORPUS_APPS, CORPUS_DIR, GROUND_TRUTH_SCHEMA_VERSION, ground_truth, manifest, require_corpus
from artifacts.surface import SURFACE_KINDS

# The OWASP subset this project audits, plus the auditability risk it adds.
ALLOWED_OWASP_IDS = frozenset({"LLM01", "LLM02", "LLM05", "LLM06", "AUDITABILITY"})

# code_anchor stores the first 60 characters of the trimmed source line.
ANCHOR_LENGTH = 60


def _cases(section: str) -> list:
    """Build one pytest case per record of a ground-truth section, across every corpus app."""
    cases = []
    for app in CORPUS_APPS:
        records = ground_truth(app)[section]
        cases.extend(pytest.param(app, r, id=f"{app}-{r['id']}") for r in records)
    return cases


ALL_FINDING_CASES = _cases("findings")
ALL_EXPECTED_SURFACE_CASES = _cases("expected_surfaces")


def assert_anchor_matches(app: str, record: dict) -> None:
    """Fail if the recorded line no longer starts with the record's code_anchor."""
    path = CORPUS_DIR / app / record["file"]
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= record["line"], f"{record['id']}: {path} has no line {record['line']}"
    actual = lines[record["line"] - 1].strip()
    assert actual.startswith(record["code_anchor"]), (
        f"{record['id']}: {record['file']}:{record['line']} drifted.\n"
        f"  anchor: {record['code_anchor']!r}\n"
        f"  actual: {actual[:ANCHOR_LENGTH]!r}"
    )


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_schema_version_is_the_one_the_suite_reads(app: str) -> None:
    """Every ground truth declares the schema version these tests know how to read."""
    require_corpus(app)
    assert ground_truth(app)["schema_version"] == GROUND_TRUTH_SCHEMA_VERSION


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_app_name_matches_manifest(app: str) -> None:
    """The ground truth names the same app as the manifest beside it."""
    require_corpus(app)
    assert ground_truth(app)["app"] == manifest(app)["name"] == app


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_upstream_commit_matches_manifest(app: str) -> None:
    """The ground truth was written against the commit the manifest pins."""
    require_corpus(app)
    assert ground_truth(app)["upstream_commit"] == manifest(app)["upstream_commit"]


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_finding_count_matches_findings(app: str) -> None:
    """finding_count is the real number of findings, not a stale total."""
    require_corpus(app)
    truth = ground_truth(app)
    assert truth["finding_count"] == len(truth["findings"])


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_expected_surface_count_matches_expected_surfaces(app: str) -> None:
    """expected_surface_count is the real number of expected surfaces, not a stale total."""
    require_corpus(app)
    truth = ground_truth(app)
    assert truth["expected_surface_count"] == len(truth["expected_surfaces"])


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_finding_ids_are_unique(app: str) -> None:
    """Every finding id appears once, so a finding can be referred to unambiguously."""
    require_corpus(app)
    ids = [finding["id"] for finding in ground_truth(app)["findings"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_expected_surface_ids_are_unique(app: str) -> None:
    """Every expected surface id appears once within its app, so a case id is unambiguous."""
    require_corpus(app)
    ids = [record["id"] for record in ground_truth(app)["expected_surfaces"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("app, finding", ALL_FINDING_CASES)
def test_owasp_id_is_in_the_audited_subset(app: str, finding: dict) -> None:
    """Each finding maps to a risk this project claims to cover."""
    require_corpus(app)
    assert finding["owasp_id"] in ALLOWED_OWASP_IDS


@pytest.mark.parametrize("app, finding", ALL_FINDING_CASES)
def test_llm_surface_is_null_or_a_known_kind(app: str, finding: dict) -> None:
    """A finding's llm_surface is either absent or one of the four surface kinds."""
    require_corpus(app)
    assert finding["llm_surface"] is None or finding["llm_surface"] in SURFACE_KINDS


@pytest.mark.parametrize("app, record", ALL_EXPECTED_SURFACE_CASES)
def test_expected_surface_kind_is_known(app: str, record: dict) -> None:
    """Every expected surface asks for one of the four kinds the extractor can produce."""
    require_corpus(app)
    assert record["kind"] in SURFACE_KINDS


@pytest.mark.parametrize("app, finding", ALL_FINDING_CASES)
def test_finding_anchor_still_matches_the_source_line(app: str, finding: dict) -> None:
    """The anchored source line has not drifted away from the recorded line number."""
    require_corpus(app)
    assert_anchor_matches(app, finding)


@pytest.mark.parametrize("app, record", ALL_EXPECTED_SURFACE_CASES)
def test_expected_surface_anchor_still_matches_the_source_line(app: str, record: dict) -> None:
    """An expected surface's anchor still matches its line, so the grading key is not stale."""
    require_corpus(app)
    assert_anchor_matches(app, record)

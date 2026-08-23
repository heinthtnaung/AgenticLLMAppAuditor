"""Task 1.7: every LLM surface named in a corpus app's ground truth must be extracted."""

import pytest
from conftest import CORPUS_APPS, CORPUS_DIR, ground_truth
from extractor import extract_file, extract_repo
from extractor_js import parse_source
from extractor_python import parse_file
from surface import SURFACE_KINDS, surfaces_to_json

# Named explicitly: CORPUS_APPS is discovered on disk, so its order is not a contract.
SUPPORT_AGENT_APP = "vuln-app-1-support-agent"

# A finding's line may point at any line of the construct, so allow a small window.
LINE_TOLERANCE = 3


def _surface_findings(app: str) -> list[dict]:
    """Return the findings of one app that name an LLM surface to be found."""
    findings = ground_truth(app)["findings"]
    return [finding for finding in findings if finding["llm_surface"] is not None]


def _expected_cases() -> list:
    """Build one pytest case per ground-truth finding that names a surface."""
    cases = []
    for app in CORPUS_APPS:
        cases.extend(pytest.param(app, f, id=f["id"]) for f in _surface_findings(app))
    return cases


EXPECTED_SURFACE_CASES = _expected_cases()


def _line_window(finding: dict) -> tuple[int, int]:
    """Return the accepted line range for a finding, widened by the tolerance."""
    last_line = finding["line_end"] or finding["line"]
    return finding["line"] - LINE_TOLERANCE, last_line + LINE_TOLERANCE


@pytest.fixture(scope="module")
def extracted() -> dict:
    """Extract every corpus app once and share the result across the tests."""
    return {app: extract_repo(str(CORPUS_DIR / app)) for app in CORPUS_APPS}


@pytest.mark.parametrize("app, finding", EXPECTED_SURFACE_CASES)
def test_ground_truth_surface_is_extracted(extracted: dict, app: str, finding: dict) -> None:
    """The extractor finds each ground-truth surface at the right file, kind and line."""
    low, high = _line_window(finding)
    matches = [
        surface
        for surface in extracted[app]
        if surface.file == finding["file"]
        and surface.kind == finding["llm_surface"]
        and low <= surface.line <= high
    ]
    assert matches, (
        f"{finding['id']}: no {finding['llm_surface']} surface extracted for "
        f"{app}/{finding['file']} lines {low}-{high} "
        f"(ground truth line {finding['line']}, name {finding['surface_name']!r})"
    )


@pytest.mark.parametrize("app, finding", EXPECTED_SURFACE_CASES)
def test_ground_truth_surface_name_matches(extracted: dict, app: str, finding: dict) -> None:
    """A ground-truth surface_name matches an extracted surface's name exactly."""
    if finding["surface_name"] is None:
        pytest.skip("finding records no surface name")
    low, high = _line_window(finding)
    names = [
        surface.name
        for surface in extracted[app]
        if surface.file == finding["file"]
        and surface.kind == finding["llm_surface"]
        and low <= surface.line <= high
    ]
    assert finding["surface_name"] in names, (
        f"{finding['id']}: expected a surface named {finding['surface_name']!r} at "
        f"{app}/{finding['file']}:{finding['line']}, extracted {names}"
    )


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_extract_repo_returns_repo_relative_paths(extracted: dict, app: str) -> None:
    """Extracted files are repo-relative posix paths, so output is machine-independent."""
    files = {surface.file for surface in extracted[app]}
    assert files
    assert not [f for f in files if f.startswith("/") or "\\" in f]


@pytest.mark.parametrize("app", CORPUS_APPS)
def test_extract_repo_uses_only_known_kinds(extracted: dict, app: str) -> None:
    """Every extracted surface carries one of the four declared kinds."""
    kinds = {surface.kind for surface in extracted[app]}
    assert kinds <= set(SURFACE_KINDS)


def test_support_agent_finds_all_four_kinds(extracted: dict) -> None:
    """Demo app 1 exercises all four detectors, not just one."""
    kinds = {surface.kind for surface in extracted[SUPPORT_AGENT_APP]}
    assert kinds == set(SURFACE_KINDS)


def test_extract_repo_on_repo_without_source_returns_empty(tmp_path) -> None:
    """A repository with no source files yields no surfaces rather than an error."""
    (tmp_path / "README.md").write_text("no code here\n", encoding="utf-8")
    assert extract_repo(str(tmp_path)) == []


def test_extract_file_uses_the_given_label(tmp_path) -> None:
    """extract_file records the caller's label, not the absolute path on disk."""
    source = tmp_path / "agent.py"
    source.write_text("system_prompt = \"be helpful\"\n", encoding="utf-8")
    surfaces = extract_file(source, "app/agent.py")
    assert [(s.file, s.line, s.name) for s in surfaces] == [("app/agent.py", 1, "system_prompt")]


def test_parse_file_names_the_file_with_broken_syntax(tmp_path) -> None:
    """An unparsable Python file raises a SyntaxError naming the file and line."""
    broken = tmp_path / "broken.py"
    broken.write_text("def oops(:\n", encoding="utf-8")
    with pytest.raises(SyntaxError, match="broken.py"):
        parse_file(broken)


def test_parse_source_names_the_file_with_broken_typescript(tmp_path) -> None:
    """A malformed TypeScript file raises an error naming the file, never zero surfaces."""
    broken = tmp_path / "broken.ts"
    broken.write_text("function oops( {\n", encoding="utf-8")
    with pytest.raises(SyntaxError, match="broken.ts"):
        parse_source(broken.read_bytes(), broken)


def test_extract_file_requires_a_file_label() -> None:
    """extract_file will not guess a label, so a misused call fails at the call site."""
    with pytest.raises(TypeError):
        extract_file(CORPUS_DIR / SUPPORT_AGENT_APP / "main.py")


def test_extract_file_rejects_an_absolute_label() -> None:
    """An absolute label is refused outright rather than producing a machine-specific artifact."""
    path = CORPUS_DIR / SUPPORT_AGENT_APP / "main.py"
    with pytest.raises(ValueError, match="repo-relative"):
        extract_file(path, str(path))


def test_repeated_runs_produce_identical_bytes() -> None:
    """The same repository always serialises to the same bytes."""
    repo = str(CORPUS_DIR / SUPPORT_AGENT_APP)
    assert surfaces_to_json(extract_repo(repo)) == surfaces_to_json(extract_repo(repo))

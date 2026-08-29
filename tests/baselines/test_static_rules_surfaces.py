"""Baseline A's surfaces.json is derived from its findings, never inventoried.

An empty surfaces list beside findings that name surfaces is a self-contradiction:
the scorer reads `surfaces` to attribute a miss, so a system claiming to have
extracted nothing while reporting six surfaces would have every miss attributed
to `surface_not_extracted` on evidence its own findings deny.

What a grep tool knows about a repository is exactly what it matched, so the
derived list is the distinct surface tuples the findings name -- no more.
"""

from pathlib import Path

from artifacts.finding import STATIC, Finding
from baseline_fixtures import write_tiny_app
from baselines.static_rules import scan_repo, surfaces_from

# A surface two rules could both name, to prove the derivation deduplicates.
SHARED_FILE = "app/agent.py"
SHARED_LINE = 12
SHARED_KIND = "TOOL_CALL"
SHARED_NAME = "ShellTool"
SHARED_SURFACE_ID = f"{SHARED_FILE}:{SHARED_LINE}:{SHARED_KIND}:{SHARED_NAME}"

TYPESCRIPT_FILE = "src/agent.ts"
TYPESCRIPT_SURFACE_ID = f"{TYPESCRIPT_FILE}:4:DATA_SOURCE:input"


def finding_naming(surface_id: str, rule_id: str, file: str, line: int,
                   kind: str, name: str) -> Finding:
    """Build one finding carrying a surface tuple, the way a matched rule does."""
    return Finding(
        owasp_id="LLM06", rule_id=rule_id, title="a rule matched", detection=STATIC,
        surface_id=surface_id, surface_kind=kind, surface_name=name, file=file, line=line,
    )


def shared_surface_findings() -> list[Finding]:
    """Two rules, one surface: the case a per-finding surface list would double-count."""
    return [
        finding_naming(SHARED_SURFACE_ID, rule, SHARED_FILE, SHARED_LINE,
                       SHARED_KIND, SHARED_NAME)
        for rule in ("grep_free_form_tool", "grep_agent_without_audit")
    ]


def test_the_derived_surfaces_are_exactly_the_tuples_the_findings_name(tmp_path: Path) -> None:
    """One surface per distinct `surface_id`, and nothing the findings did not cite."""
    findings = scan_repo(write_tiny_app(tmp_path))
    surfaces = surfaces_from(findings)
    assert {s.id for s in surfaces} == {f.surface_id for f in findings}


def test_the_derived_list_is_not_empty_when_the_findings_name_surfaces(tmp_path: Path) -> None:
    """The self-contradiction this derivation exists to prevent, asserted directly."""
    findings = scan_repo(write_tiny_app(tmp_path))
    assert len(findings) == 5
    assert len(surfaces_from(findings)) == 5


def test_two_rules_naming_one_surface_derive_a_single_surface(tmp_path: Path) -> None:
    """Identity is the surface tuple, so the same code location is one entry."""
    surfaces = surfaces_from(shared_surface_findings())
    assert [s.id for s in surfaces] == [SHARED_SURFACE_ID]


def test_no_findings_derive_no_surfaces(tmp_path: Path) -> None:
    """A repository nothing matched has nothing to say about its surfaces."""
    assert surfaces_from([]) == []


def test_each_derived_surface_names_the_rule_that_matched_it(tmp_path: Path) -> None:
    """`detail` is descriptive, and it is where a reader learns this was a grep hit."""
    surfaces = surfaces_from(shared_surface_findings())
    assert surfaces[0].detail == "matched by grep_free_form_tool"


def test_a_derived_surface_carries_the_language_of_its_file(tmp_path: Path) -> None:
    """`Surface` requires a language, and the file extension is the only evidence there is."""
    finding = finding_naming(TYPESCRIPT_SURFACE_ID, "grep_untrusted_input",
                             TYPESCRIPT_FILE, 4, "DATA_SOURCE", "input")
    assert surfaces_from([finding])[0].language == "typescript"


def test_the_derived_surfaces_are_ordered_by_where_they_sit(tmp_path: Path) -> None:
    """File then line, so the artifact is stable no matter what order rules matched in."""
    surfaces = surfaces_from(scan_repo(write_tiny_app(tmp_path)))
    assert [s.line for s in surfaces] == sorted(s.line for s in surfaces)

"""The report's findings half: nothing-found, the evidence under a finding, and its inputs.

The gap list -- the other half, and the one that stops a short findings list
being read as a clean bill -- is checked in test_report_gaps.py.
"""

import pytest

from artifacts.finding import SCHEMA_VERSION
from artifacts.findings_document import findings_to_json
from artifacts.skipped_file import UNDECODABLE_BYTES, SkippedFile
from artifacts.surface import surfaces_to_json
from findings_fixtures import (
    OWASP_ID,
    build_document,
    confirmed_probe,
    probe_finding,
    static_finding,
)
from report import NOTHING_FOUND, RISK_TITLES, render, render_from_files
from report_fixtures import (
    APP,
    FINDINGS_HEADING,
    HOW_HEADING,
    NOT_EXAMINED_HEADING,
    UNREADABLE,
    document_with_coverage,
    findings_section,
    surfaces_document,
    unresolved_probe,
)


# --- Nothing found is not a clean bill -------------------------------------

def test_an_empty_findings_list_warns_against_reading_it_as_clean() -> None:
    """"No findings" on its own reads as a pass, so the line points at the gap list."""
    text = render(APP, build_document([]), surfaces_document())
    assert NOTHING_FOUND in findings_section(text)
    assert "See what was not examined" in NOTHING_FOUND


def test_an_empty_findings_list_still_renders_the_gap_list() -> None:
    """The section a clean-looking report defers to has to actually be there."""
    text = render(APP, build_document([]), surfaces_document())
    assert NOT_EXAMINED_HEADING in text


def test_the_gap_list_is_a_section_of_the_same_rank_as_the_findings() -> None:
    """Equal billing is a heading level: a subsection would read as an appendix."""
    text = render(APP, build_document([static_finding()]), surfaces_document())
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == [FINDINGS_HEADING, NOT_EXAMINED_HEADING, HOW_HEADING]


def test_the_heading_names_the_app_that_was_audited() -> None:
    """A report sitting in a folder of reports must say which app it is about."""
    text = render(APP, build_document([]), surfaces_document())
    assert text.startswith(f"# Audit report: {APP}")


# --- A finding carries the evidence behind it ------------------------------

def test_a_finding_shows_the_file_and_line_a_reader_can_open() -> None:
    """The point of the report is sending someone to the code that caused the finding."""
    finding = static_finding()
    section = findings_section(render(APP, build_document([finding]), surfaces_document()))
    assert f"- **Where**: `{finding.file}:{finding.line}`" in section


def test_a_finding_shows_its_owasp_id_its_title_and_the_rule_that_raised_it() -> None:
    """Classification and provenance travel together, or neither can be checked."""
    finding = static_finding()
    section = findings_section(render(APP, build_document([finding]), surfaces_document()))
    assert f"### {finding.owasp_id} — {finding.title}" in section
    assert f"- **Risk**: {RISK_TITLES[OWASP_ID]} ({OWASP_ID}, OWASP 2025 list)" in section
    assert f"- **Reached by**: `{finding.rule_id}`, static analysis" in section
    assert f"- **Surface**: `{finding.surface_id}`" in section


def test_a_supply_chain_finding_shows_its_component_and_why_it_was_mapped() -> None:
    """An LLM03 finding's evidence is a package and the reason it was tied to a surface."""
    finding = static_finding(
        owasp_id="LLM03", rule_id="undeclared_dependency",
        purl="pkg:pypi/langchain-community@0.3.0", component_name="langchain-community",
        mapping_reason="import_matched_component")
    section = findings_section(render(APP, build_document([finding]), surfaces_document()))
    assert "- **Component**: `pkg:pypi/langchain-community@0.3.0`" in section
    assert "- **Mapping**: import_matched_component" in section


def test_a_finding_with_no_code_location_says_so_rather_than_printing_none() -> None:
    """A component-only finding has no line to open, and has to admit it."""
    finding = static_finding(surface_id=None, surface_kind=None, surface_name=None,
                             file=None, line=None, component_name="langchain-community")
    section = findings_section(render(APP, build_document([finding]), surfaces_document()))
    assert "- **Where**: `no code location`" in section
    assert "None" not in section


def test_a_static_finding_claims_no_probe() -> None:
    """Nothing was run against the app, and the report must not suggest otherwise."""
    section = findings_section(
        render(APP, build_document([static_finding()]), surfaces_document()))
    assert "static analysis" in section
    assert "probe" not in section.lower()


def test_a_probe_finding_names_the_probe_that_confirmed_it() -> None:
    """A finding reached by a probe must cite it, or that evidence is unreachable."""
    probe = confirmed_probe()
    document = build_document([probe_finding(probe)], [probe])
    section = findings_section(render(APP, document, surfaces_document()))
    assert probe.id in section


# --- Determinism and the on-disk path --------------------------------------

def test_rendering_the_same_evidence_twice_is_byte_identical() -> None:
    """Every artifact here is byte-stable across runs, and the report is one of them."""
    surfaces = surfaces_document([UNREADABLE, SkippedFile("app/notes.py", UNDECODABLE_BYTES)])
    renders = [
        render(APP, document_with_coverage([static_finding()], [unresolved_probe()],
                                           risk_classes=[OWASP_ID]), surfaces)
        for _ in range(2)
    ]
    assert renders[0] == renders[1]


def test_render_from_files_reads_both_artifacts_off_disk(tmp_path) -> None:
    """The two artifacts are the report's only inputs, so it must render from them alone."""
    document = build_document([static_finding()])
    findings_path = tmp_path / "findings.json"
    surfaces_path = tmp_path / "surfaces.json"
    findings_path.write_text(findings_to_json(document), encoding="utf-8")
    surfaces_path.write_text(surfaces_to_json([], [UNREADABLE]), encoding="utf-8")
    text = render_from_files(APP, findings_path, surfaces_path)
    assert text == render(APP, document, surfaces_document([UNREADABLE]))


def test_render_from_files_fails_loudly_when_an_artifact_is_missing(tmp_path) -> None:
    """A report rendered from half its inputs would understate the audit silently."""
    surfaces_path = tmp_path / "surfaces.json"
    surfaces_path.write_text(surfaces_to_json([], []), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        render_from_files(APP, tmp_path / "findings.json", surfaces_path)


# --- An artifact this report cannot read is refused -------------------------

def refusal_message(document: dict) -> str:
    """Render the document and return the refusal it raised."""
    with pytest.raises(ValueError) as refused:
        render(APP, document, surfaces_document())
    return str(refused.value)


def test_render_refuses_a_findings_document_from_an_older_schema() -> None:
    """A v1 file cannot say which risk classes went unchecked, so rendering it would mislead."""
    document = build_document([static_finding()])
    document["schema_version"] = 1
    message = refusal_message(document)
    assert "schema_version 1" in message
    assert f"needs {SCHEMA_VERSION}" in message


def test_render_refuses_a_findings_document_with_no_schema_version() -> None:
    """An unversioned file is refused by name, not left to fail as a KeyError deeper in."""
    document = build_document([static_finding()])
    del document["schema_version"]
    message = refusal_message(document)
    assert "schema_version None" in message
    assert f"needs {SCHEMA_VERSION}" in message


def document_missing_its_cited_probe() -> dict:
    """A document whose probe finding cites a probe the probe list no longer holds.

    `build_findings_document` refuses this, so it is built valid and then edited
    the way a stale or hand-touched findings.json on disk would be.
    """
    probe = confirmed_probe()
    document = build_document([probe_finding(probe)], [probe])
    document["probes"] = []
    document["probe_count"] = 0
    return document


def test_render_refuses_a_probe_finding_whose_probe_is_absent_from_the_document() -> None:
    """Rendered, it says "probe analysis" and shows no probe: a claim with nothing behind it."""
    message = refusal_message(document_missing_its_cited_probe())
    assert confirmed_probe().id in message

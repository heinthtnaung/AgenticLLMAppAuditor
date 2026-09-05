"""The report's advisory lines: the quoted evidence, the pin, and the remainder.

Split from test_report_gaps.py, which owns the other gap lines and already
holds that a snapshot drops "No advisory data was read". This file holds what
a snapshot renders instead: the dated provenance line, the unreached-component
remainder when it is non-zero, and the per-finding advisory evidence.
"""

from advisory_fixtures import (
    ADVISORY_ID, CVSS_SOURCE, CVSS_VECTOR, SEVERITY, advisory_finding)
from artifacts.findings_document import ADVISORY_SNAPSHOT
from cli_helpers import STUB_ADVISORY_PIN
from findings_fixtures import static_finding
from report import render
from report_fixtures import (
    APP,
    document_with_coverage,
    findings_section,
    not_examined_section,
    surfaces_document,
)

UNREACHED_LINE = "with a known advisory reached by no LLM surface"


def gaps(findings_document: dict) -> str:
    """Render the report and return only its gap list."""
    return not_examined_section(render(APP, findings_document, surfaces_document()))


def rendered_finding(finding) -> str:
    """Render a snapshot-backed document holding one finding, findings section only."""
    document = document_with_coverage(findings=(finding,), advisory=ADVISORY_SNAPSHOT)
    return findings_section(render(APP, document, surfaces_document()))


def test_a_snapshot_renders_the_dated_provenance_line() -> None:
    """Without the pin, "scanned for known vulnerabilities" is an undated claim."""
    section = gaps(document_with_coverage(advisory=ADVISORY_SNAPSHOT))
    assert (f"Known-vulnerability data: `{STUB_ADVISORY_PIN['advisory_generator_name']}` "
            f"{STUB_ADVISORY_PIN['advisory_generator_version']}, database of "
            f"`{STUB_ADVISORY_PIN['advisory_db_updated_at']}`.") in section


def test_a_non_zero_unreached_count_is_rendered_with_its_caveat() -> None:
    """The honest remainder: real advisories this report's reachability claim excludes."""
    section = gaps(document_with_coverage(advisory=ADVISORY_SNAPSHOT, advisory_unreached=2))
    assert f"**2 components {UNREACHED_LINE}**" in section


def test_an_unreached_count_of_zero_drops_the_line() -> None:
    """Every dangerous component reached is no remainder, so no caveat is printed."""
    section = gaps(document_with_coverage(advisory=ADVISORY_SNAPSHOT, advisory_unreached=0))
    assert UNREACHED_LINE not in section


def test_a_single_unreached_component_is_not_pluralised() -> None:
    """The human report must not print "1 components"."""
    section = gaps(document_with_coverage(advisory=ADVISORY_SNAPSHOT, advisory_unreached=1))
    assert f"**1 component {UNREACHED_LINE}**" in section


VULN_HEADING = "## Known vulnerabilities in dependencies"


def dependency_section(rendered: str) -> str:
    """The itemized unreached-advisory section, sliced from the whole report."""
    after = rendered.split(VULN_HEADING, 1)[1]
    return after.split("## ", 1)[0]


def test_the_unreached_components_are_itemized_in_their_own_section() -> None:
    """The whole point of the fix: the vulnerable components are listed, not just counted."""
    items = [{"purl": "pkg:npm/lodash@4.17.19",
              "advisories": [{"id": "CVE-2021-23337", "severity": "HIGH"},
                             {"id": "CVE-2020-28500", "severity": None}]},
             {"purl": "pkg:npm/ejs@3.1.6",
              "advisories": [{"id": "CVE-2022-29078", "severity": "CRITICAL"}]}]
    report = render(APP, document_with_coverage(
        advisory=ADVISORY_SNAPSHOT, advisory_unreached=2,
        advisory_unreached_components=items), surfaces_document())
    assert VULN_HEADING in report
    section = dependency_section(report)
    assert "`pkg:npm/lodash@4.17.19` — CVE-2021-23337 (HIGH), CVE-2020-28500" in section
    assert "`pkg:npm/ejs@3.1.6` — CVE-2022-29078 (CRITICAL)" in section


def test_no_unreached_components_writes_no_dependency_section() -> None:
    """An app whose vulnerable components are all reached has nothing to list here."""
    report = render(APP, document_with_coverage(advisory=ADVISORY_SNAPSHOT, advisory_unreached=0),
                    surfaces_document())
    assert VULN_HEADING not in report


def test_zero_reached_findings_but_vulnerable_deps_is_not_a_clean_bill() -> None:
    """The headline must not read 'No findings' when known vulnerabilities are listed below."""
    items = [{"purl": "pkg:npm/lodash@4.17.19",
              "advisories": [{"id": "CVE-2021-23337", "severity": "HIGH"}]}]
    report = render(APP, document_with_coverage(
        advisory=ADVISORY_SNAPSHOT, advisory_unreached=1,
        advisory_unreached_components=items), surfaces_document())
    assert "No finding reaches an LLM surface" in report
    assert VULN_HEADING in report


def test_a_finding_quotes_its_advisory_and_the_fix() -> None:
    """The id and the fix the database names, so a reader can check the claim."""
    section = rendered_finding(advisory_finding(advisory_fixed_version="0.3.26"))
    assert f"- **Advisory**: `{ADVISORY_ID}`, fixed in `0.3.26`" in section


def test_a_finding_with_no_fix_says_so_rather_than_printing_none() -> None:
    """"No fixed version published" is the fact; a null rendered raw is not."""
    section = rendered_finding(advisory_finding(advisory_fixed_version=None))
    assert f"- **Advisory**: `{ADVISORY_ID}`, no fixed version published" in section


def test_a_finding_quotes_the_severity_word_with_its_source_named() -> None:
    """The rating is attributed, because "HIGH" from nobody is not evidence."""
    section = rendered_finding(advisory_finding())
    assert f"- **Severity**: {SEVERITY} (per {CVSS_SOURCE})" in section


def test_a_finding_quotes_the_cvss_vector_with_its_source_named() -> None:
    """Quoted verbatim and attributed -- a quotation, never a severity judgement."""
    section = rendered_finding(advisory_finding())
    assert f"- **CVSS ({CVSS_SOURCE}, quoted)**: `{CVSS_VECTOR}`" in section


def test_a_finding_with_no_vector_renders_no_cvss_line() -> None:
    """No vector was quoted, so no CVSS line may imply one was.

    The severity word goes with the vector, and not merely for tidiness:
    `finding.py`'s `_check_advisory_fields` refuses a rating with nothing
    attributing it, so a finding carrying "HIGH" and no source is not a
    Finding this project can build.
    """
    section = rendered_finding(advisory_finding(advisory_cvss_vector=None,
                                                advisory_cvss_source=None,
                                                advisory_severity=None))
    assert "CVSS" not in section


def test_the_report_summarizes_vex_statements_by_status() -> None:
    """The VEX subsection counts affected vs under_investigation, from one source."""
    items = [{"purl": "pkg:npm/x@1", "advisories": [{"id": "CVE-1", "severity": "HIGH"}]}]
    report = render(APP, document_with_coverage(
        advisory=ADVISORY_SNAPSHOT, advisory_unreached=1,
        advisory_unreached_components=items), surfaces_document())
    assert "## VEX (exploitability statements)" in report
    assert "0 affected statements" in report
    assert "1 under_investigation" in report
    assert "never claims that a component is not affected" in report


# The VEX status line, spelled whole: it names what `src/emit_vex.py` would
# state about this finding, so a reader can check the claim against the
# emitter without the OpenVEX document having been written yet.
VEX_STATUS_LINE = ("- **VEX Status**: carries `{advisory_id}`, so "
                   "`python src/emit_vex.py` would state it as `affected` — a "
                   "component a surface reaches.")
VEX_STATUS_MARKER = "- **VEX Status**"

# An id no fixture default uses, so a line hard-coding one cannot pass.
OTHER_ADVISORY = "CVE-2026-31337"

# Every line `report._advisory_evidence` can emit, named by its rendered prefix,
# so "no advisory means no advisory lines" is asserted over the whole set.
ADVISORY_MARKERS = ("- **Advisory**", "- **Severity**", "- **CVSS (", VEX_STATUS_MARKER)


def test_a_finding_states_the_vex_status_its_own_advisory_would_carry() -> None:
    """The line renders, and quotes this finding's advisory rather than any other."""
    section = rendered_finding(advisory_finding(OTHER_ADVISORY))
    assert VEX_STATUS_LINE.format(advisory_id=OTHER_ADVISORY) in section
    assert ADVISORY_ID not in section, "the line quotes a constant, not the finding"


def test_a_finding_with_no_advisory_renders_none_of_the_advisory_lines() -> None:
    """The guard clause, read through the report: no advisory_id, none of its four lines.

    Through `render` rather than `report._advisory_evidence`, following
    `test_sbom_duplicates.py`: the rendered line is the contract, and a test
    reaching past it would keep passing after the renderer stopped calling the
    helper at all. Each marker below is asserted *present* by a test above, so
    absence here cannot mean the section rendered empty.
    """
    section = findings_section(render(APP, document_with_coverage(findings=(static_finding(),)),
                                      surfaces_document()))
    assert [marker for marker in ADVISORY_MARKERS if marker in section] == []

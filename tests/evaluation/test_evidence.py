"""The evidence-link predicates and the counts built from them, one shape at a time.

The proposal asks for the *share* of findings carrying each kind of evidence
link, and `evaluation.json` refuses to hold one: no field in that file is a
float, so this module counts and the denominator travels beside every count.
What that refusal looks like in the finished artifact is asserted in
`test_evidence_document.py`; this file owns the three predicates, `evidence_counts`
and `pooled_evidence`, each read on its own.

The findings are built through `Finding` and serialised by the real document
builder, never hand-written as dicts, because a predicate reading `component_name`
is only correct if that is the field the artifact actually writes. The one
exception is the `line: 0` boundary, which `Finding` refuses outright: it is
written as a literal dict and the test below says why.
"""

import pytest

from artifacts.finding import Finding
from evaluation.evidence import (
    evidence_counts,
    has_code_evidence,
    has_sbom_evidence,
    has_vex_evidence,
    pooled_evidence,
)
from evaluation.scorer import score_app
from evaluation_fixtures import (
    findings_document,
    grading_key,
    key_entry,
    surfaces_document,
)
from advisory_fixtures import ADVISORY_PURL, advisory_finding
from findings_fixtures import build_document, static_finding

# The four keys an evidence block holds, and nothing else: three counts and the
# denominator they are all out of.
EVIDENCE_KEYS = {"findings_considered", "with_code_evidence",
                 "with_sbom_evidence", "with_vex_evidence"}

# A component with no file behind it: the supply-chain shape, where the evidence
# is a package rather than a line.
COMPONENT_NAME = "langchain"


def serialised(*findings: Finding) -> list[dict]:
    """Put findings through the real document builder, so the field names are the artifact's."""
    return build_document(list(findings))["findings"]


def component_finding(**overrides) -> Finding:
    """A finding anchored on a component rather than a surface, so it cites no line."""
    fields = {"owasp_id": "LLM03", "rule_id": "undeclared_dependency",
              "title": "A package the app imports is not declared",
              "detection": "static", "component_name": COMPONENT_NAME,
              "surface_id": None, "surface_kind": None, "surface_name": None,
              "file": None, "line": None, **overrides}
    return Finding(**fields)


# --- has_code_evidence -----------------------------------------------------

def test_a_finding_citing_a_file_and_a_line_carries_code_evidence() -> None:
    """The ordinary static finding: it points at `app/agent.py:12`."""
    finding = serialised(static_finding())[0]
    assert (finding["file"], finding["line"]) == ("app/agent.py", 12)
    assert has_code_evidence(finding) is True


def test_a_component_finding_carries_no_code_evidence() -> None:
    """A package name is not a location: file and line are both null there."""
    finding = serialised(component_finding())[0]
    assert (finding["file"], finding["line"]) == (None, None)
    assert has_code_evidence(finding) is False


def test_a_finding_with_a_file_and_no_line_carries_no_code_evidence() -> None:
    """A whole-file finding cannot be pointed at, so it does not count as located.

    Constructible: only a finding citing a `surface_id` must copy a line, so a
    component finding may name the file it was declared in and no line at all.
    """
    finding = serialised(component_finding(file="requirements.txt"))[0]
    assert (finding["file"], finding["line"]) == ("requirements.txt", None)
    assert has_code_evidence(finding) is False


def test_line_zero_counts_as_located_because_it_is_not_null() -> None:
    """The falsy-int boundary: `0` is a line, `None` is the absence of one.

    Written as a literal because `Finding` refuses `line < 1`, so no artifact
    can hold this record -- which is why the predicate tests `is not None`
    rather than truthiness, and why that is the right test.
    """
    assert has_code_evidence({"file": "app/agent.py", "line": 0}) is True


def test_finding_line_zero_is_refused_by_the_record_itself() -> None:
    """The companion to the boundary above: the shape it guards against is unconstructible."""
    with pytest.raises(ValueError, match="line must be 1 or greater"):
        component_finding(file="app/agent.py", line=0)


# --- has_sbom_evidence -----------------------------------------------------

def test_a_finding_naming_a_component_carries_sbom_evidence() -> None:
    """`component_name` with no purl is the used-but-undeclared case, and it counts."""
    finding = serialised(component_finding())[0]
    assert (finding["component_name"], finding["purl"]) == (COMPONENT_NAME, None)
    assert has_sbom_evidence(finding) is True


def test_a_finding_naming_only_a_purl_carries_sbom_evidence() -> None:
    """The other half of the or: a purl alone is a component the bill of materials holds."""
    finding = serialised(component_finding(component_name=None, purl=ADVISORY_PURL))[0]
    assert (finding["component_name"], finding["purl"]) == (None, ADVISORY_PURL)
    assert has_sbom_evidence(finding) is True


def test_a_surface_only_finding_carries_no_sbom_evidence() -> None:
    """A tool call with no component behind it: the supply chain says nothing about it."""
    assert has_sbom_evidence(serialised(static_finding())[0]) is False


# --- has_vex_evidence ------------------------------------------------------

def test_an_advisory_finding_carries_vex_evidence() -> None:
    """`advisory_id` is what `artifacts/vex.py` keeps, so it is what is counted."""
    finding = serialised(advisory_finding())[0]
    assert finding["advisory_id"] == "CVE-2024-0001"
    assert has_vex_evidence(finding) is True


def test_a_finding_with_no_advisory_carries_no_vex_evidence() -> None:
    """Every other check leaves the field null, and null becomes no statement."""
    finding = serialised(static_finding())[0]
    assert finding["advisory_id"] is None
    assert has_vex_evidence(finding) is False


# --- evidence_counts -------------------------------------------------------

def test_the_counts_are_the_findings_carrying_each_link() -> None:
    """Three findings of three shapes, each counted into every column it belongs to.

    The advisory finding is anchored on a surface, so it is located *and* names
    a component *and* carries a CVE: 2 of the 3 cite code, 2 cite a component.
    """
    findings = serialised(static_finding(), component_finding(), advisory_finding())
    assert evidence_counts(findings) == {
        "findings_considered": 3, "with_code_evidence": 2,
        "with_sbom_evidence": 2, "with_vex_evidence": 1}


def test_one_finding_can_carry_every_kind_of_link_at_once() -> None:
    """The columns are not exclusive: an advisory finding reached from a surface is all three."""
    findings = serialised(advisory_finding())
    assert evidence_counts(findings) == {
        "findings_considered": 1, "with_code_evidence": 1,
        "with_sbom_evidence": 1, "with_vex_evidence": 1}


def test_no_findings_gives_zeros_and_a_zero_denominator() -> None:
    """A run that produced nothing reports 0 of 0, never an absent block."""
    assert evidence_counts([]) == {
        "findings_considered": 0, "with_code_evidence": 0,
        "with_sbom_evidence": 0, "with_vex_evidence": 0}


def test_the_block_holds_the_three_counts_and_their_denominator_only() -> None:
    """No fourth field, and above all no share: the division stays the reader's."""
    assert set(evidence_counts([])) == EVIDENCE_KEYS


# --- pooled_evidence -------------------------------------------------------

def scored_app(app: str, findings: list, **key_overrides) -> dict:
    """Score one app through the real scorer, so the pool reads a real scorecard."""
    key = grading_key([key_entry()], **key_overrides)
    return score_app(app, key, findings_document(findings), surfaces_document())


def unreportable_app(app: str = "unreportable-app") -> dict:
    """An app whose key supports neither rate: no graded findings, and not complete."""
    key = grading_key([], findings_complete=False)
    return score_app(app, key, findings_document([static_finding()]), surfaces_document())


def test_the_pool_adds_the_apps_counts_together() -> None:
    """Pooled, never averaged: two apps' findings are one denominator."""
    apps = [scored_app("first-app", [static_finding()]),
            scored_app("second-app", [advisory_finding()])]
    pooled = pooled_evidence(apps)
    assert pooled["findings_considered"] == 2
    assert (pooled["with_code_evidence"], pooled["with_sbom_evidence"]) == (2, 1)
    assert pooled["with_vex_evidence"] == 1


def test_an_app_supporting_neither_rate_still_counts_toward_the_pool() -> None:
    """Deliberate: evidence coverage is a property of what the tool produced.

    The recall and precision pools gate on what a grading key claims. This one
    must not, or the share would silently describe the graded apps alone.
    """
    app = unreportable_app()
    assert (app["recall_reportable"], app["precision_reportable"]) == (False, False)
    assert pooled_evidence([app])["findings_considered"] == 1
    assert pooled_evidence([app])["with_code_evidence"] == 1


def test_the_pool_names_the_apps_it_rests_on() -> None:
    """Every pooled block in the document names its sample; this one is no exception."""
    apps = [scored_app("second-app", [static_finding()]),
            unreportable_app("first-app")]
    assert pooled_evidence(apps)["apps_included"] == ["first-app", "second-app"]


def test_pooling_no_apps_gives_zeros_rather_than_an_error() -> None:
    """A run with no scored app pools to 0 of 0, which is the honest reading."""
    assert pooled_evidence([]) == {
        "apps_included": [], "findings_considered": 0, "with_code_evidence": 0,
        "with_sbom_evidence": 0, "with_vex_evidence": 0}


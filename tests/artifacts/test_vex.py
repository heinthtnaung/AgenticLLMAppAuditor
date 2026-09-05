"""What a findings document implies as VEX claims, decided without running anything.

Pure throughout: `to_vex_statements` takes two documents' worth of facts and
returns a list, so nothing here starts a process or touches a disk. The two
load-bearing properties are the deduplication -- `known_advisory` reports one
finding per (surface, component, advisory), and OpenVEX cannot order two
statements sharing a timestamp -- and the bound that every statement is
`affected`, which surface reachability is the only evidence for.
"""

from advisory_fixtures import (
    ADVISORY_ID,
    ADVISORY_PURL,
    FIXED_VERSION,
    advisory_document,
    advisory_finding,
)
from artifacts.vex import AFFECTED, NO_FIX, advisory_findings, to_vex_statements
from findings_fixtures import build_document
from sarif_fixtures import component_finding, taint_finding
from vex_fixtures import reaching

# What vexctl writes when no action statement is given. Never this project's
# text: it reads as a finding rather than as the absence of one.
VEXCTL_PLACEHOLDER = "No action statement provided"

SECOND_ADVISORY = "CVE-2024-0002"
SECOND_FIXED_VERSION = "0.3.27"


def test_a_document_with_no_advisory_finding_states_nothing() -> None:
    """The other checks say nothing here: a hygiene finding is not a CVE claim."""
    document = build_document([component_finding(), taint_finding()])
    assert advisory_findings(document) == []
    assert to_vex_statements(document) == []


def test_one_advisory_finding_becomes_one_statement() -> None:
    """The whole claim: this app, this component, this advisory, and the fix."""
    statements = to_vex_statements(advisory_document(advisory_finding()))
    assert statements == [{
        "vulnerability": ADVISORY_ID,
        "subcomponent": ADVISORY_PURL,
        "status": AFFECTED,
        "status_note": "Reached by ShellTool at app/agent.py:12",
        "action_statement": FIXED_VERSION,
    }]


def test_two_surfaces_reaching_one_component_are_one_statement() -> None:
    """Deduplicated on (advisory, component): two statements would not outrank each other."""
    document = advisory_document(reaching("ShellTool", "app/agent.py", 12),
                                 reaching("SearchTool", "app/tools.py", 40))
    statements = to_vex_statements(document)
    assert len(statements) == 1
    assert statements[0]["vulnerability"] == ADVISORY_ID
    assert statements[0]["subcomponent"] == ADVISORY_PURL


def test_the_deduplicated_statement_still_names_every_surface() -> None:
    """Nothing is lost to the grouping: the note carries the evidence both findings had."""
    document = advisory_document(reaching("ShellTool", "app/agent.py", 12),
                                 reaching("SearchTool", "app/tools.py", 40))
    note = to_vex_statements(document)[0]["status_note"]
    assert note == ("Reached by ShellTool at app/agent.py:12, "
                    "SearchTool at app/tools.py:40")


def test_the_surfaces_in_a_note_are_ordered_by_file_and_line() -> None:
    """Built from findings given in the opposite order, so the sort is doing the work."""
    document = advisory_document(reaching("Late", "app/z_last.py", 90),
                                 reaching("Middle", "app/agent.py", 30),
                                 reaching("Early", "app/agent.py", 12))
    note = to_vex_statements(document)[0]["status_note"]
    assert note == ("Reached by Early at app/agent.py:12, Middle at app/agent.py:30, "
                    "Late at app/z_last.py:90")


def test_two_advisories_on_one_component_are_two_statements() -> None:
    """One statement per advisory: they have different fixes, so they are different claims."""
    document = advisory_document(
        advisory_finding(),
        advisory_finding(SECOND_ADVISORY, advisory_fixed_version=SECOND_FIXED_VERSION))
    statements = to_vex_statements(document)
    assert [one["vulnerability"] for one in statements] == [ADVISORY_ID, SECOND_ADVISORY]
    assert [one["action_statement"] for one in statements] == [FIXED_VERSION,
                                                               SECOND_FIXED_VERSION]


def test_the_statement_order_does_not_depend_on_the_finding_order() -> None:
    """Sorted on (advisory, component), so two runs of the same audit agree."""
    findings = (advisory_finding(SECOND_ADVISORY), advisory_finding(ADVISORY_ID))
    forwards = to_vex_statements(advisory_document(*findings))
    backwards = to_vex_statements(advisory_document(*reversed(findings)))
    assert forwards == backwards
    assert [one["vulnerability"] for one in forwards] == [ADVISORY_ID, SECOND_ADVISORY]


def test_a_component_with_no_recorded_fix_says_so_in_this_project_s_words() -> None:
    """vexctl's own placeholder would ship as though a fix had been named."""
    document = advisory_document(advisory_finding(advisory_fixed_version=None))
    assert to_vex_statements(document)[0]["action_statement"] == NO_FIX
    assert NO_FIX != VEXCTL_PLACEHOLDER
    assert VEXCTL_PLACEHOLDER not in NO_FIX


def test_every_statement_from_every_input_is_affected() -> None:
    """The measured bound: reachability proves a component IS reached, never that it is not."""
    document = advisory_document(
        advisory_finding(),
        advisory_finding(SECOND_ADVISORY, advisory_fixed_version=None),
        reaching("SearchTool", "app/tools.py", 40))
    statements = to_vex_statements(document)
    assert len(statements) == 2
    assert {one["status"] for one in statements} == {AFFECTED}
    assert AFFECTED == "affected"


def _doc_with_unreached(unreached_items):
    """A findings document carrying an unreached-components coverage list."""
    from artifacts.findings_document import build_findings_document, coverage, model_run, \
        MODEL_DISABLED, ADVISORY_SNAPSHOT
    return build_findings_document([], [],
        coverage(0, ["known_advisory"], ADVISORY_SNAPSHOT,
                 advisory_generator_name="trivy", advisory_generator_version="0.74.0",
                 advisory_db_updated_at="2026-09-01T00:00:00Z",
                 advisory_unreached_component_count=len(unreached_items),
                 advisory_unreached_components=unreached_items),
        model_run(MODEL_DISABLED))


def test_unreached_components_become_under_investigation_statements() -> None:
    """The vulnerable-but-unreached components get a non-suppressing VEX status."""
    from artifacts.vex import UNDER_INVESTIGATION, to_vex_statements
    items = [{"purl": "pkg:npm/lodash@4.17.19",
              "advisories": [{"id": "CVE-1", "severity": "HIGH"},
                             {"id": "CVE-2", "severity": None}]}]
    statements = to_vex_statements(_doc_with_unreached(items))
    assert [s["status"] for s in statements] == [UNDER_INVESTIGATION, UNDER_INVESTIGATION]
    assert {s["vulnerability"] for s in statements} == {"CVE-1", "CVE-2"}
    assert all(s["action_statement"] is None for s in statements)
    assert all("not reached by any LLM surface" in s["status_note"] for s in statements)


def test_no_statement_is_ever_not_affected() -> None:
    """The measured bound, at the statement level: only affected / under_investigation."""
    from artifacts.vex import AFFECTED, UNDER_INVESTIGATION, to_vex_statements
    items = [{"purl": "pkg:npm/x@1", "advisories": [{"id": "CVE-9", "severity": "LOW"}]}]
    statuses = {s["status"] for s in to_vex_statements(_doc_with_unreached(items))}
    assert statuses <= {AFFECTED, UNDER_INVESTIGATION}

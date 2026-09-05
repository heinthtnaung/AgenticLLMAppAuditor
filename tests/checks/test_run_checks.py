"""Running the static checks over one app's artifacts and assembling findings.json.

The load-bearing part is `coverage.checks_run`: it names the checks that had
something to examine on this app. A check named there and silent examined its
subjects and cleared them, which is a result -- it leaves no probe record, and
that silence is the one a reader would misread as a clean bill. A check absent
from it could not look at all, so its absence is never a clean result.

Most tests here pass an empty directory, which is one half of that rule by
itself: with no Python file to read, the taint trace never had a subject. The
risk-class tests write one file, so every check has a subject and the agreement
between `checks_run` and `risk_classes_checked` is checked over the whole map
rather than over the checks that happen to need no source.

What is *not* here: which app shapes each check is planned for at all. Those
gates -- the query check needing a model, the auditability check needing an
agent -- live in `test_check_scope.py`, because they are about the plan rather
than about the document this file assembles from it.
"""

from pathlib import Path

from artifacts.findings_document import ADVISORY_NOT_INGESTED, MODEL_DISABLED
from artifacts.mapping import MAPPING_REASONS, STDLIB, UNRESOLVED, USED_BUT_UNDECLARED
from artifacts.surface import AGENT_DEF, DATA_SOURCE, TOOL_CALL, Surface
from checks import permissions, supply_chain, workflow
from checks.run_checks import (
    EDGE_CHECKS, GRAPH_CHECKS, RISK_CLASS_BY_CHECK, build_findings)
from parsing.languages import PYTHON

TOOL_SURFACE = Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")
DATA_SURFACE = Surface(DATA_SOURCE, "yaml.load", "utils.py", 75, PYTHON, "yaml read", "yaml")

# An agent built by a factory the auditability check will look at. It is only
# there to make that check plannable: no source line matches it, so the check
# looks and stays silent, which is exactly the state the risk-class tests below
# are about.
AGENT_SURFACE = Surface(AGENT_DEF, "AgentExecutor", "app.py", 1, PYTHON, "agent",
                        "langchain.agents")

# The two checks under test here, whatever else runs beside them.
STATIC_CHECKS = (supply_chain.CHECK_NAME, permissions.CHECK_NAME)

# Python the taint trace can read and clear, so a test can hand every check a
# subject and the risk-class invariant is checked against every check, not most.
CLEAN_PYTHON = "greeting = 'hello'\n"

# Shaped like a real mapping.json: all five reasons present, including zeros.
MAPPING = {
    "entries": [{
        "surface_id": DATA_SURFACE.id,
        "reason": USED_BUT_UNDECLARED,
        "component_name": "pyyaml",
    }],
    "reason_counts": {reason: 0 for reason in MAPPING_REASONS} | {USED_BUT_UNDECLARED: 1},
}


# The same mapping with one surface the resolver could not name a package for,
# beside one it answered `stdlib` for: `unmapped_count` would count both.
UNRESOLVED_MAPPING = {
    "entries": [],
    "reason_counts": {reason: 0 for reason in MAPPING_REASONS} | {UNRESOLVED: 1, STDLIB: 1},
}


def findings_for(repo: Path, surfaces: list, mapping: dict | None,
                 advisories: dict | None = None) -> dict:
    """Assemble the findings document for the given repository.

    The planner document `build_findings` returns beside it is dropped: this
    file is about the findings, and `tests/checks/test_planner_wiring.py` owns
    the other one.
    """
    from cli_helpers import STUB_ADVISORY_PIN
    pin = STUB_ADVISORY_PIN if advisories is not None else None
    document, _planner_document = build_findings(
        str(repo), surfaces, mapping, advisories, pin)
    return document


def test_a_check_that_examined_its_subjects_is_named_even_when_silent(tmp_path) -> None:
    """The permission check read the surface and cleared it, and coverage still names it."""
    document = findings_for(tmp_path, [DATA_SURFACE], None)
    assert document["findings"] == []
    assert permissions.CHECK_NAME in document["coverage"]["checks_run"]


def test_coverage_names_exactly_the_checks_that_had_a_subject_here(tmp_path) -> None:
    """A mapping to read and no Python to trace: two checks could look, the third could not."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], MAPPING)
    assert document["coverage"]["checks_run"] == sorted(STATIC_CHECKS)


def test_coverage_counts_the_surfaces_the_checks_saw(tmp_path) -> None:
    """A short findings list is read against how much was actually looked at."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], None)
    assert document["coverage"]["surfaces_considered"] == 2


def test_coverage_states_that_no_advisory_data_was_read(tmp_path) -> None:
    """An LLM03 finding here cites the mapping, and nothing about known vulnerabilities."""
    document = findings_for(tmp_path, [], None)
    assert document["coverage"]["advisory_data"] == ADVISORY_NOT_INGESTED


def test_the_model_is_recorded_as_disabled(tmp_path) -> None:
    """These checks read artifacts, so there is no prose and the block says why."""
    run = findings_for(tmp_path, [], None)["model_run"]
    assert run["status"] == MODEL_DISABLED
    assert run["ranking"] is None


def test_no_finding_carries_a_narrative_when_the_model_is_disabled(tmp_path) -> None:
    """The one model-authored field stays null unless a model actually wrote it."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], MAPPING)
    assert document["finding_count"] == 2
    assert all(finding["narrative"] is None for finding in document["findings"])


def test_both_static_checks_contribute_their_findings(tmp_path) -> None:
    """One privileged tool and one undeclared package produce one finding each."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], MAPPING)
    assert sorted(f["rule_id"] for f in document["findings"]) == sorted(STATIC_CHECKS)


def test_a_missing_mapping_silences_the_check_that_needs_one(tmp_path) -> None:
    """Without an SBOM there is no mapping, and the supply-chain check reports nothing."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], None)
    assert [f["rule_id"] for f in document["findings"]] == [permissions.CHECK_NAME]


def test_a_missing_mapping_leaves_its_check_out_of_coverage(tmp_path) -> None:
    """That check had nothing to read, so naming it would claim a clean result it never reached."""
    document = findings_for(tmp_path, [DATA_SURFACE], None)
    assert supply_chain.CHECK_NAME not in document["coverage"]["checks_run"]


def test_a_missing_mapping_leaves_the_unresolved_count_null(tmp_path) -> None:
    """No bill of materials means nothing to resolve against, so there is no count to give."""
    document = findings_for(tmp_path, [DATA_SURFACE], None)
    assert document["coverage"]["unresolved_component_count"] is None


def test_a_mapping_that_resolved_everything_reports_zero_rather_than_null(tmp_path) -> None:
    """0 and null are different claims: one resolved every surface, the other never looked."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], MAPPING)
    assert document["coverage"]["unresolved_component_count"] == 0


def test_the_unresolved_count_comes_from_the_mappings_unresolved_reason(tmp_path) -> None:
    """It is that one reason, not `unmapped_count`, which also counts answers like stdlib."""
    document = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], UNRESOLVED_MAPPING)
    assert document["coverage"]["unresolved_component_count"] == 1


def test_an_app_with_no_surfaces_produces_an_empty_document(tmp_path) -> None:
    """Audited and clean is a real result, distinct from never audited."""
    document = findings_for(tmp_path, [], None)
    assert document["finding_count"] == 0
    assert document["probes"] == []


# --- risk_classes_checked agrees with checks_run ----------------------------

def document_where_every_check_had_a_subject(tmp_path: Path) -> dict:
    """Assemble a document from a repository every check has something to look at in.

    Four things are load-bearing and none may be dropped: a mapping for the
    supply-chain check, a Python file for the three that read source,
    `TOOL_SURFACE` -- the query check is planned only on an app that drives a
    model, so without an LLM surface it would be absent and the plan short --
    and `AGENT_SURFACE`, which is what makes the auditability check plannable.
    Drop either surface and `checks_run` comes up one name short, so the
    equality against the whole risk-class map stops meaning anything.
    """
    (tmp_path / "app.py").write_text(CLEAN_PYTHON, encoding="utf-8")
    # An empty index is still a subject: the advisory check looked and matched
    # nothing, which is not the same as having had nothing to look at.
    return findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE, AGENT_SURFACE],
                        MAPPING, advisories={})


def test_every_check_that_ran_has_its_risk_class_named(tmp_path) -> None:
    """A check that looked and stayed silent still covered its class, or silence reads as a gap.

    Every check in the map *except* the edge ones, which is what `GRAPH_CHECKS`
    names. `findings_for` hands `build_findings` no `model_ask_fn`, so the
    semantic probe was never offered a model and produced no probe at all -- it
    had nothing to look at, which is the same absence rule the rest of this file
    is about. Expecting the whole map here would claim a model-backed verdict
    from a run with no model in it; the check is exercised in
    `test_semantic_probe.py`, where one is passed.
    """
    coverage = document_where_every_check_had_a_subject(tmp_path)["coverage"]
    assert coverage["checks_run"] == sorted(GRAPH_CHECKS)
    assert all(RISK_CLASS_BY_CHECK[check] in coverage["risk_classes_checked"]
               for check in coverage["checks_run"])


def test_an_edge_check_is_absent_from_a_run_that_was_offered_no_model(tmp_path) -> None:
    """Guard: without this the subtraction above would pass on an edge check that always ran."""
    coverage = document_where_every_check_had_a_subject(tmp_path)["coverage"]
    assert EDGE_CHECKS
    assert set(coverage["checks_run"]) & set(EDGE_CHECKS) == set()


def test_every_risk_class_named_is_one_a_check_that_ran_can_report(tmp_path) -> None:
    """The field is derived from `checks_run`, so no class may outrun the checks behind it."""
    coverage = document_where_every_check_had_a_subject(tmp_path)["coverage"]
    reportable = {RISK_CLASS_BY_CHECK[check] for check in coverage["checks_run"]}
    assert coverage["risk_classes_checked"]
    assert all(risk in reportable for risk in coverage["risk_classes_checked"])


def test_a_check_that_could_not_look_leaves_its_risk_class_out(tmp_path) -> None:
    """No mapping, no supply-chain check, and so no claim that LLM03 was covered."""
    coverage = findings_for(tmp_path, [TOOL_SURFACE, DATA_SURFACE], None)["coverage"]
    assert supply_chain.CHECK_NAME not in coverage["checks_run"]
    assert supply_chain.OWASP_ID not in coverage["risk_classes_checked"]
    assert permissions.OWASP_ID in coverage["risk_classes_checked"]


def test_a_capped_run_claims_only_the_risk_classes_it_reached(monkeypatch, tmp_path) -> None:
    """The plan is not the run: a truncated audit must not claim the classes it never got to."""
    monkeypatch.setattr(workflow, "MAX_STEPS", 1)
    coverage = document_where_every_check_had_a_subject(tmp_path)["coverage"]
    assert len(coverage["checks_run"]) == 1
    assert coverage["risk_classes_checked"] == [RISK_CLASS_BY_CHECK[coverage["checks_run"][0]]]

"""What the planner's order does to the audit: everything, and nothing.

**Nothing, in `findings.json`.** `coverage.checks_run` is sorted, findings and
probes are sorted, and the merge is a permutation, so two runs that ordered the
checks differently produce the same bytes. `README.md` claims that, and until
now nothing compared a model-on run with a model-off one --
`test_determinism.py` compares two model-off runs.

**Everything, to which checks get to look.** A check missing from
`coverage.checks_run` means "could not look at all" (`docs/SCHEMAS.md`), which
`src/evaluation/scorer.py` reads as `no_check_for_risk_class`. So a model able
to drop a name from the order would be deciding what counts as a finding, in
coverage vocabulary, where a reader would not see it.

Between those two sits the falsifier this file exists for: because a full run
leaves no trace of its order, an inert planner -- one whose answer is recorded
and then not used -- looks exactly like a working one. Capping the loop at a
single step is what makes the order observable.

The app comes from `planner_app_fixtures`; every `ask` is a stand-in from
`semantic_probe_fixtures`. Nothing reaches a server.
"""

from artifacts.findings_document import findings_to_json
from checks import workflow
from checks.auditability import CHECK_NAME as AUDITABILITY_CHECK
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.run_checks import GRAPH_CHECKS
from checks.taint import CHECK_NAME as TAINT_CHECK
from planner_app_fixtures import (
    EXPECTED_FINDINGS, REORDERING_REPLY, SUBSET_REPLY, audit)
from semantic_probe_fixtures import PROBE_MODEL, Answering


# --- the model cannot subtract ----------------------------------------------

def test_a_reordering_model_leaves_every_eligible_check_in_coverage(tmp_path) -> None:
    """Reordered or not, every check that could look still looked."""
    document, _planner_document = audit(tmp_path, Answering(REORDERING_REPLY), PROBE_MODEL)
    assert document["coverage"]["checks_run"] == sorted(GRAPH_CHECKS)


def test_a_model_naming_one_check_cannot_drop_the_other_five(tmp_path) -> None:
    """The subtraction attempt in the shape it would arrive in: a strict subset.

    The reply names one of the six. All six still ran, and the one it named ran
    first -- which is the whole of the power the planner has.
    """
    document, planner_document = audit(tmp_path, Answering(SUBSET_REPLY), PROBE_MODEL)
    assert planner_document["order"][0] == AUDITABILITY_CHECK
    assert document["coverage"]["checks_run"] == sorted(GRAPH_CHECKS)


# --- the order reaches the graph --------------------------------------------

def test_a_capped_run_runs_the_check_the_model_put_first(monkeypatch, tmp_path) -> None:
    """The falsifier for an inert planner: with one step, only the first check runs.

    This is the one test that fails if `build_findings` hands `workflow.audit`
    the plan instead of the planner's answer. On an uncapped run the two are
    indistinguishable inside `findings.json`, which is by design.
    """
    monkeypatch.setattr(workflow, "MAX_STEPS", 1)
    document, _planner_document = audit(tmp_path, Answering(REORDERING_REPLY), PROBE_MODEL)
    assert document["coverage"]["checks_run"] == [TAINT_CHECK]


def test_that_capped_run_would_have_run_a_different_check_without_the_model(
        monkeypatch, tmp_path) -> None:
    """Guard: the model has to have moved something, or the test above proves nothing."""
    monkeypatch.setattr(workflow, "MAX_STEPS", 1)
    document, _planner_document = audit(tmp_path)
    assert document["coverage"]["checks_run"] == [PERMISSION_CHECK]


# --- and changes nothing else -----------------------------------------------

def test_the_findings_are_the_same_whatever_order_the_model_chose(tmp_path) -> None:
    """The byte-identity claim, compared model-on against model-off for the first time.

    This app carries no prompt template, so the semantic probe -- which takes
    the same `ask` -- contributes nothing, and the check order is the only
    difference between the two runs.
    """
    ordered, _ = audit(tmp_path / "ordered", Answering(REORDERING_REPLY), PROBE_MODEL)
    default, _ = audit(tmp_path / "default")
    assert ordered["finding_count"] == EXPECTED_FINDINGS, "a silent run proves nothing"
    assert findings_to_json(ordered) == findings_to_json(default)

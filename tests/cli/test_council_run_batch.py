"""Guards on the batch: every council before any escalation, and one record from the same replies.

Why the order is worth having -- a server that cannot hold the escalation model
beside the members loads it once per run -- is in `cli.council_run`. What that
saves on a real GPU has not been measured, and nothing here asks a live model.
"""

import io
from pathlib import Path

from cli.council_run import assessments, watching
from cli.progress import ESCALATION_LINE
from council.prompt import PROMPT_VERSION, REVERSED_PROMPT_VERSION
from report.council_record import CouncilAssessment, CouncilNotAsked, CouncilWithoutVector
from batch_samples import (
    BIG,
    COUNCIL,
    ESCALATION,
    FINDINGS,
    OPEN_ON_AC_AND_S,
    OPEN_ON_S,
    answering,
    one_finding_at_a_time,
)

# The council runs kept with their progress streams, every one of them made live.
KEPT_RUNS = Path(__file__).resolve().parents[2] / "measurements" / "council_runs"


def batched(calls: list, out=None):
    """Assess the four findings in the batch order, noting every call."""
    progress = watching(FINDINGS, COUNCIL, out or io.StringIO())
    return assessments(FINDINGS, COUNCIL, answering(calls), progress, escalation=ESCALATION)


def in_turn(calls: list, out=None):
    """Assess the four findings one at a time, as before the batch, noting every call."""
    progress = watching(FINDINGS, COUNCIL, out or io.StringIO())
    clients = answering(calls)
    return one_finding_at_a_time(FINDINGS, COUNCIL, clients, progress, escalation=ESCALATION)


def both_ways(text: str, metric: str) -> list[tuple[str, str, str, str]]:
    """Give the escalation model's two calls on one metric: in order, then reversed."""
    return [(BIG, text, metric, PROMPT_VERSION), (BIG, text, metric, REVERSED_PROMPT_VERSION)]


def escalation_lines(progress: Path) -> list[str]:
    """Give every escalation line in one kept run's progress stream."""
    lines = progress.read_text(encoding="utf-8").splitlines()
    return [one for one in lines if one.startswith(ESCALATION_LINE)]


def test_every_member_call_is_made_before_the_first_escalation_call():
    calls = []
    batched(calls)
    askers = [name for name, *_ in calls]
    first_escalation = askers.index(BIG)
    assert set(askers[:first_escalation]) == {"small", "other"}
    assert set(askers[first_escalation:]) == {BIG}


def test_the_escalation_calls_come_last_by_finding_then_metric_each_in_both_orders():
    calls = []
    batched(calls)
    expected = [
        *both_ways(OPEN_ON_S, "S"),
        *both_ways(OPEN_ON_AC_AND_S, "AC"),
        *both_ways(OPEN_ON_AC_AND_S, "S"),
    ]
    assert calls[-len(expected):] == expected
    # Three findings asked, two members, eight metrics, both orders.
    assert len(calls) == 3 * 2 * 8 * 2 + len(expected)


def test_the_batch_makes_exactly_the_calls_one_finding_at_a_time_makes():
    batch, turn = [], []
    batched(batch)
    in_turn(turn)
    assert batch != turn
    assert sorted(batch) == sorted(turn)


def test_the_batch_records_exactly_what_one_finding_at_a_time_records():
    batch = batched([])
    assert batch == in_turn([])
    kinds = [type(one) for one in batch]
    assert kinds == [CouncilAssessment, CouncilAssessment, CouncilWithoutVector, CouncilNotAsked]


def test_only_the_order_of_the_progress_lines_changes_and_each_escalation_names_its_finding():
    batch, turn = io.StringIO(), io.StringIO()
    batched([], batch)
    in_turn([], turn)
    said, before = batch.getvalue().splitlines(), turn.getvalue().splitlines()
    escalations = [one for one in before if one.startswith(ESCALATION_LINE)]
    council = [one for one in before if not one.startswith(ESCALATION_LINE)]
    assert said != before
    assert said == council + escalations
    assert escalations[0] == f"{ESCALATION_LINE} 1  finding 1/3 CVE-OPEN-S  S  {BIG}"
    assert escalations[-1] == (
        f"{ESCALATION_LINE} 6  finding 3/3 CVE-OPEN-AC-S  S (options reversed)  {BIG}"
    )


def test_no_kept_run_escalated_so_what_the_batch_saves_on_a_gpu_is_unmeasured():
    # A known gap, asserted so that closing it turns this red. Every run kept in
    # `measurements/council_runs/` predates escalation, so none times a load of the
    # escalation model, per finding or per run. Timing the saving needs a live GPU
    # run the user approves; whoever keeps one updates this and the docstring above.
    kept = sorted(KEPT_RUNS.glob("*.progress.txt"))
    assert kept
    assert [one.name for one in kept if escalation_lines(one)] == []

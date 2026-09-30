"""Guards on the same-evidence flag in the audit record: beside the ruling, and deciding nothing."""

import json

from council_runs import LONG_QUOTE, QUOTED, answering
from escalation_runs import escalated
from report.json_council import council_of
from report.json_report import as_json
from same_evidence_runs import APART, SAME_WORDS, apart, av_of, report_of, same_words, unflagged

FLAG = "same_evidence_different_reading"


def metrics_of(outcome) -> dict:
    """Give an advisory's council metrics from the record, by metric."""
    written = council_of(report_of(outcome), outcome.advisory_id)
    return {one["metric"]: one for one in written["metrics"]}


def without_flags(record):
    """Give a JSON value with every same-evidence flag taken out, and nothing else."""
    if isinstance(record, dict):
        return {key: without_flags(one) for key, one in record.items() if key != FLAG}
    if isinstance(record, list):
        return [without_flags(one) for one in record]
    return record


def test_the_metric_read_two_ways_from_the_same_words_is_flagged_and_no_other():
    flags = {metric: one[FLAG] for metric, one in metrics_of(same_words()).items()}
    assert [metric for metric, flagged in flags.items() if flagged] == ["AV"]
    assert metrics_of(apart())["AV"][FLAG] is False


def test_the_whole_record_changes_only_by_the_flag_its_scores_and_approval_included():
    flagged = json.loads(as_json(report_of(same_words())))
    plain = json.loads(as_json(report_of(unflagged(same_words()))))
    assert flagged != plain
    assert without_flags(flagged) == without_flags(plain)
    assert flagged["findings"][0]["organisation_risk"] and flagged["approval"]


def test_an_escalation_settles_a_flagged_metric_exactly_as_it_settles_its_twin():
    big_says = {"AV": answering("A", QUOTED)}
    flagged = av_of(escalated(big_says, members=SAME_WORDS, advisory_id="CVE-SAME-WORDS"))
    twin = av_of(escalated(big_says, members=APART, advisory_id="CVE-APART"))
    assert flagged.same_evidence_different_reading and not twin.same_evidence_different_reading
    decided = [(one.outcome, one.value, one.basis, one.confidence) for one in (flagged, twin)]
    assert decided[0] == decided[1]
    assert flagged.escalation.said == twin.escalation.said


def test_the_escalation_model_reading_a_members_words_apart_is_not_flagged_the_known_gap():
    """The gap `council.same_evidence` documents, asserted so closing it cannot go unremarked."""
    # RED HERE MEANS THE GAP HAS BEEN CLOSED, not that something broke. Only
    # members count: the escalation model quotes Qwen's sentence and reads A where
    # Qwen read N, and the metric is not flagged.
    big_says = {"AV": answering("A", LONG_QUOTE)}
    escalated_av = av_of(escalated(big_says, members=APART, advisory_id="CVE-APART"))
    assert escalated_av.escalation.said.evidence == LONG_QUOTE
    assert escalated_av.escalation.said.verified and escalated_av.escalation.said.value == "A"
    assert not escalated_av.same_evidence_different_reading

"""The evaluation document: what it states, what it pools, and what it refuses.

The two apps built here are the shape a real pair takes -- one whose key is
incomplete, one whose key grades nothing -- because that is the case in which
an F1 would be a number about no system.
"""

import json

import pytest

from evaluation.document import (
    AGENTIC_AUDITOR,
    SCHEMA_VERSION,
    SCORED_SYSTEMS,
    build_evaluation,
)
from evaluation.scorer import score_app
from evaluation_fixtures import (
    every_value,
    findings_document,
    grading_key,
    key_entry,
    surfaces_document,
    unrelated_finding,
)
from findings_fixtures import static_finding

# One app scores recall only, the other precision only: no app supports both.
RECALL_ONLY_APP = "vulnerable-app"
PRECISION_ONLY_APP = "clean-app"


def recall_only() -> dict:
    """An app whose key grades one finding but does not claim to list them all."""
    key = grading_key([key_entry(), key_entry(id="TINY-02", line=99, line_end=None)],
                      findings_complete=False)
    return score_app(RECALL_ONLY_APP, key, findings_document([static_finding()]),
                     surfaces_document())


def precision_only() -> dict:
    """An app with a complete key that grades nothing, and one finding it did not ask for."""
    return score_app(PRECISION_ONLY_APP, grading_key([]),
                     findings_document([unrelated_finding()]), surfaces_document())


def both_apps() -> list[dict]:
    """The usual shape: the two scorecards, in the order that is not sorted."""
    return [precision_only(), recall_only()]


def test_no_value_anywhere_in_the_document_is_a_float() -> None:
    """The point of the artifact: a reader cannot copy a percentage out of it.

    Asserted over the serialised document rather than the object, because that
    is the file someone quotes from.
    """
    document = json.loads(json.dumps(build_evaluation(both_apps())))
    assert [value for value in every_value(document) if isinstance(value, float)] == []


def test_the_document_states_its_schema_version() -> None:
    """A reader keys on the version, so it is in the file and not only in the code."""
    assert build_evaluation(both_apps())["schema_version"] == SCHEMA_VERSION == 3


def test_the_system_is_carried_inside_the_record() -> None:
    """A table row copied into the write-up keeps the label of what produced it."""
    assert build_evaluation(both_apps())["system"] == AGENTIC_AUDITOR


@pytest.mark.parametrize("system", SCORED_SYSTEMS)
def test_each_declared_system_is_accepted(system: str) -> None:
    """The baselines share this document, distinguished only by this field."""
    assert build_evaluation([], system)["system"] == system


def test_an_unknown_system_is_refused() -> None:
    """A typo would silently label a baseline's numbers as the auditor's."""
    with pytest.raises(ValueError, match="unknown system"):
        build_evaluation([], "some_other_tool")


def test_the_apps_are_sorted_by_name() -> None:
    """Sorted, so the same two scorecards always serialise the same way."""
    document = build_evaluation(both_apps())
    assert [app["app"] for app in document["apps"]] == [PRECISION_ONLY_APP, RECALL_ONLY_APP]


def test_the_app_count_is_the_length_of_the_list() -> None:
    """Stated as its own field, so a truncated list is visible rather than plausible."""
    document = build_evaluation(both_apps())
    assert document["app_count"] == len(document["apps"]) == 2


def test_the_recall_block_names_the_apps_it_rests_on() -> None:
    """The sample size cannot be read past: one app, and it is named."""
    totals = build_evaluation(both_apps())["totals"]
    assert totals["recall"]["apps_included"] == [RECALL_ONLY_APP]


def test_the_precision_block_names_the_apps_it_rests_on() -> None:
    """A different app, which is why an F1 over the two would be about neither."""
    totals = build_evaluation(both_apps())["totals"]
    assert totals["precision"]["apps_included"] == [PRECISION_ONLY_APP]


def test_the_recall_block_carries_only_counts_and_a_denominator() -> None:
    """No rate is stored: the reader divides, and to divide holds the denominator."""
    totals = build_evaluation(both_apps())["totals"]
    assert set(totals["recall"]) == {"apps_included", "true_positives",
                                     "false_negatives", "key_finding_count"}


def test_the_precision_block_carries_only_counts_and_a_denominator() -> None:
    """Same rule on the other side: counts and the number of findings produced."""
    totals = build_evaluation(both_apps())["totals"]
    assert set(totals["precision"]) == {"apps_included", "true_positives",
                                        "answered_finding_count",
                                        "false_positives", "produced_finding_count"}


def test_the_totals_hold_exactly_the_five_blocks_the_schema_names() -> None:
    """A closed set, so a sixth block cannot appear in the artifact unnoticed.

    The `evidence` block is one of the five as of schema 3; `f1` is not, and is
    two fields saying it is refused rather than a number.
    """
    assert set(build_evaluation(both_apps())["totals"]) == {
        "recall", "precision", "evidence", "f1_reportable", "f1_blocked_reason"}


def test_the_counts_are_pooled_from_the_included_apps_only() -> None:
    """An app excluded from a block contributes nothing to it, not even its zeros."""
    totals = build_evaluation(both_apps())["totals"]
    assert (totals["recall"]["true_positives"], totals["recall"]["false_negatives"]) == (1, 1)
    assert totals["recall"]["key_finding_count"] == 2


def test_an_app_whose_false_positives_are_null_is_left_out_of_precision() -> None:
    """Null is not zero, and pooling it as zero would invent a measurement."""
    totals = build_evaluation([recall_only()])["totals"]
    assert totals["precision"]["apps_included"] == []
    assert totals["precision"]["false_positives"] == 0


def test_f1_is_refused_with_a_stated_reason() -> None:
    """Refused, not omitted: an absent field reads as unimplemented, this is a decision."""
    totals = build_evaluation(both_apps())["totals"]
    assert totals["f1_reportable"] is False
    assert totals["f1_blocked_reason"] == "no app supports both precision and recall"


def test_f1_becomes_reportable_when_one_app_supports_both() -> None:
    """The refusal is derived from the scored apps, not written into the scorer."""
    complete = score_app("both-app", grading_key([key_entry()]),
                         findings_document([static_finding()]), surfaces_document())
    totals = build_evaluation([complete])["totals"]
    assert totals["f1_reportable"] is True
    assert totals["f1_blocked_reason"] is None


def test_no_app_scores_a_rate_of_its_own() -> None:
    """A per-app percentage would travel without the totals' caveats; there is none."""
    for app in build_evaluation(both_apps())["apps"]:
        assert {"precision", "recall", "f1"} & set(app) == set()

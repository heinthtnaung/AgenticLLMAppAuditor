"""What `score_app` counts for one app, and what it refuses to count.

The counts are the whole point of the artifact -- there are no rates in it --
so each one is pinned here on inputs a reader can hold in their head: one key
entry, one produced finding, one scan.
"""

import pytest

from evaluation.scorer import score_app
from evaluation_fixtures import (
    APP,
    COMMIT,
    FILE,
    KEY_ID,
    LINE,
    SURFACE_KIND,
    answered_key,
    findings_document,
    grading_key,
    key_entry,
    surfaces_document,
    unrelated_finding,
)
from findings_fixtures import RULE_ID, static_finding


# Two findings whose document order (by line) is the reverse of their id order
# (by text), so a list that merely came back untouched would fail the sort test.
EARLIER_SURFACE_ID = "app/z.py:9:TOOL_CALL:Alpha"
LATER_SURFACE_ID = "app/z.py:10:TOOL_CALL:Beta"
TWO_UNMATCHED_FINDINGS = [
    static_finding(file="app/z.py", line=9, surface_id=EARLIER_SURFACE_ID,
                   surface_name="Alpha"),
    static_finding(file="app/z.py", line=10, surface_id=LATER_SURFACE_ID,
                   surface_name="Beta"),
]


def score(key: dict, document: dict, surfaces: dict | None = None) -> dict:
    """Score the fixture app, defaulting to a scan that read every graded file."""
    return score_app(APP, key, document, surfaces if surfaces is not None
                     else surfaces_document())


def test_a_matched_key_entry_is_a_true_positive() -> None:
    """The ordinary case: the finding answers the entry, and the entry is named."""
    scored = score(*answered_key()[:2])
    assert (scored["true_positives"], scored["matched_key_ids"]) == (1, [KEY_ID])


def test_an_unanswered_key_entry_is_a_false_negative() -> None:
    """Nothing produced, so the one graded entry is missed rather than absent."""
    scored = score(grading_key([key_entry()]), findings_document())
    assert (scored["true_positives"], scored["false_negatives"]) == (0, 1)
    assert [miss["key_id"] for miss in scored["misses"]] == [KEY_ID]


def test_two_findings_answering_one_entry_count_as_one_true_positive() -> None:
    """Recall counts key entries, not findings, so a duplicate cannot inflate it."""
    twice = [static_finding(),
             static_finding(line=LINE + 1, surface_id=f"{FILE}:13:{SURFACE_KIND}:ShellTool")]
    scored = score(grading_key([key_entry()]), findings_document(twice))
    assert scored["true_positives"] == 1
    assert scored["produced_finding_count"] == 2


def test_false_positives_are_null_when_the_key_is_not_complete() -> None:
    """`0` would be a lie: an unmatched finding may be real and simply unlisted.

    This is the assertion the whole gating exists for, so it is stated as
    identity against None rather than as falsiness -- `0` is falsy too.
    """
    key = grading_key([key_entry()], findings_complete=False)
    scored = score(key, findings_document([static_finding(), unrelated_finding()]))
    assert scored["false_positives"] is None


def test_an_unmatched_finding_is_still_named_when_it_cannot_be_counted() -> None:
    """The finding is reported under a name that asserts nothing about its truth."""
    key = grading_key([key_entry()], findings_complete=False)
    scored = score(key, findings_document([static_finding(), unrelated_finding()]))
    assert scored["unmatched_finding_ids"] == [unrelated_finding().id]


def test_false_positives_are_counted_when_the_key_is_complete() -> None:
    """A complete key lists every real finding, so an unmatched one is wrong."""
    scored = score(grading_key([key_entry()]),
                   findings_document([static_finding(), unrelated_finding()]))
    assert scored["false_positives"] == 1


def test_a_complete_key_with_nothing_produced_has_no_false_positives() -> None:
    """Zero here is a measurement, not a placeholder: the key could have caught one."""
    scored = score(grading_key([]), findings_document())
    assert scored["false_positives"] == 0


def test_the_denominators_travel_with_the_counts() -> None:
    """A count without its denominator is the thing this artifact exists to prevent."""
    scored = score(grading_key([key_entry()]),
                   findings_document([static_finding(), unrelated_finding()]))
    assert (scored["key_finding_count"], scored["produced_finding_count"]) == (1, 2)


def test_the_scorecard_carries_the_keys_provenance() -> None:
    """A score whose key is unattributed is a score quoted without its source."""
    scored = score(*answered_key()[:2])
    assert scored["upstream_commit"] == COMMIT
    assert scored["key_source"] == "manual_review"
    assert (scored["key_verified"], scored["key_verified_by"]) == (True, "a person")
    assert scored["key_verified_date"] == "2026-01-01"


def test_the_scorecard_records_both_schema_versions_it_read() -> None:
    """What invalidates the score, in place of a timestamp that would break byte-identity."""
    key, document, _ = answered_key()
    scored = score(key, document)
    assert scored["ground_truth_schema_version"] == key["schema_version"]
    assert scored["findings_schema_version"] == document["schema_version"]


def test_the_completeness_flags_are_copied_so_the_gating_is_checkable() -> None:
    """A reader must be able to see why a rate was allowed without opening the key."""
    key = grading_key([key_entry()], findings_complete=False,
                      expected_surfaces_complete=False)
    scored = score(key, findings_document())
    assert (scored["findings_complete"], scored["expected_surfaces_complete"]) == (False, False)


def test_recall_is_reportable_when_the_key_grades_something() -> None:
    """One graded entry and a scan that read its file: recall means something here."""
    assert score(*answered_key()[:2])["recall_reportable"] is True


def test_recall_is_not_reportable_when_the_key_grades_nothing() -> None:
    """Recall over zero entries is not 100%, it is undefined."""
    assert score(grading_key([]), findings_document())["recall_reportable"] is False


def test_recall_is_not_reportable_when_a_graded_file_was_skipped() -> None:
    """A file the scan could not read is a miss nobody can attribute to the checks."""
    scan = surfaces_document(files=(), skipped=(FILE,))
    scored = score(grading_key([key_entry()]), findings_document(), scan)
    assert scored["recall_reportable"] is False
    assert scored["graded_files_skipped"] == [FILE]


def test_a_skipped_file_the_key_does_not_grade_leaves_recall_reportable() -> None:
    """Only the graded files matter: an unreadable README grades nothing."""
    scan = surfaces_document(skipped=("app/other.py",))
    scored = score(*answered_key()[:2], scan)
    assert scored["graded_files_skipped"] == []
    assert scored["recall_reportable"] is True


def test_precision_is_reportable_only_when_the_key_is_complete() -> None:
    """Precision needs a key that claims to list everything; ours says it does not."""
    complete = score(grading_key([key_entry()]), findings_document())
    partial = score(grading_key([key_entry()], findings_complete=False), findings_document())
    assert (complete["precision_reportable"], partial["precision_reportable"]) == (True, False)


def test_matched_key_ids_come_back_sorted_rather_than_in_key_order() -> None:
    """Sorted, so the same scan scored twice produces the same bytes."""
    key = grading_key([key_entry(id="TINY-02"), key_entry()])
    scored = score(key, findings_document([static_finding()]))
    assert scored["matched_key_ids"] == [KEY_ID, "TINY-02"]


def test_unmatched_finding_ids_come_back_sorted_rather_than_in_document_order() -> None:
    """The document orders findings by line; the list orders them by id, and they differ."""
    scored = score(grading_key([]), findings_document(TWO_UNMATCHED_FINDINGS))
    assert scored["unmatched_finding_ids"] == [f"{LATER_SURFACE_ID}:{RULE_ID}",
                                               f"{EARLIER_SURFACE_ID}:{RULE_ID}"]


def test_an_empty_findings_document_is_an_error_not_zero_findings() -> None:
    """A findings.json that was never written must not read as a clean bill.

    The scorer takes documents, not paths, so the refusal it can make is to
    raise on one that has no findings list at all rather than default it to [].
    """
    with pytest.raises(KeyError):
        score(grading_key([key_entry()]), {})

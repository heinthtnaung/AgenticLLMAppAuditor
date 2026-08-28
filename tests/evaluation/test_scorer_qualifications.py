"""What bounds an app's numbers, and where each bound comes from.

A qualification the scorer cannot switch off by changing an artifact is a label
someone typed. So every one below is asserted twice: present on the input that
earns it, absent on the same input with that one fact changed.
"""

from artifacts.findings_document import ADVISORY_SNAPSHOT, MODEL_USED, model_run
from evaluation.scorer import QUALIFICATIONS, SMALL_SAMPLE_BELOW, score_app
from evaluation_fixtures import (
    APP,
    FILE,
    findings_document,
    grading_key,
    key_entry,
    surfaces_document,
)

# A model that really ran, so `model_disabled` has an off position.
MODEL_NAME = "qwen2.5-coder:7b-instruct"


def qualifications(key: dict, document: dict | None = None,
                   surfaces: dict | None = None) -> list[str]:
    """Score one app and return only what its numbers are qualified by."""
    scored = score_app(APP, key, document if document is not None else findings_document(),
                       surfaces if surfaces is not None else surfaces_document())
    return scored["qualifications"]


def many_entries(count: int) -> list[dict]:
    """Return `count` distinct key entries, so the sample size can be varied."""
    return [key_entry(id=f"TINY-{number:02d}") for number in range(count)]


def test_the_vocabulary_is_the_documented_one() -> None:
    """A fixed list, sorted: the write-up quotes these strings verbatim."""
    assert QUALIFICATIONS == (
        "advisory_data_not_ingested", "expected_surfaces_not_complete",
        "findings_not_complete", "key_ai_drafted", "key_unverified",
        "model_disabled", "no_key_findings", "scan_partial", "small_sample",
        "unresolved_components")


def test_every_qualification_reported_is_in_the_vocabulary() -> None:
    """An input that earns nearly all of them must still only produce known strings."""
    key = grading_key([], source="ai_drafted", verified=False,
                      findings_complete=False, expected_surfaces_complete=False)
    assert set(qualifications(key)) <= set(QUALIFICATIONS)


def test_the_qualifications_come_back_sorted() -> None:
    """Sorted, so two runs of the same scan produce the same bytes."""
    key = grading_key([], source="ai_drafted", verified=False)
    assert qualifications(key) == sorted(qualifications(key))


def test_an_unverified_key_qualifies_the_numbers() -> None:
    """Nobody checked the answer key, so nothing measured against it is settled."""
    assert "key_unverified" in qualifications(grading_key([key_entry()], verified=False))


def test_a_verified_key_does_not() -> None:
    """The off position: the same key with the flag set drops the qualification."""
    assert "key_unverified" not in qualifications(grading_key([key_entry()]))


def test_an_ai_drafted_key_qualifies_the_numbers() -> None:
    """A key a model wrote is evidence about a model, until a person signs it off."""
    key = grading_key([key_entry()], source="ai_drafted")
    assert "key_ai_drafted" in qualifications(key)


def test_a_hand_reviewed_key_does_not() -> None:
    """`source` is read, not assumed: manual_review earns no such qualification."""
    assert "key_ai_drafted" not in qualifications(grading_key([key_entry()]))


def test_an_incomplete_key_qualifies_the_numbers() -> None:
    """The same flag that makes false positives null is reported in words too."""
    key = grading_key([key_entry()], findings_complete=False)
    assert "findings_not_complete" in qualifications(key)


def test_a_complete_key_does_not() -> None:
    """The off position: the key claims every finding, so precision has a denominator."""
    assert "findings_not_complete" not in qualifications(grading_key([key_entry()]))


def test_an_incomplete_surface_list_qualifies_the_numbers() -> None:
    """Recall over a partial surface list is recall over an unknown denominator."""
    key = grading_key([key_entry()], expected_surfaces_complete=False)
    assert "expected_surfaces_not_complete" in qualifications(key)


def test_a_complete_surface_list_does_not() -> None:
    """The off position: the key claims every surface, so recall has one too."""
    assert "expected_surfaces_not_complete" not in qualifications(grading_key([key_entry()]))


def test_a_key_that_grades_nothing_says_so() -> None:
    """The clean fixture's case: there was nothing to find, which is not a perfect score."""
    assert "no_key_findings" in qualifications(grading_key([]))


def test_a_key_that_grades_something_does_not() -> None:
    """The off position: one entry to grade, so the score is measured and not vacuous."""
    assert "no_key_findings" not in qualifications(grading_key([key_entry()]))


def test_a_scan_that_skipped_a_graded_file_says_so() -> None:
    """`scan_partial` is the word for a score measured over less than the app."""
    scan = surfaces_document(files=(), skipped=(FILE,))
    assert "scan_partial" in qualifications(grading_key([key_entry()]), surfaces=scan)


def test_a_scan_that_read_every_graded_file_does_not() -> None:
    """The off position, so `scan_partial` is a fact about this run and not a default."""
    assert "scan_partial" not in qualifications(grading_key([key_entry()]))


def test_a_run_without_advisory_data_says_so() -> None:
    """LLM03 numbers rest on the bill alone while advisory ingestion is unfinished."""
    assert "advisory_data_not_ingested" in qualifications(grading_key([key_entry()]))


def test_a_run_with_advisory_data_does_not() -> None:
    """Read from `coverage.advisory_data`, so the artifact can turn it off."""
    document = findings_document(advisory=ADVISORY_SNAPSHOT)
    assert "advisory_data_not_ingested" not in qualifications(grading_key([key_entry()]),
                                                              document)


def test_a_run_with_an_unresolved_component_says_so() -> None:
    """A surface the mapping left without a component is one the LLM03 check could not read."""
    document = findings_document(unresolved_components=1)
    assert "unresolved_components" in qualifications(grading_key([key_entry()]), document)


def test_a_run_that_resolved_every_component_does_not() -> None:
    """The off position: a count of zero is a mapping that left nothing open."""
    document = findings_document(unresolved_components=0)
    assert "unresolved_components" not in qualifications(grading_key([key_entry()]), document)


def test_a_run_that_counted_no_components_at_all_does_not() -> None:
    """`null` means not counted, not "some": no mapping ran, so it bounds nothing."""
    document = findings_document(unresolved_components=None)
    assert "unresolved_components" not in qualifications(grading_key([key_entry()]), document)


def test_a_run_with_the_model_off_says_so() -> None:
    """Every narrative is null, so this is a score for the static checks alone."""
    assert "model_disabled" in qualifications(grading_key([key_entry()]))


def test_a_run_that_used_the_model_does_not() -> None:
    """Read from `model_run.status`, which only a real run can set to `used`."""
    document = findings_document(run=model_run(MODEL_USED, MODEL_NAME))
    assert "model_disabled" not in qualifications(grading_key([key_entry()]), document)


def test_a_key_below_the_sample_floor_says_so() -> None:
    """Under ten graded findings, any rate computed from them is an anecdote."""
    key = grading_key(many_entries(SMALL_SAMPLE_BELOW - 1))
    assert "small_sample" in qualifications(key)


def test_a_key_at_the_sample_floor_does_not() -> None:
    """The boundary is asserted, so the floor cannot drift without a test failing."""
    key = grading_key(many_entries(SMALL_SAMPLE_BELOW))
    assert "small_sample" not in qualifications(key)

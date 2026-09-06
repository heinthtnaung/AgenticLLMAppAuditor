"""Does the rendered page carry every count with the denominator that belongs to it?

Three numbers on this page were wrong in ways that read as results. A model's
flagged count was printed against the union of subjects rather than the ones
*that arm* saw. The exposure section read `arms[-1]` and presented one arm's
traffic as the run's total. And the agreement line stood alone, so a run that
asked nobody anything read as unanimity.

Every test below therefore checks a whole sentence, not a substring: the arms
are built to see different subject sets and to send different amounts, so a
denominator taken from the wrong place produces a different sentence and fails.
"""

from agreement import EXCLUSION_REASONS, INTERPOLATES_NOTHING, TEXT_NOT_LITERAL
from .arm_fixtures import (
    CLEARED_STATE, FIRST, FLAGGED_STATE, HOSTED, INTERPOLATES_NOTHING_STATE, LOCAL,
    MODEL_UNREACHABLE_STATE, SECOND, TEXT_NOT_LITERAL_STATE, arm, study_result)
from comparison_report import REASON_WORDING, TITLE, to_markdown, to_page
from prompt_kinds import FIELD_KINDS, PLANNER_PROMPT, PROBE_PROMPT

# Deliberately different per arm, so a total read off one arm is a wrong total.
LOCAL_REQUESTS, LOCAL_BYTES = 1, 100
HOSTED_REQUESTS, HOSTED_BYTES = 2, 250
TOTAL_REQUESTS, TOTAL_BYTES = 3, 350

PROBE_FIELDS = tuple(FIELD_KINDS[PROBE_PROMPT])
PLANNER_FIELDS = tuple(FIELD_KINDS[PLANNER_PROMPT])

NOT_COMPARED_HEADING = "## Templates the comparison could not use"


def uneven_arms() -> list[dict]:
    """Two arms seeing different subject sets and sending different amounts."""
    return [arm(LOCAL, {FIRST: FLAGGED_STATE, SECOND: CLEARED_STATE},
                requests=LOCAL_REQUESTS, bytes_sent=LOCAL_BYTES, field_kinds=PROBE_FIELDS),
            arm(HOSTED, {FIRST: FLAGGED_STATE},
                requests=HOSTED_REQUESTS, bytes_sent=HOSTED_BYTES,
                field_kinds=PLANNER_FIELDS)]


def test_each_models_flagged_count_is_out_of_what_that_arm_examined() -> None:
    """The denominator is the arm's own subject count, not the union across arms."""
    page = to_markdown(study_result(uneven_arms()))
    assert f"- **`{LOCAL}`** — flagged 1 of 2 it examined," in page
    assert f"- **`{HOSTED}`** — flagged 1 of 1 it examined," in page


def test_each_models_line_carries_its_own_seconds_bytes_and_requests() -> None:
    """The same line's other numbers are that arm's, and bytes never appear alone.

    A byte count without its request count is what let one planner prompt read
    as one probe request per template, so the page pairs them as stdout does.
    """
    page = to_markdown(study_result(uneven_arms()))
    assert (f"flagged 1 of 2 it examined, 1.5s, {LOCAL_BYTES} bytes over "
            f"{LOCAL_REQUESTS} request(s)") in page
    assert (f"flagged 1 of 1 it examined, 1.5s, {HOSTED_BYTES} bytes over "
            f"{HOSTED_REQUESTS} request(s)") in page
    assert "bytes sent" not in page


def test_the_four_bucket_counts_are_printed_together() -> None:
    """No count is quoted without the other three that give it its denominator."""
    page = to_markdown(study_result(uneven_arms()))
    assert ("Of 2 template(s): 1 agreed, 0 disagreed, 0 never put to a model, "
            "1 not seen by every model.") in page


def test_a_run_that_compared_nothing_says_so_rather_than_agreeing() -> None:
    """Both models were unreachable: the page reports two exclusions, not unanimity."""
    unreachable = [arm(LOCAL, {FIRST: MODEL_UNREACHABLE_STATE, SECOND: MODEL_UNREACHABLE_STATE}),
                   arm(HOSTED, {FIRST: MODEL_UNREACHABLE_STATE, SECOND: MODEL_UNREACHABLE_STATE})]
    page = to_markdown(study_result(unreachable))
    assert ("Of 2 template(s): 0 agreed, 0 disagreed, 2 never put to a model, "
            "0 not seen by every model.") in page
    assert NOT_COMPARED_HEADING in page
    assert "agree on" not in page


def test_the_not_compared_section_names_every_excluded_subject_and_its_reason() -> None:
    """Two exclusions for two different reasons, each named in the study's own wording."""
    excluded = [arm(LOCAL, {FIRST: TEXT_NOT_LITERAL_STATE, SECOND: INTERPOLATES_NOTHING_STATE}),
                arm(HOSTED, {FIRST: TEXT_NOT_LITERAL_STATE, SECOND: INTERPOLATES_NOTHING_STATE})]
    page = to_markdown(study_result(excluded))
    assert f"- `{FIRST}` — {REASON_WORDING[TEXT_NOT_LITERAL]}" in page
    assert f"- `{SECOND}` — {REASON_WORDING[INTERPOLATES_NOTHING]}" in page


def test_the_not_compared_section_names_who_never_saw_a_subject() -> None:
    """An absent arm is reported by name, since the planner may have narrowed it away."""
    page = to_markdown(study_result(uneven_arms()))
    assert f"- `{SECOND}` — examined by {LOCAL}, not by {HOSTED}" in page


def test_every_exclusion_reason_has_wording_on_the_page() -> None:
    """A reason with no wording would print its own identifier at a reader."""
    assert set(REASON_WORDING) == set(EXCLUSION_REASONS)


def test_the_exposure_section_sums_the_requests_of_every_arm() -> None:
    """The run's total, not the last arm's: two arms sending 1 and 2 requests make 3."""
    page = to_markdown(study_result(uneven_arms()))
    assert (f"{TOTAL_REQUESTS} request(s) over 2 model(s), {TOTAL_BYTES} bytes in "
            "total.") in page
    assert f"{HOSTED_BYTES} bytes in total" not in page


def test_the_exposure_section_lists_what_either_arm_transmitted() -> None:
    """One arm sent template text and the other surface ids; both are named once."""
    page = to_markdown(study_result(uneven_arms()))
    for kind in PROBE_FIELDS + PLANNER_FIELDS:
        assert f"- {kind}" in page
        assert page.count(f"- {kind}") == 1


def test_the_page_renders_as_html_through_the_reports_own_converter() -> None:
    """The converter refuses constructs it cannot handle, so the whole page is rendered."""
    html = to_page(study_result(uneven_arms()), "**They disagree.**")
    assert html.startswith("<!DOCTYPE html>")
    assert f"<h1>{TITLE}</h1>" in html
    assert "<h2>Summary</h2>" in html

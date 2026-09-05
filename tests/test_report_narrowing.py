"""What the report tells a reader about a check that examined only some of its surfaces.

"How it was audited" ends on a sentence that has to be exactly right, because it
is the only place the report explains what a name in `checks_run` means. Before
task 7.4 it said a named check that reported nothing "looked and found nothing",
full stop -- and that became false the moment a check could look at three
surfaces of eleven and still be named. A reader trusting the old sentence would
read a narrowed silence as a clean result for the whole risk class.

So this file asserts three things: the caveat names `checks_narrowed` by the
field a reader would go and look at; a narrowed check is still listed as having
had something to examine; and the counts are reachable from the document the
report was rendered from. The last is not a rendering test -- it is the check
that the report's caveat points at something that is actually there.

The document is built through `build_findings_document`, the real producer, so
nothing here asserts a shape the tool does not write.
"""

from artifacts.findings_document import (
    MODEL_DISABLED, build_findings_document, coverage, model_run)
from findings_fixtures import RULE_ID, static_finding
from report import render
from report_fixtures import APP, HOW_HEADING, NOT_EXAMINED_HEADING, surfaces_document

# The field a reader is sent to. Spelled here rather than imported, because the
# caveat is prose for a human and a rename has to be a decision, not a refactor.
NARROWED_FIELD = "checks_narrowed"

SURFACES_CONSIDERED = 4
EXAMINED = 1


def narrowed_document() -> dict:
    """One findings document in which the only check that ran examined one surface of four."""
    return build_findings_document(
        [static_finding()], [],
        coverage(SURFACES_CONSIDERED, [RULE_ID], risk_classes_checked=["LLM06"]),
        model_run(MODEL_DISABLED),
        [{"check": RULE_ID, "examined_surface_count": EXAMINED,
          "eligible_surface_count": SURFACES_CONSIDERED}],
    )


def how_section(text: str) -> str:
    """Return only the "How it was audited" part, so an earlier section cannot satisfy a test."""
    return text.split(HOW_HEADING, 1)[1]


def test_the_caveat_sends_a_reader_to_the_field_that_holds_the_counts() -> None:
    """Naming the field is what makes the caveat actionable rather than a hedge."""
    text = render(APP, narrowed_document(), surfaces_document())
    assert NARROWED_FIELD in how_section(text)


def test_the_caveat_still_says_what_an_absent_check_means() -> None:
    """The older half of the sentence, which the narrowing clause must not have displaced."""
    assert "absent could not look at all" in how_section(
        render(APP, narrowed_document(), surfaces_document()))


def test_a_narrowed_check_is_still_listed_as_having_had_something_to_examine() -> None:
    """It looked, so it is named -- the caveat is what qualifies the name, not its absence."""
    text = render(APP, narrowed_document(), surfaces_document())
    assert RULE_ID in how_section(text).split("- **Risk classes covered**")[0]


def test_the_counts_the_caveat_points_at_are_in_the_document_it_rendered() -> None:
    """A caveat naming a field the document does not carry would send a reader nowhere."""
    document = narrowed_document()
    assert document[NARROWED_FIELD] == [
        {"check": RULE_ID, "examined_surface_count": EXAMINED,
         "eligible_surface_count": SURFACES_CONSIDERED}]


def test_the_caveat_is_in_the_report_of_a_run_that_narrowed_nothing_too() -> None:
    """One sentence for every run: a caveat that appeared only sometimes would read as an alert.

    It is a definition of what `checks_run` means, not a warning about this
    particular audit, so it belongs in every report or none.
    """
    unnarrowed = build_findings_document(
        [static_finding()], [], coverage(SURFACES_CONSIDERED, [RULE_ID]),
        model_run(MODEL_DISABLED))
    assert NARROWED_FIELD in how_section(render(APP, unnarrowed, surfaces_document()))


def test_the_caveat_is_in_the_how_section_rather_than_the_gap_list() -> None:
    """Guard: the two sections are next to each other, so the slice above has to be doing work."""
    text = render(APP, narrowed_document(), surfaces_document())
    gaps = text.split(NOT_EXAMINED_HEADING, 1)[1].split(HOW_HEADING, 1)[0]
    assert NARROWED_FIELD not in gaps

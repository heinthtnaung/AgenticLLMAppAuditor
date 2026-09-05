"""findings.sarif.json is byte-identical every run, with no field exempt.

This is the strongest claim the module makes, and it is stronger than
findings.json's. That file exempts `model_run.ranking` and each finding's
`narrative` from the byte comparison because a model wrote them; this one
drops both instead, so the whole document stays under the rule that every
other artifact keeps.

The volatile fields SARIF offers -- invocations, automation guids, the
artifacts array, uri base ids, ranks -- are all optional, and all of them are
either wall-clock, machine-describing or a judgement this project does not
make. Absence is what keeps two runs comparable.
"""

import json

from artifacts.findings_document import (
    MODEL_AUTHORED_DOCUMENT_FIELD,
    MODEL_AUTHORED_FINDING_FIELD,
    MODEL_USED,
    model_run,
)
from artifacts.sarif import sarif_to_json, to_sarif
from dependency_fixtures import string_values
from findings_fixtures import build_document, static_finding
from sarif_fixtures import taint_finding

MODEL = "qwen2.5-coder:7b-instruct"

# Prose only a model could have written, and the one thing in a finding that
# two runs may legitimately differ on.
NARRATIVE = "The tool hands the agent an operating-system shell, unguarded."
OTHER_NARRATIVE = "This tool exposes a shell to whatever the model decides."

# Optional SARIF fields that record when, where or by whom the run happened.
VOLATILE_RUN_FIELDS = ("invocations", "automationDetails", "artifacts", "originalUriBaseIds")

# Optional per-result fields: a fresh guid every run, and a severity score this
# project does not compute.
VOLATILE_RESULT_FIELDS = ("guid", "rank")

# Tokens that must not appear anywhere in the serialised text, nested or not.
# `uriBaseId` is where an absolute path would enter a location.
VOLATILE_SUBSTRINGS = ("invocations", "automationDetails", "originalUriBaseIds",
                       "uriBaseId", "guid", "rank", "timestamp", "suppressions")


def every_key(value: object) -> set[str]:
    """Return every object key anywhere inside a JSON-shaped value."""
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in every_key(item)}
    if isinstance(value, list):
        return {key for item in value for key in every_key(item)}
    return set()


def document_with(narrative: str) -> dict:
    """Build a two-finding document whose prose and ordering a model wrote."""
    findings = [static_finding(narrative=narrative), taint_finding(narrative=narrative)]
    ranking = [finding.id for finding in reversed(findings)]
    return build_document(findings, run=model_run(MODEL_USED, MODEL, {"seed": 0}, ranking))


def sarif_text(narrative: str = NARRATIVE) -> str:
    """Serialise the SARIF copy of that document."""
    return sarif_to_json(to_sarif(document_with(narrative)))


def test_two_conversions_of_one_document_produce_identical_bytes() -> None:
    """Same findings, same bytes: nothing in the conversion reads a clock or a machine."""
    assert sarif_text() == sarif_text()


def test_the_narrative_a_model_wrote_never_reaches_the_output() -> None:
    """The load-bearing one: no exempt field, because the exemptible field is dropped."""
    text = sarif_text()
    assert NARRATIVE not in text
    assert MODEL_AUTHORED_FINDING_FIELD not in text
    assert NARRATIVE not in string_values(json.loads(text))


def test_two_documents_differing_only_in_their_prose_serialise_identically() -> None:
    """What makes the exemption unnecessary here: prose cannot move a byte."""
    assert sarif_text(NARRATIVE) == sarif_text(OTHER_NARRATIVE)


def test_the_ordering_a_model_chose_never_reaches_the_output() -> None:
    """The other model-authored field goes the same way as the narrative."""
    assert MODEL_AUTHORED_DOCUMENT_FIELD not in sarif_text()


def test_the_run_carries_no_volatile_field_at_any_depth() -> None:
    """Each would differ between two runs of the same analysis, or describe this machine.

    Every key is searched, not just the run's own: a volatile field tucked into
    a property bag would vary exactly as much as one at the top.
    """
    run = to_sarif(document_with(NARRATIVE))["runs"][0]
    present = sorted(set(VOLATILE_RUN_FIELDS) & every_key(run))
    assert present == []


def test_no_result_carries_a_guid_or_a_rank() -> None:
    """A guid is new every run; a rank is a severity nothing in a grading key could check."""
    for result in to_sarif(document_with(NARRATIVE))["runs"][0]["results"]:
        for field in VOLATILE_RESULT_FIELDS:
            assert field not in result, field


def test_no_volatile_token_appears_anywhere_in_the_serialised_document() -> None:
    """The checks above look at keys; this one catches a token hiding in a value."""
    text = sarif_text()
    for substring in VOLATILE_SUBSTRINGS:
        assert substring not in text, substring


def test_no_absolute_path_appears_anywhere_in_the_document() -> None:
    """An absolute path is this machine's layout, which no artifact may record."""
    absolute = [value for value in string_values(json.loads(sarif_text()))
                if value.startswith("/")]
    assert absolute == []


def test_the_document_ends_with_exactly_one_newline() -> None:
    """A stable trailing newline keeps two runs diff-friendly."""
    text = sarif_text()
    assert text.endswith("\n") and not text.endswith("\n\n")

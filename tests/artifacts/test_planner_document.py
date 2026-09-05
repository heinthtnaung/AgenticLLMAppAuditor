"""What `planner.json` is allowed to say, and what it must refuse to say.

Nothing reads this file -- not the scorer, not the report, not SARIF, not VEX
(`docs/SCHEMAS.md`). That is exactly why it needs its own tests: a wrong field
here is never caught downstream, because there is no downstream. So the rules
`docs/SCHEMAS.md` publishes are asserted here or nowhere.

Two of them are easy to lose and worth naming. `order` is **never sorted** --
the order is the single fact this artifact exists to record, so a tidy-up that
sorted it would empty the file of content while leaving every field present.
And `identifier` is non-null **exactly when** `status` is `used`, in both
directions: an unnamed `used` cannot be reproduced, and a named `disabled` is a
claim about a model that never ran.

The last part of this file is the round trip. `checks/planner.py` builds the
record and this module writes it out, and until now no test passed one to the
other -- which is how a record `order_checks` would build and this document
would refuse survived review.

No model is reached: every `ask` below is a function written in this file.
"""

import json

import pytest

from artifacts.finding import SCHEMA_VERSION as FINDINGS_SCHEMA_VERSION
from artifacts.findings_document import (
    MODEL_DISABLED, MODEL_UNAVAILABLE, MODEL_USED, findings_to_json)
from artifacts.planner_document import (
    DOCUMENT_FIELDS, SCHEMA_VERSION, build_planner_document, planner_to_json)
from artifacts.surface import TOOL_CALL, Surface
from checks import planner
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.supply_chain import CHECK_NAME as SUPPLY_CHAIN_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON

# The model whose name a `used` record has to carry.
MODEL_ID = "qwen2.5-coder:7b-instruct@sha256:abc"

# Deliberately not in alphabetical order: `taint` sorts last of the three, so
# a document that sorted `order` could not return this list unchanged.
UNSORTED_ORDER = [TAINT_CHECK, SUPPLY_CHAIN_CHECK, PERMISSION_CHECK]

ELIGIBLE = [PERMISSION_CHECK, SUPPLY_CHAIN_CHECK, TAINT_CHECK]

SURFACES = [Surface(TOOL_CALL, "ShellTool", "agent.py", 12, PYTHON, "tool", "langchain.tools")]

# The one reply shape that makes the model's preference visible in the order.
REORDERING_REPLY = '{"order": ["%s", "%s"]}' % (TAINT_CHECK, PERMISSION_CHECK)


def record(status: str, order: list[str], identifier: str | None = None) -> dict:
    """A planner record shaped by hand, so the document is tested apart from the planner."""
    return {"status": status, "identifier": identifier, "order": list(order)}


def answering(reply: str):
    """An `ask` that returns one fixed reply, standing in for the model."""
    def ask(prompt: str) -> str:
        return reply
    return ask


def refusing_to_be_reached(prompt: str) -> str:
    """An `ask` that fails the way `model_client` reports an unreachable Ollama."""
    raise RuntimeError("cannot reach the local model server")


def test_a_used_status_without_an_identifier_is_refused() -> None:
    """A run that used a model without naming it cannot be reproduced."""
    with pytest.raises(ValueError, match="must name it"):
        build_planner_document(record(MODEL_USED, UNSORTED_ORDER), FINDINGS_SCHEMA_VERSION)


@pytest.mark.parametrize("status", [MODEL_UNAVAILABLE, MODEL_DISABLED])
def test_a_status_that_did_not_use_a_model_may_not_name_one(status: str) -> None:
    """A named `disabled` or `unavailable` is a claim about a model that never ran."""
    with pytest.raises(ValueError, match="must not name a model"):
        build_planner_document(record(status, UNSORTED_ORDER, MODEL_ID), FINDINGS_SCHEMA_VERSION)


def test_an_unknown_status_is_refused() -> None:
    """An invented status reaches a reader as a claim about how the order was chosen."""
    with pytest.raises(ValueError, match="unknown planner status 'guessed'"):
        build_planner_document(record("guessed", UNSORTED_ORDER), FINDINGS_SCHEMA_VERSION)


def test_the_order_is_copied_rather_than_aliased() -> None:
    """The document holds its own list, so the caller cannot edit the artifact after building it."""
    planner_run = record(MODEL_DISABLED, UNSORTED_ORDER)
    document = build_planner_document(planner_run, FINDINGS_SCHEMA_VERSION)
    planner_run["order"].append("invented")
    assert document["order"] == UNSORTED_ORDER


def test_the_order_is_never_sorted() -> None:
    """The order is the fact this artifact records: sorted, the file would say nothing."""
    document = build_planner_document(
        record(MODEL_DISABLED, UNSORTED_ORDER), FINDINGS_SCHEMA_VERSION)
    assert document["order"] == UNSORTED_ORDER
    assert document["order"] != sorted(UNSORTED_ORDER)


def test_the_keys_are_exactly_the_documented_fields_in_the_documented_order() -> None:
    """`DOCUMENT_FIELDS` is what a reader is promised, so the document has to match it."""
    document = build_planner_document(
        record(MODEL_USED, UNSORTED_ORDER, MODEL_ID), FINDINGS_SCHEMA_VERSION)
    assert tuple(document) == DOCUMENT_FIELDS


def test_the_documented_fields_are_the_seven_the_schema_lists() -> None:
    """Guard: an emptied tuple would make the key-order test pass over nothing."""
    assert len(DOCUMENT_FIELDS) == 7


def test_the_schema_version_is_two() -> None:
    """Its own version, independent of findings.json's, and a reader is told which.

    Version 2 added `surface_selection` and `refused_narrowing`. The two files
    moved in the same change and to different numbers, which is the point of
    versioning them apart.
    """
    document = build_planner_document(record(MODEL_DISABLED, ELIGIBLE), FINDINGS_SCHEMA_VERSION)
    assert document["schema_version"] == SCHEMA_VERSION == 2


def test_the_findings_schema_version_is_the_one_passed_in() -> None:
    """What invalidates this file, in place of a timestamp -- so it is recorded, not assumed."""
    document = build_planner_document(record(MODEL_DISABLED, ELIGIBLE), 99)
    assert document["findings_schema_version"] == 99


def test_a_used_record_keeps_the_model_that_chose_the_order() -> None:
    """Which model ordered the audit is part of reproducing the audit."""
    document = build_planner_document(
        record(MODEL_USED, UNSORTED_ORDER, MODEL_ID), FINDINGS_SCHEMA_VERSION)
    assert document["identifier"] == MODEL_ID


def test_a_disabled_record_names_no_model() -> None:
    """`identifier` is present and null rather than absent: the field is required either way."""
    document = build_planner_document(record(MODEL_DISABLED, ELIGIBLE), FINDINGS_SCHEMA_VERSION)
    assert document["identifier"] is None


def test_a_disabled_run_round_trips_from_the_planner_into_the_document() -> None:
    """`ask=None` builds a record the document accepts, with the planned order intact."""
    _, planner_run = planner.order_checks(SURFACES, ELIGIBLE)
    document = build_planner_document(planner_run, FINDINGS_SCHEMA_VERSION)
    assert document["status"] == MODEL_DISABLED
    assert document["identifier"] is None
    assert document["order"] == ELIGIBLE


def test_an_unavailable_run_round_trips_from_the_planner_into_the_document() -> None:
    """An unreachable model builds a record the document accepts, naming no model."""
    _, planner_run = planner.order_checks(
        SURFACES, ELIGIBLE, refusing_to_be_reached, MODEL_ID)
    document = build_planner_document(planner_run, FINDINGS_SCHEMA_VERSION)
    assert document["status"] == MODEL_UNAVAILABLE
    assert document["identifier"] is None
    assert document["order"] == ELIGIBLE


def test_a_used_run_round_trips_from_the_planner_into_the_document() -> None:
    """The case the two modules disagreed about: a `used` record must carry its model.

    `order_checks` once built `used` records with no identifier, which
    `build_planner_document` then refused -- an audit that failed only when it
    tried to write its artifact. Nothing joined the two modules, so nothing saw it.
    """
    _, planner_run = planner.order_checks(
        SURFACES, ELIGIBLE, answering(REORDERING_REPLY), MODEL_ID)
    document = build_planner_document(planner_run, FINDINGS_SCHEMA_VERSION)
    assert document["status"] == MODEL_USED
    assert document["identifier"] == MODEL_ID
    assert document["order"] == [TAINT_CHECK, PERMISSION_CHECK, SUPPLY_CHAIN_CHECK]


# --- the on-disk form -------------------------------------------------------

def written(status: str = MODEL_DISABLED, identifier: str | None = None) -> str:
    """Serialise one planner document the way the audit writes it to disk."""
    return planner_to_json(
        build_planner_document(record(status, UNSORTED_ORDER, identifier),
                               FINDINGS_SCHEMA_VERSION))


def test_the_serialisation_is_the_one_every_other_artifact_uses() -> None:
    """Delegated, not re-implemented: two serialisers is how two of them start disagreeing."""
    document = build_planner_document(
        record(MODEL_DISABLED, UNSORTED_ORDER), FINDINGS_SCHEMA_VERSION)
    assert planner_to_json(document) == findings_to_json(document)


def test_the_written_keys_are_sorted_however_the_document_lists_them() -> None:
    """The reading order is the document's; the on-disk order is alphabetical, like the rest."""
    assert list(json.loads(written())) == sorted(DOCUMENT_FIELDS)


def test_the_written_form_is_indented_two_spaces() -> None:
    """A diff on this file has to show content rather than one reflowed line."""
    assert '\n  "status": "disabled"' in written()


def test_the_written_form_ends_with_exactly_one_newline() -> None:
    """Every artifact this project writes ends the same way, so a diff shows no phantom line."""
    text = written()
    assert text.endswith("}\n")
    assert not text.endswith("\n\n")


def test_the_written_order_survives_the_round_trip_unsorted() -> None:
    """`sort_keys` sorts the keys and must never reach the one list whose order is the point."""
    assert json.loads(written())["order"] == UNSORTED_ORDER


def test_a_used_document_writes_the_model_that_chose_the_order() -> None:
    """The identifier is what makes the run repeatable, so it has to reach the file."""
    assert json.loads(written(MODEL_USED, MODEL_ID))["identifier"] == MODEL_ID

"""Reading the explanation projection back: the no-entry note, and fields refused when malformed."""

import json

import pytest

from full_runs import fully_assessed
from report.json_explanation import NOT_RECORDED
from report.json_report import as_json
from report.load_explanation import unrecorded
from report.load_json import ReportJsonFault
from report.load_report import report_from_json


def explained_document() -> dict:
    """Give the JSON of a record whose sources were explained, to corrupt one item at a time."""
    return json.loads(as_json(fully_assessed()))


def test_an_unrecorded_note_names_no_model_or_dropped_item():
    # A finding a council ran on but kept no explanation for writes the bare note; one that
    # also names a model or a dropped item is a kept record, not the no-entry note.
    assert unrecorded({"assessed": False, "because": NOT_RECORDED}) is True
    assert unrecorded({"assessed": False, "because": NOT_RECORDED, "model": "m"}) is False
    with_dropped = {"assessed": False, "because": NOT_RECORDED, "dropped_items": [{"metric": "C"}]}
    assert unrecorded(with_dropped) is False


def test_an_explained_item_missing_its_evidence_flag_is_refused():
    document = explained_document()
    del document["findings"][0]["llm_explanation"]["items"][0]["evidence_verified"]
    with pytest.raises(ReportJsonFault, match="evidence_verified"):
        report_from_json(document, "report.json")

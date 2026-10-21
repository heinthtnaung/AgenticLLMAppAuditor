"""Reading the organisation risk back: the answers it is recomputed from, refused when malformed."""

import json

import pytest

from full_runs import fully_assessed
from report.json_report import as_json
from report.load_json import ReportJsonFault
from report.load_report import report_from_json


def scored_document() -> dict:
    """Give the JSON of a record that was scored, to corrupt one field of its risk at a time."""
    return json.loads(as_json(fully_assessed()))


def test_an_answer_that_is_no_answer_is_refused():
    document = scored_document()
    categories = document["findings"][0]["organisation_risk"]["categories"]
    categories["exposure"]["answers"][0]["answer"] = "Maybe"
    with pytest.raises(ReportJsonFault, match="an answer is"):
        report_from_json(document, "report.json")


def test_a_category_that_is_not_an_object_is_refused():
    document = scored_document()
    document["findings"][0]["organisation_risk"]["categories"]["exposure"] = []
    with pytest.raises(ReportJsonFault, match="categories.exposure must be a JSON object"):
        report_from_json(document, "report.json")


def test_an_answer_naming_no_question_is_refused():
    document = scored_document()
    exposure = document["findings"][0]["organisation_risk"]["categories"]["exposure"]
    del exposure["answers"][0]["question_id"]
    with pytest.raises(ReportJsonFault, match="question_id"):
        report_from_json(document, "report.json")

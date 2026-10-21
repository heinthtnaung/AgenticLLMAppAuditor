"""Reading a finding back: its component and advisory, refused when a field is malformed."""

import json

import pytest

from full_runs import fully_assessed
from report.json_report import as_json
from report.load_json import ReportJsonFault
from report.load_report import report_from_json


def finding_document() -> dict:
    """Give the JSON of a record with one finding, to corrupt one of its fields at a time."""
    return json.loads(as_json(fully_assessed()))


def test_a_component_missing_its_name_is_refused():
    document = finding_document()
    del document["findings"][0]["component"]["name"]
    with pytest.raises(ReportJsonFault, match="component has no 'name'"):
        report_from_json(document, "report.json")


def test_a_component_whose_locations_are_not_a_list_is_refused():
    document = finding_document()
    document["findings"][0]["component"]["locations"] = "requirements.txt"
    with pytest.raises(ReportJsonFault, match="locations must be a JSON list"):
        report_from_json(document, "report.json")


def test_an_advisory_missing_its_id_is_refused():
    document = finding_document()
    del document["findings"][0]["advisory"]["advisory_id"]
    with pytest.raises(ReportJsonFault, match="advisory_id"):
        report_from_json(document, "report.json")

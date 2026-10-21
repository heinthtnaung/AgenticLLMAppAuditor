"""Reading the run's provenance back: its fields, refused when one is missing or malformed."""

import json

import pytest

from full_runs import fully_assessed
from report.json_report import as_json
from report.load_json import ReportJsonFault
from report.load_report import report_from_json
from report_pages import report_with_models


def plain_document() -> dict:
    """Give the JSON of a record whose run named no council, for the simple provenance fields."""
    return json.loads(as_json(fully_assessed()))


def models_document() -> dict:
    """Give the JSON of a record whose run named local models, for the local-models fields."""
    return json.loads(as_json(report_with_models()))


def test_a_run_missing_its_repository_is_refused():
    document = plain_document()
    del document["run"]["repository"]
    with pytest.raises(ReportJsonFault, match="run has no 'repository'"):
        report_from_json(document, "report.json")


def test_a_component_count_that_is_not_a_count_is_refused():
    document = plain_document()
    document["run"]["component_count"] = "many"
    with pytest.raises(ReportJsonFault, match="component_count must be a non-negative integer"):
        report_from_json(document, "report.json")


def test_an_advisory_database_missing_its_reason_is_refused():
    document = plain_document()
    document["run"]["advisory_database"] = {"known": False}
    with pytest.raises(ReportJsonFault, match="advisory_database has no 'reason'"):
        report_from_json(document, "report.json")


def test_a_local_models_seed_that_is_not_a_number_is_refused():
    document = models_document()
    document["run"]["local_models"]["seed"] = "eleven"
    with pytest.raises(ReportJsonFault, match="seed must be a number"):
        report_from_json(document, "report.json")

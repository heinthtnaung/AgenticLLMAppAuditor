"""Reading the council projection back: its variants, and the fields refused when malformed."""

import json

import pytest

from full_runs import fully_assessed
from report.json_report import as_json
from report.load_council import order_values_from
from report.load_json import ReportJsonFault
from report.load_report import report_from_json


def council_document() -> dict:
    """Give the JSON of a record a council assessed, to corrupt one council field at a time."""
    return json.loads(as_json(fully_assessed()))


def test_an_orders_object_missing_a_value_is_refused():
    # `members[0].orders: {}` once raised a bare KeyError; now it is named and refused.
    document = council_document()
    document["findings"][0]["council"]["metrics"][0]["members"][0]["orders"] = {}
    with pytest.raises(ReportJsonFault, match="orders"):
        report_from_json(document, "report.json")


def test_a_metric_outcome_that_is_no_outcome_is_refused():
    document = council_document()
    document["findings"][0]["council"]["metrics"][0]["outcome"] = "bogus"
    with pytest.raises(ValueError, match="bogus"):
        report_from_json(document, "report.json")


def test_order_values_are_read_when_present_and_empty_otherwise():
    assert order_values_from(None, "council[X].metrics[0].members[0]") == ()
    both = {"in_order": "N", "reversed": "A"}
    assert order_values_from(both, "council[X].metrics[0].members[0]") == ("N", "A")


def test_an_orders_object_that_is_not_an_object_is_refused():
    with pytest.raises(ReportJsonFault, match="orders must be a JSON object"):
        order_values_from([], "council[X].metrics[0].members[0]")

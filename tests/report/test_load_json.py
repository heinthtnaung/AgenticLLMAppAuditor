"""The boundary checks every loader shares: a malformed field is refused, not followed."""

import pytest

from report.load_json import (
    ReportJsonFault,
    as_list,
    as_object,
    require,
    required_number,
    required_object,
)


def test_an_object_of_another_shape_is_refused_by_where_it_sits():
    with pytest.raises(ReportJsonFault, match="run must be a JSON object"):
        as_object([], "run")


def test_a_list_of_another_shape_is_refused_by_where_it_sits():
    with pytest.raises(ReportJsonFault, match="findings must be a JSON list"):
        as_list({}, "findings")


def test_a_missing_required_field_is_named():
    with pytest.raises(ReportJsonFault, match="run has no 'repository'"):
        require({}, "repository", "run")


def test_a_required_object_that_is_not_one_is_refused():
    with pytest.raises(ReportJsonFault, match="run.advisory_database must be a JSON object"):
        required_object({"advisory_database": 3}, "advisory_database", "run")


def test_a_number_field_passes_an_int_through_unchanged():
    # Not coerced: a pinned temperature of 0 must stay 0, or it re-renders as 0.0.
    assert required_number({"temperature": 0}, "temperature", "run") == 0
    assert isinstance(required_number({"temperature": 0}, "temperature", "run"), int)


def test_a_boolean_is_not_a_number():
    with pytest.raises(ReportJsonFault, match="must be a number"):
        required_number({"seed": True}, "seed", "run")


def test_a_string_is_not_a_number():
    with pytest.raises(ReportJsonFault, match="must be a number"):
        required_number({"seed": "7"}, "seed", "run")

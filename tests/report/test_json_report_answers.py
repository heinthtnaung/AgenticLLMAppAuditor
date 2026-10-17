"""Guards on where a typed run's answers came from, recorded in the audit artefact's run block."""

from dataclasses import replace

from report.json_report import as_dictionary
from report.record import build_report
from report_samples import PROVENANCE, catalogue, component

TYPED = "typed at the prompt and saved to reports/x.answers.json"


def run_block(provenance) -> dict:
    """Build a report with the given provenance and read its run block back."""
    return as_dictionary(build_report(provenance, catalogue(component()), (), {}))["run"]


def test_answers_from_a_file_or_none_leave_no_answers_source_in_the_record():
    # A file run and a run with no answers carry no answers_source, so the key is absent.
    assert "answers_source" not in run_block(PROVENANCE)


def test_a_typed_run_records_where_its_answers_came_from():
    assert run_block(replace(PROVENANCE, answers_source=TYPED))["answers_source"] == TYPED

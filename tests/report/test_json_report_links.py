"""Guards on an advisory's own page in the audit artefact: carried, and null when there is none."""

import json

from report.json_report import as_json
from report.record import build_report
from report_samples import ADVISORY_URL, PROVENANCE, catalogue, component, finding

DJANGO = component()


def advisory_written(**advisory_overrides) -> dict:
    """Write one finding's record and read its advisory back from the JSON."""
    raised = (finding(DJANGO, **advisory_overrides),)
    record = json.loads(as_json(build_report(PROVENANCE, catalogue(DJANGO), raised, {})))
    return record["findings"][0]["advisory"]


def test_the_record_carries_the_page_trivy_names_for_an_advisory():
    assert advisory_written(url=ADVISORY_URL)["url"] == ADVISORY_URL


def test_an_advisory_with_no_page_is_written_null_and_never_an_empty_link():
    # Present and null, like a fix nobody published: a missing key reads as a
    # record from before the field existed, and "" reads as a link.
    written = advisory_written()
    assert "url" in written and written["url"] is None

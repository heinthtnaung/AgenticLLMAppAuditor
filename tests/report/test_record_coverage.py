"""Guards on what the record says a run could not read: every manifest, named first."""

from full_runs import fully_assessed
from report.record import NOTHING_ABSENT, UNREAD_MANIFEST, Coverage, build_report
from report.text_report import as_text
from report_samples import PROVENANCE, catalogue

UNREAD = ("frontend/package.json", "package.json")
WHAT_A_BARE_RUN_LEAVES_OUT = ["Organisation Risk Score", "Approval record", "Council ruling"]


def test_each_manifest_nothing_was_read_from_is_named_first_with_why():
    unread = Coverage(unread_manifests=UNREAD)
    report = build_report(PROVENANCE, catalogue(), (), {}, coverage=unread)
    named = [(one.what, one.because) for one in report.not_assessed]
    assert named[:2] == [(path, UNREAD_MANIFEST) for path in UNREAD]
    assert [one for one, _ in named[2:]] == WHAT_A_BARE_RUN_LEAVES_OUT


def test_the_record_keeps_the_manifests_it_could_not_read():
    report = fully_assessed(Coverage(unread_manifests=UNREAD))
    assert report.coverage.unread_manifests == UNREAD


def test_a_run_that_assessed_everything_else_still_names_an_unread_manifest():
    # "Nothing" under the heading would be the one thing the section exists to prevent.
    report = fully_assessed(Coverage(unread_manifests=("package.json",)))
    assert [one.what for one in report.not_assessed] == ["package.json"]
    assert NOTHING_ABSENT not in as_text(report)

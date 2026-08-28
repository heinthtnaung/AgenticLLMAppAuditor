"""Why a key entry went unanswered, derived from the artifacts and nothing else.

Each reason is asserted twice where it can be: once on an input that produces
it, once on the same input with the one fact changed that produces a different
reason. A reason that cannot be changed by changing an artifact would be a
hardcoded excuse, which is exactly what the scorer must not hold.
"""

from artifacts.finding import (
    COMPONENT_SUBJECT,
    CONFIRMED,
    INCONCLUSIVE,
    SURFACE_SUBJECT,
    Probe,
)
from evaluation.scorer import (
    CHECKED_AND_SILENT,
    FILE_SKIPPED,
    NO_CHECK_FOR_RISK_CLASS,
    PROBE_UNRESOLVED,
    SURFACE_NOT_EXTRACTED,
    score_app,
)
from evaluation_fixtures import (
    APP,
    FILE,
    KEY_ID,
    PROBE_NAME,
    PROBE_REASON,
    findings_document,
    grading_key,
    key_entry,
    surfaces_document,
    unresolved_probe,
)
from findings_fixtures import OWASP_ID, SURFACE_ID

# A class the fixture's one check cannot report, used to switch a reason on and off.
UNCHECKED_CLASS = "LLM02"

# A component probe subject. A purl carries colons but no line number, so it is
# what a scorer that guessed at the id shape instead of reading `subject_kind`
# would crash on.
COMPONENT_PURL = "pkg:pypi/pyyaml@6.0"
COMPONENT_PROBE_NAME = "advisory_lookup"
COMPONENT_PROBE_REASON = "model_unavailable"


def miss(entry: dict, document: dict, surfaces: dict | None = None) -> dict:
    """Score one unanswered key entry and return the single miss it produces."""
    scored = score_app(APP, grading_key([entry]), document,
                       surfaces if surfaces is not None else surfaces_document())
    assert len(scored["misses"]) == 1, scored["misses"]
    return scored["misses"][0]


def test_the_reason_vocabulary_is_the_one_the_schema_documents() -> None:
    """The five strings are a contract with the write-up, not internal names."""
    assert (NO_CHECK_FOR_RISK_CLASS, CHECKED_AND_SILENT, PROBE_UNRESOLVED,
            SURFACE_NOT_EXTRACTED, FILE_SKIPPED) == (
        "no_check_for_risk_class", "checked_and_silent", "probe_unresolved",
        "surface_not_extracted", "file_skipped")


def test_a_class_no_check_can_report_is_a_miss_of_coverage() -> None:
    """`risk_classes_checked` is what separates "not looked for" from "not found"."""
    entry = key_entry(owasp_id=UNCHECKED_CLASS)
    assert miss(entry, findings_document())["reason"] == NO_CHECK_FOR_RISK_CLASS


def test_the_same_entry_is_checked_and_silent_once_a_check_covers_its_class() -> None:
    """One field of one artifact changes, and the reason changes with it.

    This is the pair that shows the reason is derived: the key entry, the
    findings and the scan are identical in both tests.
    """
    entry = key_entry(owasp_id=UNCHECKED_CLASS)
    document = findings_document(risk_classes=(OWASP_ID, UNCHECKED_CLASS))
    assert miss(entry, document)["reason"] == CHECKED_AND_SILENT


def test_a_graded_file_the_scan_could_not_read_is_reported_as_skipped() -> None:
    """The checks never saw the file, so their silence about it means nothing."""
    scan = surfaces_document(files=(), skipped=(FILE,))
    assert miss(key_entry(), findings_document(), scan)["reason"] == FILE_SKIPPED


def test_a_skipped_file_outranks_the_coverage_reason() -> None:
    """An unread file is the earlier failure: no check could have run on it at all."""
    entry = key_entry(owasp_id=UNCHECKED_CLASS)
    scan = surfaces_document(files=(), skipped=(FILE,))
    assert miss(entry, findings_document(), scan)["reason"] == FILE_SKIPPED


def test_a_file_read_with_no_surface_extracted_is_reported_as_such() -> None:
    """The extractor is upstream of the checks, so its gap is named as its own."""
    scan = surfaces_document(files=())
    assert miss(key_entry(), findings_document(), scan)["reason"] == SURFACE_NOT_EXTRACTED


def test_a_probe_that_gave_up_on_the_surface_is_reported_as_unresolved() -> None:
    """Work was attempted and did not conclude, which is not the same as silence."""
    document = findings_document(probes=[unresolved_probe()])
    assert miss(key_entry(), document)["reason"] == PROBE_UNRESOLVED


def test_a_probe_that_concluded_leaves_the_entry_merely_silent() -> None:
    """Only an unresolved probe is a reason; a confirmed one is not an excuse."""
    concluded = Probe(PROBE_NAME, SURFACE_SUBJECT, SURFACE_ID, CONFIRMED, "it holds a shell")
    document = findings_document(probes=[concluded])
    assert miss(key_entry(), document)["reason"] == CHECKED_AND_SILENT


def test_a_component_probe_is_never_read_as_a_surface_anchor() -> None:
    """Probes are selected by `subject_kind`: a purl holds colons but names no line.

    Scoring at all is half the assertion. Splitting this subject id on colons
    raises, so the entry is only reached because the filter kept the probe out.
    """
    component = Probe(COMPONENT_PROBE_NAME, COMPONENT_SUBJECT, COMPONENT_PURL, INCONCLUSIVE,
                      "the local model was not reachable", COMPONENT_PROBE_REASON)
    reported = miss(key_entry(), findings_document(probes=[component]))
    assert (reported["reason"], reported["probe_reason"]) == (CHECKED_AND_SILENT, None)


def test_a_probe_reason_is_reported_alongside_the_primary_reason() -> None:
    """Two facts about one miss: no check covers the class, and the trace stopped too."""
    entry = key_entry(owasp_id=UNCHECKED_CLASS)
    reported = miss(entry, findings_document(probes=[unresolved_probe()]))
    assert (reported["reason"], reported["probe_reason"]) == (NO_CHECK_FOR_RISK_CLASS,
                                                              PROBE_REASON)


def test_no_probe_reason_is_invented_when_no_probe_ran() -> None:
    """`probe_reason` is null rather than absent, so a reader can see nothing was tried."""
    assert miss(key_entry(), findings_document())["probe_reason"] is None


def test_a_probe_on_another_surface_is_not_this_entrys_reason() -> None:
    """Probes are joined by file and line, never by the fact that one exists."""
    elsewhere = unresolved_probe("app/other.py:99:TOOL_CALL:OtherTool")
    reported = miss(key_entry(), findings_document(probes=[elsewhere]))
    assert (reported["reason"], reported["probe_reason"]) == (CHECKED_AND_SILENT, None)


def test_every_miss_names_the_entry_and_its_risk_class() -> None:
    """A miss a reader cannot look up in the key is a number with no evidence."""
    reported = miss(key_entry(), findings_document())
    assert (reported["key_id"], reported["owasp_id"]) == (KEY_ID, OWASP_ID)


def test_misses_are_sorted_by_key_id() -> None:
    """Sorted, so the same two artifacts always score to the same bytes."""
    key = grading_key([key_entry(id="TINY-09"), key_entry(id="TINY-02")])
    scored = score_app(APP, key, findings_document(), surfaces_document())
    assert [reported["key_id"] for reported in scored["misses"]] == ["TINY-02", "TINY-09"]

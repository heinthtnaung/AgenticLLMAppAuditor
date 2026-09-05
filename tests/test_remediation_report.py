"""remediation.md's frame: who wrote the advice, how much of it there is, and when none was.

The provenance line is the part a reader six months on depends on -- a tag
alone names a different build after the next pull, so the short digest and the
decode settings are on the same line as the model's name. It is absent when no
model ran, because the "no advice was written" block says that more usefully
and two lines making one point read as a stutter.

Two report-wide lines join it here. The same provenance line carries what
grounded the advice, so "whose words are these" and "based on what" arrive in
one breath; and the licence note closes the report, because passages quoted
from someone else's repository oblige it to name their terms once.
"""

import json

from artifacts.remediation import NAMES_APP_IDENTIFIER, NO_INDEX, OWASP_CHEATSHEETS
from findings_fixtures import build_document, static_finding
from remediation_fixtures import (
    MODEL,
    indexed_knowledge,
    rejected_entry,
    remediation_document,
    source,
    unavailable_entry,
    unavailable_run,
    used_run,
    written_entry,
)
from remediation_report import (
    DIGEST_CHARS,
    LICENCE_NOTE,
    NO_MODEL,
    NOTHING_TO_FIX,
    render,
    render_from_files,
)
from retrieval.manifest import SOURCES
from cli_helpers import STUB_MODEL_DIGEST

APP = "vulnerable-support-agent"

# What a grounded fixture pins, and the prefix of the digest a reader is shown:
# the block is built by `indexed_knowledge`, so neither is spelled twice.
GROUNDED = indexed_knowledge()
SHORT_MANIFEST = GROUNDED["manifest_digest"].removeprefix("sha256:")[:DIGEST_CHARS]

# The licence note as the report renders it for the one registered source.
CHEATSHEET_LICENCE = SOURCES[OWASP_CHEATSHEETS].license
LICENCE_LINE = LICENCE_NOTE.format(names=OWASP_CHEATSHEETS, licences=CHEATSHEET_LICENCE)

# How the provenance line opens. Asserted on directly because its absence is a
# property in its own right, and "the model's name is missing" is too weak a
# test: a line naming no model at all would still satisfy it.
PROVENANCE_OPENER = "Advice written by"


def findings_and_ids() -> tuple[dict, list[str]]:
    """Build two findings through their real producer, and hand back their ids."""
    document = build_document([static_finding(), static_finding(rule_id="other_rule")])
    return document, [finding["finding_id"] for finding in document["findings"]]


def test_the_report_opens_with_a_heading_naming_the_app() -> None:
    """A truncated file would still be written, so the heading says it was rendered."""
    findings, ids = findings_and_ids()
    text = render(APP, remediation_document([written_entry(one) for one in ids]), findings)
    assert text.startswith(f"# How to fix what was found: {APP}")


def provenance_line(digest: str | None = STUB_MODEL_DIGEST) -> str:
    """Render a report from a run that reached the server, and return its third line."""
    findings, ids = findings_and_ids()
    document = remediation_document([written_entry(one) for one in ids], used_run(digest))
    return render(APP, document, findings).splitlines()[2]


def test_the_provenance_line_names_the_model_that_wrote_the_advice() -> None:
    """A reader has to know whose words these are before weighing them."""
    assert f"`{MODEL}`" in provenance_line()


def test_the_provenance_line_names_the_models_short_digest() -> None:
    """A tag is mutable, so the build is identified the way a short commit hash does."""
    assert f"build `{STUB_MODEL_DIGEST[:DIGEST_CHARS]}`" in provenance_line()


def test_the_provenance_line_shortens_the_digest_rather_than_printing_all_of_it() -> None:
    """The full digest is noise in a sentence; the prefix is what identifies the build."""
    assert STUB_MODEL_DIGEST not in provenance_line()


def test_the_provenance_line_names_the_decode_settings_that_were_sent() -> None:
    """Repeatable prose rests on the settings, so they are rendered beside the model."""
    assert "seed 0, temperature 0" in provenance_line()


def test_the_provenance_line_says_when_no_build_was_recorded() -> None:
    """An unrecorded digest is stated as one; silence would read as a digest nobody checked."""
    assert "build not recorded" in provenance_line(None)


def grounded_provenance_line() -> str:
    """Render a report whose advice was grounded on a passage, and return its third line."""
    findings, ids = findings_and_ids()
    document = remediation_document([written_entry(one, sources=[source()]) for one in ids])
    return render(APP, document, findings).splitlines()[2]


def test_the_provenance_line_says_what_grounded_the_advice_when_an_index_was_read() -> None:
    """A reader weighing the prose needs the passages behind it named beside the model.

    On the same line rather than below it: the provenance line has a fixed
    place in the report, and a second line would compete with it.
    """
    line = grounded_provenance_line()
    assert f"grounded on {GROUNDED['source_count']} knowledge source(s)" in line
    assert f"`{GROUNDED['embed_model']}`" in line
    assert f"manifest `{SHORT_MANIFEST}`" in line


def test_the_provenance_line_shortens_the_manifest_digest_rather_than_printing_all_of_it() -> None:
    """The same treatment the model's build gets, for the same reason: a digest is not prose."""
    assert GROUNDED["manifest_digest"] not in grounded_provenance_line()


def test_the_provenance_line_gives_the_reason_when_nothing_grounded_the_advice() -> None:
    """Ungrounded advice must say so and why, not merely omit the clause that would."""
    line = provenance_line()
    assert NO_INDEX in line
    assert "No knowledge base was retrieved from" in line


def test_the_licence_note_closes_the_report_and_names_what_was_cited() -> None:
    """Quoting someone else's passages obliges the report to name them and their terms."""
    findings, ids = findings_and_ids()
    document = remediation_document(
        [written_entry(ids[0], sources=[source()]), written_entry(ids[1])])
    assert render(APP, document, findings).splitlines()[-1] == LICENCE_LINE


def test_the_licence_note_is_written_once_however_many_entries_cited_a_passage() -> None:
    """It covers the whole report, so a copy per citing entry would be a stutter."""
    findings, ids = findings_and_ids()
    document = remediation_document([written_entry(one, sources=[source()]) for one in ids])
    assert render(APP, document, findings).count(LICENCE_LINE) == 1


def test_no_licence_note_is_written_when_no_entry_cited_anything() -> None:
    """A licence named over nothing quoted would claim a grounding the run did not have."""
    findings, ids = findings_and_ids()
    text = render(APP, remediation_document([written_entry(one) for one in ids]), findings)
    assert LICENCE_LINE not in text
    assert CHEATSHEET_LICENCE not in text


def unreached_report() -> str:
    """Render the report a run with no model reachable produces."""
    findings, ids = findings_and_ids()
    document = remediation_document([unavailable_entry(one) for one in ids], unavailable_run())
    return render(APP, document, findings)


def test_no_provenance_line_is_rendered_when_no_model_ran() -> None:
    """Naming a model that wrote nothing would credit it with the empty page below."""
    text = unreached_report()
    assert PROVENANCE_OPENER not in text
    assert MODEL not in text
    assert "build not recorded" not in text


def test_the_no_model_block_stands_where_the_provenance_line_would_have() -> None:
    """No line is left empty in its place, so the block is the third line of the report."""
    assert unreached_report().splitlines()[2] == NO_MODEL


def test_a_run_with_no_model_says_so_once_and_plainly() -> None:
    """One block covers it, and it says nothing was substituted in the model's place."""
    text = unreached_report()
    assert NO_MODEL in text
    assert text.count(NO_MODEL) == 1


def test_the_no_model_block_is_absent_when_a_model_did_run() -> None:
    """It is the alternative to the provenance line, never a companion to it."""
    findings, ids = findings_and_ids()
    document = remediation_document([written_entry(one) for one in ids])
    assert NO_MODEL not in render(APP, document, findings)


def test_the_summary_says_how_many_findings_carry_advice() -> None:
    """A reader sees the shortfall without counting the sections below."""
    findings, ids = findings_and_ids()
    document = remediation_document(
        [written_entry(ids[0]), rejected_entry(ids[1], NAMES_APP_IDENTIFIER)])
    assert "1 of 2 findings carry advice" in render(APP, document, findings)


def test_the_summary_explains_the_refusals() -> None:
    """A missing section is explained where it is counted, not left to be inferred."""
    findings, ids = findings_and_ids()
    document = remediation_document(
        [written_entry(ids[0]), rejected_entry(ids[1], NAMES_APP_IDENTIFIER)])
    assert "1 were refused" in render(APP, document, findings)


def test_the_summary_counts_the_findings_never_attempted() -> None:
    """Refused and never attempted are counted apart, as they are stored apart."""
    assert "2 were not attempted" in unreached_report()


def test_a_document_with_no_advice_says_there_is_nothing_to_fix() -> None:
    """No findings is not a clean bill, and the line says which report carries the caveat."""
    text = render(APP, remediation_document([]), build_document([]))
    assert NOTHING_TO_FIX in text
    assert "see the audit report" in text


def test_rendering_the_same_document_twice_is_byte_identical() -> None:
    """The report is a rendering, so it must add nothing that varies between calls."""
    findings, ids = findings_and_ids()
    document = remediation_document([written_entry(one) for one in ids])
    assert render(APP, document, findings) == render(APP, document, findings)


def test_rendering_from_files_matches_rendering_from_the_documents(tmp_path) -> None:
    """The two artifacts on disk are its only inputs, so reading them back must agree."""
    findings, ids = findings_and_ids()
    document = remediation_document([written_entry(one) for one in ids])
    remediation_path = tmp_path / "remediation.json"
    findings_path = tmp_path / "findings.json"
    remediation_path.write_text(json.dumps(document), encoding="utf-8")
    findings_path.write_text(json.dumps(findings), encoding="utf-8")
    assert render_from_files(APP, remediation_path, findings_path) == render(
        APP, document, findings)

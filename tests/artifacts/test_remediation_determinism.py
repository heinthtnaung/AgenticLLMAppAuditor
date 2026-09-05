"""Determinism in three tiers: the skeleton repeats, the words do not.

`strip_advice_text` is the sibling of `strip_model_authored`. It removes what
the model decided -- the words, and the statuses derived from them -- and what
survives is asserted byte-identical across runs that got different answers. The
degraded case is stronger: with no model reached, tier (b) collapses to a
constant and the whole file repeats exactly.
"""

from artifacts.remediation import (
    CODE_FENCE_IN_GUIDANCE,
    NAMES_APP_IDENTIFIER,
    remediation_to_json,
    strip_advice_text,
)
from remediation_fixtures import (
    indexed_knowledge,
    rejected_entry,
    remediation_document,
    source,
    unavailable_entry,
    unavailable_run,
    snippet,
    written_entry,
)

FIRST = "a.py:1:TOOL_CALL:First:high_privilege_tool"
SECOND = "b.py:2:TOOL_CALL:Second:high_privilege_tool"

# Two answers to the same two findings: one run the model passed on both, one
# where its answer was refused twice for different reasons.
OTHER_GUIDANCE = "Bound what the agent may reach, and log every call it makes."

# The fields the strip removes: what a model's answer decided, directly or by
# derivation, plus `sources` -- tool-written rather than model-decided, but
# carried only beside a written answer, so it comes and goes with one.
STRIPPED_FIELDS = ("status", "reason", "rejected_on", "guidance", "snippets", "sources")

# A second passage, so two runs can be given different citations to strip.
OTHER_SOURCE_PATH = "cheatsheets/Other_Cheat_Sheet.md"
OTHER_SOURCE_URL = "https://cheatsheetseries.owasp.org/cheatsheets/Other_Cheat_Sheet.html"


def accepted_run() -> dict:
    """A run whose answers both passed the contract."""
    return remediation_document([written_entry(FIRST), written_entry(SECOND)])


def refused_run() -> dict:
    """The same two findings, with both answers refused for different reasons."""
    return remediation_document([
        rejected_entry(FIRST, NAMES_APP_IDENTIFIER),
        rejected_entry(SECOND, CODE_FENCE_IN_GUIDANCE, "guidance"),
    ])


def test_stripping_removes_every_field_that_follows_the_answer() -> None:
    """Tiers (b) and (c) go: the words, the statuses derived from them, and the citations."""
    stripped = strip_advice_text(accepted_run())
    for entry in stripped["advice"]:
        assert not set(entry) & set(STRIPPED_FIELDS)


def test_stripping_removes_the_status_counts() -> None:
    """The counts are derived from the statuses, so they are exempt for the same reason."""
    assert "status_counts" not in strip_advice_text(accepted_run())


def test_stripping_keeps_the_whole_skeleton() -> None:
    """Tier (a) is what a run must reproduce, so nothing in it may be excused."""
    document = accepted_run()
    stripped = strip_advice_text(document)
    assert stripped["schema_version"] == document["schema_version"]
    assert stripped["findings_schema_version"] == document["findings_schema_version"]
    assert stripped["model_run"] == document["model_run"]
    assert stripped["advice_count"] == document["advice_count"]
    assert [entry["finding_id"] for entry in stripped["advice"]] == [FIRST, SECOND]


def test_stripping_removes_nothing_else() -> None:
    """A wider exception would quietly excuse the skeleton from the comparison."""
    document = accepted_run()
    stripped = strip_advice_text(document)
    assert set(stripped) == set(document) - {"status_counts"}
    assert all(set(entry) == {"finding_id"} for entry in stripped["advice"])


def test_stripping_leaves_the_original_document_untouched() -> None:
    """The projection is a copy, so the caller can still write the real file after it."""
    document = accepted_run()
    strip_advice_text(document)
    assert document["advice"][0]["guidance"] is not None
    assert document["status_counts"]["written"] == 2


def test_stripping_keeps_the_knowledge_base_block_whole() -> None:
    """An index is an input like a reachable server, so tier (a) must reproduce it."""
    document = remediation_document([written_entry(FIRST, sources=[source()])])
    stripped = strip_advice_text(document)
    assert stripped["knowledge_base"] == document["knowledge_base"] == indexed_knowledge()


def test_two_runs_that_retrieved_different_passages_leave_an_identical_skeleton() -> None:
    """Which passage a query came back with is the model's tier, not the skeleton's."""
    first = remediation_document([written_entry(FIRST, sources=[source()])])
    second = remediation_document([written_entry(FIRST, sources=[
        source(path=OTHER_SOURCE_PATH, url=OTHER_SOURCE_URL)])])
    assert remediation_to_json(strip_advice_text(first)) == remediation_to_json(
        strip_advice_text(second))


def test_two_runs_with_different_answers_leave_an_identical_skeleton() -> None:
    """This is the guarantee: two runs differ only where the schema says they may."""
    assert remediation_to_json(strip_advice_text(accepted_run())) == remediation_to_json(
        strip_advice_text(refused_run()))


def test_differing_prose_alone_leaves_an_identical_skeleton() -> None:
    """Two accepted answers in different words strip to the same bytes."""
    first = remediation_document([written_entry(FIRST)])
    second = remediation_document(
        [written_entry(FIRST, OTHER_GUIDANCE, [snippet("checked = approve(value)")])])
    assert remediation_to_json(strip_advice_text(first)) == remediation_to_json(
        strip_advice_text(second))


def test_the_entry_order_never_depends_on_what_the_model_said() -> None:
    """Entries sort by finding id, so a refusal never moves a record."""
    assert [entry["finding_id"] for entry in accepted_run()["advice"]] == [
        entry["finding_id"] for entry in refused_run()["advice"]]


def test_a_run_with_no_model_reached_is_byte_identical_in_full() -> None:
    """With tier (b) collapsed to a constant, nothing in the file is exempt."""
    def unreached() -> dict:
        """Build the degraded document the way an unreachable server produces it."""
        return remediation_document(
            [unavailable_entry(FIRST), unavailable_entry(SECOND)], unavailable_run())

    assert remediation_to_json(unreached()) == remediation_to_json(unreached())

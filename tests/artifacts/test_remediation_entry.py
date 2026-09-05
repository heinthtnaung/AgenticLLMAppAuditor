"""One advice record: the three statuses, and the invariant that keeps them apart.

The shape exists so a reader can tell *the model wrote nothing* from *the model
wrote something and it was refused*. That only holds if a refusal carries no
text at all: an entry with `status: rejected` and a trimmed `guidance` would be
a quiet edit wearing a refusal's label, so the constructor refuses to build one.
Retrieved `sources` fall under the same invariant: they are the passages an
answer was grounded on, so an answer nobody accepted has nothing to cite.
"""

import pytest

from artifacts.remediation import (
    ADVICE_REASONS,
    ADVICE_STATUSES,
    MODEL_DISABLED,
    MODEL_UNAVAILABLE,
    NAMES_APP_IDENTIFIER,
    REJECTED,
    UNAVAILABLE,
    WRITTEN,
    advice_entry,
)
from remediation_fixtures import (
    CLEAN_GUIDANCE,
    rejected_entry,
    snippet,
    source,
    unavailable_entry,
    written_entry,
)

FINDING_ID = "app/agent.py:12:TOOL_CALL:ShellTool:high_privilege_tool"


def test_the_three_statuses_are_the_whole_vocabulary() -> None:
    """A fourth would be unreadable to the report, which branches on exactly these."""
    assert ADVICE_STATUSES == (WRITTEN, REJECTED, UNAVAILABLE)


def test_written_advice_carries_the_text_and_no_reason() -> None:
    """Advice that passed is the only status with anything for a reader to act on."""
    entry = written_entry(FINDING_ID)
    assert entry["status"] == WRITTEN
    assert entry["reason"] is None
    assert entry["rejected_on"] is None
    assert entry["guidance"] == CLEAN_GUIDANCE
    assert len(entry["snippets"]) == 1


def test_rejected_advice_carries_a_reason_and_the_field_it_offended() -> None:
    """A refusal is recorded rather than hidden, and names which field it was refused on."""
    entry = rejected_entry(FINDING_ID, NAMES_APP_IDENTIFIER)
    assert entry["status"] == REJECTED
    assert entry["reason"] == NAMES_APP_IDENTIFIER
    assert entry["rejected_on"] == "code"
    assert entry["guidance"] is None
    assert entry["snippets"] == []


def test_unavailable_advice_says_no_model_was_ever_asked() -> None:
    """Advice nobody wrote must never be mistaken for advice a model produced."""
    entry = unavailable_entry(FINDING_ID)
    assert entry["status"] == UNAVAILABLE
    assert entry["reason"] == MODEL_UNAVAILABLE
    assert entry["guidance"] is None
    assert entry["snippets"] == []


def test_a_refusal_and_a_silence_are_told_apart_by_status_not_by_inference() -> None:
    """Both carry no text, so the status is what distinguishes them, and it must differ."""
    refused = rejected_entry(FINDING_ID, NAMES_APP_IDENTIFIER)
    silent = unavailable_entry(FINDING_ID)
    assert refused["status"] != silent["status"]
    assert refused["reason"] != silent["reason"]


def test_every_entry_carries_the_same_seven_fields() -> None:
    """A reader reads one shape, so a missing key never has to be told from a null."""
    expected = {"finding_id", "status", "reason", "rejected_on", "guidance", "snippets",
                "sources"}
    for entry in (written_entry(FINDING_ID), rejected_entry(FINDING_ID, MODEL_DISABLED),
                  unavailable_entry(FINDING_ID)):
        assert set(entry) == expected


def test_a_refusal_carrying_guidance_is_refused_to_be_built() -> None:
    """Refusal is whole: an entry with text and a refusal label is not constructible."""
    with pytest.raises(ValueError, match="refusal is whole, not partial"):
        advice_entry(FINDING_ID, REJECTED, NAMES_APP_IDENTIFIER, "code", CLEAN_GUIDANCE)


def test_a_refusal_carrying_snippets_is_refused_to_be_built() -> None:
    """One identifier stripped can still leave a snippet applicable, so none survives."""
    with pytest.raises(ValueError, match="refusal is whole, not partial"):
        advice_entry(FINDING_ID, REJECTED, NAMES_APP_IDENTIFIER, "code", snippets=[snippet()])


def test_a_refusal_carrying_retrieved_sources_is_refused_to_be_built() -> None:
    """Citations without the answer they grounded would credit a passage with prose nobody kept."""
    with pytest.raises(ValueError, match="refusal is whole, not partial"):
        advice_entry(FINDING_ID, REJECTED, NAMES_APP_IDENTIFIER, "code", sources=[source()])


def test_an_unavailable_entry_carrying_text_is_refused_to_be_built() -> None:
    """The same invariant on the other non-written status; a canned fallback is not allowed."""
    with pytest.raises(ValueError, match="refusal is whole, not partial"):
        advice_entry(FINDING_ID, UNAVAILABLE, MODEL_UNAVAILABLE, guidance=CLEAN_GUIDANCE)


@pytest.mark.parametrize("status", [REJECTED, UNAVAILABLE])
def test_a_status_that_is_not_written_needs_a_reason(status: str) -> None:
    """Advice absent without a why is a gap a reader cannot act on."""
    with pytest.raises(ValueError, match="needs a reason"):
        advice_entry(FINDING_ID, status)


def test_a_reason_outside_the_vocabulary_is_refused() -> None:
    """The reason is a fixed vocabulary, mirroring a probe's outcome and reason pair."""
    with pytest.raises(ValueError, match="needs a reason"):
        advice_entry(FINDING_ID, REJECTED, "the model was rude")


def test_written_advice_may_not_carry_a_refusal_reason() -> None:
    """Accepted and refused at once is not a state the report could render."""
    with pytest.raises(ValueError, match="written advice carries no refusal reason"):
        advice_entry(FINDING_ID, WRITTEN, NAMES_APP_IDENTIFIER, guidance=CLEAN_GUIDANCE)


def test_an_unknown_status_is_refused() -> None:
    """The message names the three, so a caller sees what was expected."""
    with pytest.raises(ValueError, match="unknown advice status"):
        advice_entry(FINDING_ID, "maybe")


def test_every_reason_in_the_vocabulary_can_build_a_refusal() -> None:
    """A reason nothing could use would be documentation with no code behind it."""
    for reason in ADVICE_REASONS:
        assert advice_entry(FINDING_ID, REJECTED, reason)["reason"] == reason


def test_written_advice_may_carry_prose_and_no_snippet() -> None:
    """Snippets are optional: prose alone is a complete answer."""
    assert written_entry(FINDING_ID, snippets=[])["snippets"] == []


def test_sources_given_as_one_attribution_rather_than_a_list_are_refused() -> None:
    """Sources are tool-written, so the producer passing a bare dict is a bug, not an answer."""
    with pytest.raises(ValueError, match="sources is a list of attributions"):
        advice_entry(FINDING_ID, WRITTEN, guidance=CLEAN_GUIDANCE, sources=source())


def test_the_entry_copies_the_snippet_list_it_was_given() -> None:
    """A caller mutating its list afterwards must not rewrite the artifact."""
    snippets = [snippet()]
    entry = written_entry(FINDING_ID, snippets=snippets)
    snippets.append(snippet("value = other()"))
    assert len(entry["snippets"]) == 1

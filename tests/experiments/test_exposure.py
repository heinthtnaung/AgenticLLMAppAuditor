"""Does the ledger report the field kinds it actually carried, or a fixed list?

`field_kinds_transmitted` used to be a constant naming both prompts' contents on
every run. That is how a measured run claimed it had transmitted prompt template
source text when the only request that left the machine was the planner's -- a
statement about someone else's source code going to a hosted provider, written
into the study's own output with nothing behind it.

So the empty case is the sharpest test here: an empty ledger returned three
field kinds before, and must now return none. Every expectation below is derived
from `prompt_kinds.FIELD_KINDS` rather than spelled out, so an edit to what
either prompt carries cannot leave this file agreeing with the old list.
"""

import pytest
from exposure import Ledger
from prompt_kinds import FIELD_KINDS, PLANNER_PROMPT, PROBE_PROMPT

# What each kind declares it puts on the wire, read off the module under test.
PROBE_FIELDS = sorted(FIELD_KINDS[PROBE_PROMPT])
PLANNER_FIELDS = sorted(FIELD_KINDS[PLANNER_PROMPT])
ALL_FIELDS = sorted(set(PROBE_FIELDS) | set(PLANNER_FIELDS))

# Two prompts of known length, so `bytes_sent` is checked against a number and
# not against itself. Both ASCII, so one character is one byte.
PROBE_TEXT = "probe prompt body"
PLANNER_TEXT = "planner prompt body!"

UNKNOWN_KIND = "sbom prompt"


def test_an_empty_ledger_transmitted_no_field_kinds() -> None:
    """The old bug in one line: a run that sent nothing must claim nothing."""
    summary = Ledger().summary()
    assert summary["requests"] == 0
    assert summary["bytes_sent"] == 0
    assert summary["prompt_kinds"] == []
    assert summary["field_kinds_transmitted"] == []


def test_a_probe_only_ledger_names_no_planner_field_kind() -> None:
    """One probe prompt transmits the template's text and no surface ids."""
    ledger = Ledger()
    ledger.record(PROBE_TEXT, PROBE_PROMPT)
    summary = ledger.summary()
    assert summary["prompt_kinds"] == [PROBE_PROMPT]
    assert summary["field_kinds_transmitted"] == PROBE_FIELDS
    assert not set(summary["field_kinds_transmitted"]) & set(PLANNER_FIELDS)


def test_a_planner_only_ledger_names_no_probe_field_kind() -> None:
    """The run that was measured wrong: a planner prompt sends no template text."""
    ledger = Ledger()
    ledger.record(PLANNER_TEXT, PLANNER_PROMPT)
    summary = ledger.summary()
    assert summary["prompt_kinds"] == [PLANNER_PROMPT]
    assert summary["field_kinds_transmitted"] == PLANNER_FIELDS
    assert not set(summary["field_kinds_transmitted"]) & set(PROBE_FIELDS)


def test_a_mixed_ledger_names_both_sorted_and_deduplicated() -> None:
    """Two probe prompts and one planner prompt: three field kinds, each once."""
    ledger = Ledger()
    ledger.record(PROBE_TEXT, PROBE_PROMPT)
    ledger.record(PROBE_TEXT, PROBE_PROMPT)
    ledger.record(PLANNER_TEXT, PLANNER_PROMPT)
    summary = ledger.summary()
    assert summary["field_kinds_transmitted"] == ALL_FIELDS
    assert len(ALL_FIELDS) == 3
    assert summary["prompt_kinds"] == sorted([PLANNER_PROMPT, PROBE_PROMPT])


def test_counts_every_request_and_its_bytes() -> None:
    """Three prompts recorded, and the byte count is their encoded lengths summed."""
    ledger = Ledger()
    ledger.record(PROBE_TEXT, PROBE_PROMPT)
    ledger.record(PROBE_TEXT, PROBE_PROMPT)
    ledger.record(PLANNER_TEXT, PLANNER_PROMPT)
    summary = ledger.summary()
    assert summary["requests"] == 3
    assert summary["bytes_sent"] == 2 * len(PROBE_TEXT) + len(PLANNER_TEXT)


def test_the_summary_carries_no_prompt_text() -> None:
    """The counts are publishable; the audited app's source text is not."""
    ledger = Ledger()
    ledger.record(PROBE_TEXT, PROBE_PROMPT)
    summary = ledger.summary()
    assert PROBE_TEXT not in str(summary)
    assert "prompts" not in summary


def test_refuses_a_prompt_kind_it_cannot_describe() -> None:
    """An unknown kind is refused at the record, not later at the summary."""
    ledger = Ledger()
    with pytest.raises(ValueError) as raised:
        ledger.record(PROBE_TEXT, UNKNOWN_KIND)
    assert UNKNOWN_KIND in str(raised.value)


def test_a_refused_record_leaves_the_ledger_untouched() -> None:
    """A refusal must not half-record: no request counted, no bytes counted."""
    ledger = Ledger()
    with pytest.raises(ValueError):
        ledger.record(PROBE_TEXT, UNKNOWN_KIND)
    assert ledger.summary()["requests"] == 0
    assert ledger.prompts == [] and ledger.kinds == []

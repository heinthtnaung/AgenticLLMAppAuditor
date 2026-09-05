"""The answers a local model really gives, and what each one is recorded as.

Split from `test_semantic_probe.py`, which is about the four outcomes and the
finding beside a confirmed one. This file is about the *shape* the answer
arrives in: fenced, prefixed, prose with no verdict in it, empty, or not a
string at all. `read_verdict` is tested on its own in
`test_semantic_probe_reading.py`; here the reply goes through `run_over_repo`,
so what is asserted is the probe record an audit would write.

The rule every test below defends is one rule: **a reply carrying no verdict is
not a `SAFE` reply.** Recording it as `refuted` -- "the model read the template
as structurally safe" -- put a claim in `findings.json` that an empty string
supported. `inconclusive` says what happened instead, and the model's own words
are quoted beside it so a reader can see why nothing was concluded.

No server is involved: the replies are strings these tests wrote, handed to the
check through the `model_ask_fn` argument it takes for exactly this reason.
"""

from artifacts.finding import (
    CONFIRMED, INCONCLUSIVE, PROBE_REASONS, REFUTED)
from checks.semantic_probe import NO_ANSWER, NO_MODEL
from semantic_probe_fixtures import PROMPT_LINE, only_probe

# The well-formed answer, and the malformed ones a local model really produces:
# nothing at all, prose with no verdict in it, and -- when a client is
# mid-refactor -- something that is not a string.
VULNERABLE_REPLY = "VULNERABLE\nThe {question} value is dropped straight into the instructions."
VULNERABLE_RATIONALE = "The {question} value is dropped straight into the instructions."
PROSE_REPLY = "I had a look at the template and it seems fine to me."
EMPTY_REPLIES = ("", "   \n\n")
NON_STRING_REPLIES = (None, 42, ["VULNERABLE"], {"verdict": "VULNERABLE"})


def test_an_empty_reply_is_inconclusive_rather_than_a_clean_bill(tmp_path) -> None:
    """Silence is not a verdict, and recording it as `refuted` claimed the model cleared this."""
    for index, reply in enumerate(EMPTY_REPLIES):
        findings, probe = only_probe(tmp_path / f"empty-{index}", reply)
        assert findings == []
        assert (probe.outcome, probe.reason) == (INCONCLUSIVE, NO_ANSWER)


def test_an_empty_reply_says_in_the_record_that_nothing_came_back(tmp_path) -> None:
    """Rule 8: the probe has to tell a reader what the model said, even when it said nothing."""
    _findings, probe = only_probe(tmp_path, "")
    assert "(nothing)" in probe.detail


def test_a_reply_that_is_not_a_string_is_inconclusive(tmp_path) -> None:
    """A client returning JSON instead of text must not crash the audit or conclude anything."""
    for index, reply in enumerate(NON_STRING_REPLIES):
        findings, probe = only_probe(tmp_path / f"reply-{index}", reply)
        assert findings == []
        assert (probe.outcome, probe.reason) == (INCONCLUSIVE, NO_ANSWER)


def test_prose_with_no_verdict_word_is_inconclusive_and_the_prose_is_quoted(tmp_path) -> None:
    """The closed question went unanswered, so nothing is claimed and the answer is kept."""
    findings, probe = only_probe(tmp_path, PROSE_REPLY)
    assert findings == []
    assert (probe.outcome, probe.reason) == (INCONCLUSIVE, NO_ANSWER)
    assert PROSE_REPLY in probe.detail


def test_a_no_answer_is_recorded_as_a_reason_the_vocabulary_allows(tmp_path) -> None:
    """`PROBE_REASONS` is closed, so an unanswered probe borrows `model_unavailable`."""
    _findings, probe = only_probe(tmp_path, PROSE_REPLY)
    assert probe.reason in PROBE_REASONS
    assert NO_ANSWER == NO_MODEL


def test_a_fenced_reply_is_read_as_a_verdict_and_still_produces_the_finding(tmp_path) -> None:
    """The answer a local model actually gives, all the way through to the finding."""
    findings, probe = only_probe(tmp_path, f"```\n{VULNERABLE_REPLY}\n```")
    assert probe.outcome == CONFIRMED
    assert probe.detail == VULNERABLE_RATIONALE
    assert [(f.file, f.line) for f in findings] == [("agent.py", PROMPT_LINE)]


def test_a_verdict_behind_a_preamble_is_still_a_verdict(tmp_path) -> None:
    """"Answer: SAFE" was thrown away by a first-word test and recorded as no answer."""
    findings, probe = only_probe(tmp_path, "Answer: SAFE")
    assert findings == []
    assert (probe.outcome, probe.reason) == (REFUTED, None)



"""The seam between retrieval and the advice artifact: passages in, attributions out.

Both sides of this join are tested elsewhere -- the retriever's helpers in
tests/retrieval/, the refusal rules against `judge` -- and the join itself was
not. What is asserted here is the four things `advise.py` promises about
grounding: the passages reach the prompt, they sit *before* the instructions,
the attributions reach the entry, and a refused answer keeps none of them.

The retriever is a plain local function in every test below. That is the point
rather than a convenience: `advise.py` never imports the knowledge base, so
anything shaped like `Grounding.passages_for` will do, and no test here needs
ChromaDB, an index or an embedding server.
"""

import model_client
from artifacts.remediation import NAMES_APP_IDENTIFIER, REJECTED, UNAVAILABLE, WRITTEN
from checks import advise
from checks.advise import PASSAGES_HEADER, advise_all, advise_one, build_prompt
from cli_helpers import STUB_ADVICE, stub_model, stub_model_unavailable
from parsing.languages import PYTHON
from remediation_fixtures import finding_record, source
from retrieval.owasp_reference import reference_for

# One retrieved passage, as `reference_block` would have labelled it. It names
# no risk class, because a passage naming a foreign one is dropped upstream.
PASSAGE_TEXT = ("[1] owasp-cheatsheets cheatsheets/Alpha_Cheat_Sheet.md - Input Validation\n"
                "Treat every retrieved text as data, never as instruction.")

# An answer quoting the audited app's own identifier, the shortest route to a
# refusal. The same answer, and the same reason, as in test_advise.py.
LEAKING_ANSWER = ("Narrow what the agent may run.\n\n"
                  "```python\nrunner = ShellTool()\n```")

# The instruction an overrunning prompt must never lose, quoted from the
# template itself: Ollama truncates the *front* of a prompt it cannot fit, so
# the passages are placed ahead of the rules and an overrun costs passages.
FORBIDDING_INSTRUCTION = "must NOT contain any of these strings"


def grounded_retriever(finding: dict) -> tuple[str, list[dict]]:
    """Stand in for `Grounding.passages_for`: one passage and its one attribution."""
    return PASSAGE_TEXT, [source()]


def record_prompts(monkeypatch) -> list[str]:
    """Answer like the stub model, and return the list every prompt sent lands in."""
    sent = []

    def answer(prompt: str, model: str | None = None) -> str:
        """Note the prompt and reply with advice that passes the contract."""
        sent.append(prompt)
        return STUB_ADVICE
    monkeypatch.setattr(model_client, "ask", answer)
    return sent


def two_findings() -> list[dict]:
    """Two findings differing in the rule that raised them, so their ids differ."""
    return [finding_record(), finding_record(rule_id="other_rule",
                                             finding_id="app/agent.py:12:X:Y:other_rule")]


def test_the_prompt_carries_the_retrieved_passages_under_their_header() -> None:
    """Retrieval is an argument to a pure function, and the prompt shows what it was given."""
    prompt = build_prompt(finding_record(), (), PASSAGE_TEXT)
    assert PASSAGES_HEADER in prompt
    assert PASSAGE_TEXT in prompt


def test_an_ungrounded_prompt_carries_no_passage_header() -> None:
    """A header over nothing would read as passages the model was shown and ignored."""
    assert PASSAGES_HEADER not in build_prompt(finding_record())


def test_the_anchor_the_ordering_tests_search_for_is_the_templates_own_words() -> None:
    """Guard on the two tests below: a reworded rule must fail them, not slip past them."""
    assert FORBIDDING_INSTRUCTION in advise.PROMPT_TEMPLATE


def test_the_passages_sit_before_the_instructions_the_answer_must_obey() -> None:
    """The stated safety property: a prompt that overruns loses passages, never rules."""
    prompt = build_prompt(finding_record(), (), PASSAGE_TEXT)
    assert prompt.index(PASSAGE_TEXT) < prompt.index(FORBIDDING_INSTRUCTION)


def test_the_risk_class_reference_sits_before_the_instructions_too() -> None:
    """The reference block is injected on every prompt, so it is ahead of the rules as well."""
    finding = finding_record()
    prompt = build_prompt(finding)
    reference = reference_for(finding["owasp_id"]).prompt_text()
    assert prompt.index(reference) < prompt.index(FORBIDDING_INSTRUCTION)


def test_the_retrievers_passages_reach_the_prompt_the_model_is_sent(monkeypatch) -> None:
    """The wiring, not the composition: what the retriever returned is what was asked."""
    sent = record_prompts(monkeypatch)
    advise_one(finding_record(), PYTHON, (), grounded_retriever)
    assert len(sent) == 1
    assert PASSAGE_TEXT in sent[0]


def test_a_grounded_answer_records_the_attribution_the_retriever_gave(monkeypatch) -> None:
    """The other half of the seam: the entry cites what grounded it, so a reader can open it."""
    stub_model(monkeypatch)
    entry = advise_one(finding_record(), PYTHON, (), grounded_retriever)
    assert entry["status"] == WRITTEN
    assert entry["sources"] == [source()]


def test_an_ungrounded_entry_records_no_sources(monkeypatch) -> None:
    """No retriever is the normal case, and it attributes nothing rather than omitting the field."""
    stub_model(monkeypatch)
    assert advise_one(finding_record(), PYTHON)["sources"] == []


def test_a_refused_answer_discards_the_passages_it_was_grounded_on(monkeypatch) -> None:
    """Refusal is whole: an attribution beside no advice would say the tool kept something."""
    stub_model(monkeypatch, LEAKING_ANSWER)
    entry = advise_one(finding_record(), PYTHON, (), grounded_retriever)
    assert (entry["status"], entry["reason"]) == (REJECTED, NAMES_APP_IDENTIFIER)
    assert entry["sources"] == []


def test_an_unreachable_model_records_no_sources_either(monkeypatch) -> None:
    """Passages were retrieved and no answer came back, so there is nothing they grounded."""
    stub_model_unavailable(monkeypatch)
    entry = advise_one(finding_record(), PYTHON, (), grounded_retriever)
    assert entry["status"] == UNAVAILABLE
    assert entry["sources"] == []


def test_advise_all_hands_the_retriever_every_finding(monkeypatch) -> None:
    """One grounding per run, asked once per finding: none is left ungrounded by omission."""
    stub_model(monkeypatch)
    asked = []

    def recording_retriever(finding: dict) -> tuple[str, list[dict]]:
        """Note which finding was retrieved for, then ground it like the fixture above."""
        asked.append(finding["finding_id"])
        return grounded_retriever(finding)
    advise_all(two_findings(), PYTHON, (), recording_retriever)
    assert asked == [finding["finding_id"] for finding in two_findings()]


def test_advise_all_records_the_attribution_on_every_entry(monkeypatch) -> None:
    """The retriever is passed through, so every written entry carries its own sources."""
    stub_model(monkeypatch)
    entries = advise_all(two_findings(), PYTHON, (), grounded_retriever)
    assert [entry["sources"] for entry in entries] == [[source()], [source()]]

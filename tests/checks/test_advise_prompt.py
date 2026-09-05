"""Composing the one prompt a finding is advised on, and taking the answer apart.

Neither half judges anything. `build_prompt` turns evidence the tool already
gathered into a question, and `split_answer` separates prose from fenced blocks
so `judge` can rule on each. The prompt does enumerate the forbidden tokens
because it measurably lowers the refusal rate, but that is an efficiency and no
test here treats it as the guard.
"""

from artifacts.advice_rules import evidence_line
from artifacts.remediation import SAFER_LABEL, SNIPPET_LABELS
from checks.advise import MAX_SENTENCES, build_prompt, split_answer
from parsing.languages import JAVASCRIPT, PYTHON, TYPESCRIPT
from remediation_fixtures import finding_record

COMPONENT = "langchain-community"


def test_the_evidence_line_names_the_surface_it_was_raised_on() -> None:
    """The kind and the name together are what a reader recognises the surface by."""
    assert "a TOOL_CALL surface named ShellTool" in evidence_line(finding_record())


def test_the_evidence_line_names_the_file_and_line() -> None:
    """The location is copied from the surface, in the words the artifact uses."""
    assert "at app/agent.py:12" in evidence_line(finding_record())


def test_the_evidence_line_names_the_component_when_one_is_evidence() -> None:
    """A supply-chain finding is anchored on a component rather than on code."""
    line = evidence_line(finding_record(component_name=COMPONENT))
    assert f"in the component {COMPONENT}" in line


def test_the_evidence_line_says_so_when_there_is_no_location() -> None:
    """An empty string would read as evidence nobody bothered to write down."""
    assert evidence_line({}) == "no code location recorded"


def test_the_prompt_names_the_finding_and_its_own_risk_class() -> None:
    """The model advises on one finding, so the prompt carries that finding's facts."""
    finding = finding_record()
    prompt = build_prompt(finding)
    assert finding["title"] in prompt
    assert finding["owasp_id"] in prompt
    assert evidence_line(finding) in prompt


def test_the_prompt_states_the_sentence_budget() -> None:
    """The cap is a named constant, so the prompt cannot drift from what is enforced."""
    assert f"at most {MAX_SENTENCES} sentences" in build_prompt(finding_record())


def test_the_prompt_lists_the_identifiers_the_answer_should_avoid() -> None:
    """An efficiency, not the guard: enumerating them lowers the refusal rate."""
    prompt = build_prompt(finding_record(), ("tools",))
    for identifier in ("ShellTool", "app/agent.py", "tools"):
        assert identifier in prompt


def test_the_prompt_says_something_when_there_is_nothing_to_forbid() -> None:
    """An empty list would leave the sentence dangling with a bare colon."""
    assert "any identifier from the audited application" in build_prompt({
        "title": "A finding", "owasp_id": "LLM01"})


def test_the_same_finding_composes_the_same_prompt_twice() -> None:
    """The identifier list is sorted, so a repeated run sends identical bytes."""
    finding = finding_record()
    assert build_prompt(finding, ("utils", "tools")) == build_prompt(finding, ("tools", "utils"))


def test_an_answer_with_no_fence_is_all_prose() -> None:
    """Prose alone is a complete answer, and must not invent an empty snippet."""
    guidance, snippets = split_answer("Bound what the agent may reach.", PYTHON)
    assert guidance == "Bound what the agent may reach."
    assert snippets == []


def test_a_fenced_block_is_lifted_out_of_the_prose() -> None:
    """The two halves are judged by different rules, so they must be separated first."""
    guidance, snippets = split_answer(
        "Check it first.\n\n```python\nchecked = approve(value)\n```", PYTHON)
    assert guidance == "Check it first."
    assert "```" not in guidance
    assert snippets[0]["code"] == "checked = approve(value)"


def test_a_lifted_block_is_labelled_as_an_illustration() -> None:
    """Neither label reads as "apply this", and the split assigns one of them."""
    _, snippets = split_answer("Do it.\n```python\nvalue = run()\n```", PYTHON)
    assert snippets[0]["label"] == SAFER_LABEL


def test_the_label_is_drawn_from_the_fixed_vocabulary() -> None:
    """The label is written by this code, never by the model, so it cannot drift."""
    _, snippets = split_answer("Do it.\n```python\nvalue = run()\n```", PYTHON)
    assert snippets[0]["label"] in SNIPPET_LABELS


def test_a_known_fence_language_is_kept() -> None:
    """When the model names a language the parser knows, that is what the snippet carries."""
    _, snippets = split_answer("Do it.\n```typescript\nconst x = run();\n```", PYTHON)
    assert snippets[0]["language"] == TYPESCRIPT


def test_an_unknown_fence_language_falls_back_to_the_apps_own() -> None:
    """`rust` is not in the vocabulary, so the app's language is what the snippet claims."""
    _, snippets = split_answer("Do it.\n```rust\nlet x = run();\n```", JAVASCRIPT)
    assert snippets[0]["language"] == JAVASCRIPT


def test_a_fence_with_no_language_falls_back_to_the_apps_own() -> None:
    """A bare fence is the common case, and must not produce a snippet with no language."""
    _, snippets = split_answer("Do it.\n```\nvalue = run()\n```", PYTHON)
    assert snippets[0]["language"] == PYTHON


def test_two_fenced_blocks_become_two_snippets() -> None:
    """The volume cap is `judge`'s job, so the split reports what was really there."""
    answer = "One.\n```python\na = run()\n```\nTwo.\n```python\nb = run()\n```"
    guidance, snippets = split_answer(answer, PYTHON)
    assert [one["code"] for one in snippets] == ["a = run()", "b = run()"]
    assert guidance == "One.\n\nTwo."


def test_a_tilde_fenced_block_is_lifted_out_like_a_backtick_one() -> None:
    """A model reaching for ~~~ gets its snippet judged, not refused for the fence style."""
    answer = "Check it first.\n\n~~~python\nchecked = approve(value)\n~~~"
    assert split_answer(answer, PYTHON) == split_answer(answer.replace("~~~", "```"), PYTHON)


def test_a_tilde_fence_leaves_no_marker_in_the_prose() -> None:
    """The marker itself is refused in guidance, so the split has to remove it."""
    guidance, snippets = split_answer(
        "Check it first.\n~~~python\nchecked = approve(value)\n~~~", PYTHON)
    assert guidance == "Check it first."
    assert snippets == [{"label": SAFER_LABEL, "language": PYTHON,
                         "code": "checked = approve(value)"}]

"""Asking the model about one finding, with the model stubbed.

No test here reaches a server. The refusal rules are asserted directly against
`judge` elsewhere; what is checked here is that `advise_one` routes a real
answer through them and records the outcome, including the outcome where there
was no answer at all. A stubbed model keeps the suite from depending on whether
Ollama is up and on what it said today.
"""

import pytest

from artifacts.remediation import (
    CODE_FENCE_IN_GUIDANCE,
    EMPTY_ANSWER,
    MODEL_UNAVAILABLE,
    NAMES_APP_IDENTIFIER,
    REJECTED,
    SNIPPET_IS_A_DIFF,
    UNAVAILABLE,
    WRITTEN,
)
from checks.advise import advise_all, advise_one
from cli_helpers import STUB_ADVICE, stub_model, stub_model_unavailable
from parsing.languages import PYTHON
from parsing.repo_loader import local_module_names
from remediation_fixtures import finding_record

# The audited app's own modules, taken from a tree the test writes: the pinned
# app whose `transaction_db.py` this used to read is gone.
APP_MODULES = ("main", "tools", "transaction_db", "utils")

# Answers a model could plausibly give, each breaking exactly one rule.
LEAKING_ANSWER = ("Narrow what the agent may run.\n\n"
                  "```python\nrunner = ShellTool()\n```")
MODULE_ANSWER = ("Narrow what the agent may run.\n\n"
                 "```python\ntransaction_db.query(value)\n```")
PATCH_ANSWER = ("Apply this change.\n\n"
                "```python\n+checked = approve(value)\n```")
UNTERMINATED_ANSWER = "Check it first.\n\n```python\nchecked = approve(value)"


def test_a_clean_answer_becomes_written_advice(monkeypatch) -> None:
    """The accepted path end to end: prose and one generic snippet survive."""
    stub_model(monkeypatch)
    entry = advise_one(finding_record(), PYTHON)
    assert entry["status"] == WRITTEN
    assert entry["reason"] is None
    assert entry["guidance"]
    assert len(entry["snippets"]) == 1


def test_written_advice_carries_the_models_own_words(monkeypatch) -> None:
    """The guidance is the answer's prose, not a summary the tool wrote for it."""
    stub_model(monkeypatch)
    entry = advise_one(finding_record(), PYTHON)
    assert entry["guidance"] == STUB_ADVICE.split("\n\n")[0]


def test_the_entry_names_the_finding_it_was_asked_about(monkeypatch) -> None:
    """The finding id is the join key back into findings.json."""
    stub_model(monkeypatch)
    finding = finding_record()
    assert advise_one(finding, PYTHON)["finding_id"] == finding["finding_id"]


def test_an_answer_quoting_the_apps_identifier_is_rejected(monkeypatch) -> None:
    """The guard runs on the answer, so a leak is caught after the model has spoken."""
    stub_model(monkeypatch, LEAKING_ANSWER)
    entry = advise_one(finding_record(), PYTHON)
    assert entry["status"] == REJECTED
    assert entry["reason"] == NAMES_APP_IDENTIFIER
    assert entry["rejected_on"] == "code"


def test_a_rejected_entry_shows_none_of_the_refused_answer(monkeypatch) -> None:
    """Refusal is whole: no part of the leaked snippet reaches the artifact."""
    stub_model(monkeypatch, LEAKING_ANSWER)
    entry = advise_one(finding_record(), PYTHON)
    assert entry["guidance"] is None
    assert entry["snippets"] == []


def test_an_answer_naming_one_of_the_apps_modules_is_rejected(monkeypatch) -> None:
    """The app's own modules are passed in beside the finding and checked the same way."""
    stub_model(monkeypatch, MODULE_ANSWER)
    entry = advise_one(finding_record(), PYTHON, ("transaction_db",))
    assert (entry["status"], entry["reason"]) == (REJECTED, NAMES_APP_IDENTIFIER)


def test_a_patch_shaped_answer_is_rejected(monkeypatch) -> None:
    """A block a reader could feed to `git apply` is what the boundary exists to stop."""
    stub_model(monkeypatch, PATCH_ANSWER)
    assert advise_one(finding_record(), PYTHON)["reason"] == SNIPPET_IS_A_DIFF


def test_an_unterminated_fence_is_rejected_as_a_fence_in_prose(monkeypatch) -> None:
    """A block the splitter cannot lift out stays in the prose, where fences are refused."""
    stub_model(monkeypatch, UNTERMINATED_ANSWER)
    entry = advise_one(finding_record(), PYTHON)
    assert (entry["reason"], entry["rejected_on"]) == (CODE_FENCE_IN_GUIDANCE, "guidance")


@pytest.mark.parametrize("answer", ["", "   \n\t"])
def test_an_empty_answer_is_rejected_rather_than_stored(answer: str, monkeypatch) -> None:
    """A server that replies with nothing is recorded as having said nothing useful."""
    stub_model(monkeypatch, answer)
    assert advise_one(finding_record(), PYTHON)["reason"] == EMPTY_ANSWER


def test_an_unreachable_server_becomes_unavailable(monkeypatch) -> None:
    """An unreachable server is a status of its own, never a refusal of an answer."""
    stub_model_unavailable(monkeypatch)
    entry = advise_one(finding_record(), PYTHON)
    assert entry["status"] == UNAVAILABLE
    assert entry["reason"] == MODEL_UNAVAILABLE


def test_an_unreachable_server_produces_no_canned_advice(monkeypatch) -> None:
    """There is no fallback text: advice nobody wrote must not look like advice."""
    stub_model_unavailable(monkeypatch)
    entry = advise_one(finding_record(), PYTHON)
    assert entry["guidance"] is None
    assert entry["snippets"] == []


def two_findings() -> list[dict]:
    """Two findings differing in the rule that raised them, so their ids differ."""
    return [finding_record(), finding_record(rule_id="other_rule",
                                             finding_id="app/agent.py:12:X:Y:other_rule")]


def test_advise_all_returns_one_entry_per_finding(monkeypatch) -> None:
    """The artifact carries an entry for every finding, including the ones with no advice."""
    stub_model(monkeypatch)
    entries = advise_all(two_findings(), PYTHON)
    assert [entry["finding_id"] for entry in entries] == [
        finding["finding_id"] for finding in two_findings()]


def test_advise_all_on_no_findings_asks_nothing(monkeypatch) -> None:
    """An app with nothing found needs no advice, and must not invent an entry."""
    stub_model(monkeypatch)
    assert advise_all([], PYTHON) == []


def test_advise_all_carries_on_after_a_refusal(monkeypatch) -> None:
    """One refused answer must not cost the other findings their entries."""
    stub_model(monkeypatch, LEAKING_ANSWER)
    entries = advise_all(two_findings(), PYTHON)
    assert [entry["status"] for entry in entries] == [REJECTED, REJECTED]


def test_an_answer_naming_a_module_the_repository_really_has_is_rejected(
        monkeypatch, tmp_path) -> None:
    """The module list comes from the loader over a real tree, not from a literal tuple."""
    for name in APP_MODULES:
        (tmp_path / f"{name}.py").write_text("x = 1\n", encoding="utf-8")
    modules = tuple(local_module_names(str(tmp_path)))
    assert "transaction_db" in modules
    stub_model(monkeypatch, MODULE_ANSWER)
    assert advise_one(finding_record(), PYTHON, modules)["reason"] == NAMES_APP_IDENTIFIER

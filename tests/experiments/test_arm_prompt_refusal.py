"""Is a prompt the study cannot account for refused before it is transmitted?

`_arm` wraps the ask function it is handed, and the wrapper records every prompt
against `prompt_kinds.classify` *first*:

    ledger.record(prompt, classify(prompt))
    return ask(prompt)

The order is the guarantee. `classify` refuses a prompt it does not recognise
(`ValueError`, deliberately not `RuntimeError`, which both callers would file as
an absent model), and because the refusal happens before the call, a prompt
whose contents the study could not state never leaves the machine. Written the
other way round the exposure figure would still be wrong and the data would
already be gone.

**How the wrapper is reached, and what that costs.** `watched` is a closure
inside `_arm`; nothing exports it, and no prompt `build_findings` really sends
is unclassifiable, so a foreign prompt cannot be delivered through a real audit.
The smallest honest seam is to replace the one thing that hands prompts to the
wrapper -- the driver -- and keep the rest real: the real `_arm`, the real
wrapper, the real `classify`, the real `Ledger`. What that does not prove is
that `build_findings` drives the wrapper the way this stand-in does;
`test_prompt_labelling_seam.py` audits a written-out app for that.
"""

from functools import partial
from collections.abc import Callable

import pytest

import compare_models
from checks.semantic_probe import RED_TEAM_PROMPT
from prompt_kinds import PROBE_PROMPT, classify
from semantic_probe_fixtures import TEMPLATE_TEXT

from .arm_fixtures import LOCAL

DECODE_SETTINGS = {"temperature": 0, "seed": 7}

# Never opened: the driver that would have read it is replaced below.
UNREAD_REPO = "/tmp/study-app-never-read"

# A prompt from neither the planner nor the probe -- something a later caller
# might send through the same seam -- and one the probe really sends.
FOREIGN_PROMPT = "Summarise this repository's dependencies for me."
ACCOUNTABLE_PROMPT = RED_TEAM_PROMPT.format(template=TEMPLATE_TEXT)


class CountingAsk:
    """Stands in for a model: keeps every prompt, so "never sent" can be asserted."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        """Record the prompt and answer with a verdict no caller here reads."""
        self.prompts.append(prompt)
        return "SAFE"


def driver_sending(prompt: str) -> Callable[..., tuple[dict, None]]:
    """A stand-in for `build_findings` that hands the wrapper one prompt and stops."""

    def build_findings(*_args: object, model_ask_fn: Callable[[str], str],
                       **_kwargs: object) -> tuple[dict, None]:
        """Send the one prompt through the wrapper, then return an empty document."""
        model_ask_fn(prompt)
        return {"findings": [], "probes": []}, None

    return build_findings


def arm_sending(monkeypatch: pytest.MonkeyPatch,
                prompt: str) -> tuple[Callable[[], dict], CountingAsk]:
    """The real `_arm`, armed to receive one prompt, and the model stand-in it will use."""
    monkeypatch.setattr(compare_models, "build_findings", driver_sending(prompt))
    ask = CountingAsk()
    run = partial(compare_models._arm, LOCAL, ask, DECODE_SETTINGS, UNREAD_REPO, [])
    return run, ask


def test_an_unclassifiable_prompt_is_refused(monkeypatch) -> None:
    """`classify` raises rather than guessing, and the refusal leaves `_arm` unswallowed."""
    run, _ask = arm_sending(monkeypatch, FOREIGN_PROMPT)
    with pytest.raises(ValueError) as raised:
        run()
    assert "cannot classify" in str(raised.value)


def test_an_unclassifiable_prompt_is_never_sent_to_the_model(monkeypatch) -> None:
    """The load-bearing half: recorded before asked, so nothing unaccountable is transmitted."""
    run, ask = arm_sending(monkeypatch, FOREIGN_PROMPT)
    with pytest.raises(ValueError):
        run()
    assert ask.prompts == []


def test_a_prompt_the_study_can_account_for_is_sent(monkeypatch) -> None:
    """Non-vacuity: the wrapper refuses the foreign prompt, not every prompt."""
    assert classify(ACCOUNTABLE_PROMPT) == PROBE_PROMPT
    run, ask = arm_sending(monkeypatch, ACCOUNTABLE_PROMPT)
    arm = run()
    assert ask.prompts == [ACCOUNTABLE_PROMPT]
    assert arm["exposure"]["requests"] == 1
    assert arm["exposure"]["prompt_kinds"] == [PROBE_PROMPT]

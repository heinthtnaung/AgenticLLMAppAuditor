"""`model_run` after a semantic probe: what produced the model-authored content.

Split from `test_semantic_probe_document.py`, which covers the citation guard,
the coverage rule and the determinism exemption. This file covers one block and
its four states, because the block is a claim about what happened rather than
about what was configured, and three of the four states are degradations.

The states, and why each is its own test:

- `used` -- the model answered, so the artifact names it, its digest and the
  settings it was decoded with, which is what makes the verdict repeatable.
- `disabled` -- no model was offered, **or** one was offered and never asked,
  because there was nothing to ask about.
- `unavailable` -- a call was placed and the server refused it. Earned by a
  probe that actually tried; claimed anywhere else it is a false record of an
  audit that never reached for a server at all.

Every model here is a stand-in the test wrote. `PROBE_MODEL` is shaped like the
block `main.probe_inputs` builds, so what is asserted is the shape a real run
records; `tests/cli/test_main_probe.py` covers the real one.
"""

from artifacts.finding import INCONCLUSIVE, NOT_RUN
from artifacts.findings_document import MODEL_DISABLED, MODEL_UNAVAILABLE, MODEL_USED
from checks import planner, semantic_probe
from checks.semantic_probe import NO_TEXT
from semantic_probe_fixtures import (
    Answering,
    HIDDEN_TEMPLATE_APP,
    NO_PROMPT_APP,
    PROBE_MODEL,
    Refusing,
    audited,
)

VULNERABLE_REPLY = "VULNERABLE\nThe {question} value lands inside the instructions."

# Since task 7.2 `build_findings` hands the same `ask` to the planner and to the
# probe, so counting calls no longer says which of the two made them. The first
# line of a prompt names its producer, and these are the two producers.
PLANNER_OPENER = planner.PROMPT_TEMPLATE.splitlines()[0]
PROBE_OPENER = semantic_probe.RED_TEAM_PROMPT.splitlines()[0]


def openers(prompts: list[str]) -> list[str]:
    """The first line of each prompt asked, which is what names the producer."""
    return [prompt.splitlines()[0] for prompt in prompts]


def test_the_model_run_says_used_and_names_the_model_when_the_probe_ran(tmp_path) -> None:
    """A model-authored finding beside `status: disabled` would be a false provenance record."""
    run = audited(tmp_path, Answering(VULNERABLE_REPLY))[0]["model_run"]
    assert run["status"] == MODEL_USED
    assert run["model_identifier"] == PROBE_MODEL["identifier"]
    assert run["model_digest"] == PROBE_MODEL["digest"]
    assert run["model_settings"] == PROBE_MODEL["settings"]


def test_the_model_run_says_disabled_when_no_probe_ran(tmp_path) -> None:
    """The other direction: naming a model on a run that never consulted one is the same lie."""
    run = audited(tmp_path, ask=None, probe_model=None)[0]["model_run"]
    assert run["status"] == MODEL_DISABLED
    assert run["model_identifier"] is None
    assert run["model_settings"] == {}


def test_the_model_run_says_disabled_when_a_model_was_offered_but_never_asked(tmp_path) -> None:
    """Provenance follows what happened, not what was configured: no template, no consultation."""
    run = audited(tmp_path, Answering(VULNERABLE_REPLY), NO_PROMPT_APP)[0]["model_run"]
    assert run["status"] == MODEL_DISABLED
    assert run["model_identifier"] is None


def test_the_model_run_says_disabled_when_every_template_was_unreadable(tmp_path) -> None:
    """A run that placed no call cannot say the server was unavailable.

    This is the mirror of the bug below, and it hid behind it: the probe records
    an inconclusive record per template, and "there are probes" was read as "a
    call was attempted". No text means the check never got as far as asking, so
    the honest word is the same one an audit with no model at all uses.
    """
    run = audited(tmp_path, Answering(VULNERABLE_REPLY), HIDDEN_TEMPLATE_APP)[0]["model_run"]
    assert run["status"] == MODEL_DISABLED
    assert run["model_identifier"] is None


def test_that_disabled_run_really_produced_a_probe_and_placed_no_call(tmp_path) -> None:
    """Guard: `disabled` is also what an app with nothing to probe records.

    The one prompt this run sends is the planner's. The probe sent none, which
    is what makes `disabled` the honest word for it.
    """
    ask = Answering(VULNERABLE_REPLY)
    document, _surfaces = audited(tmp_path, ask, HIDDEN_TEMPLATE_APP)
    assert PLANNER_OPENER != PROBE_OPENER, "the two producers must be distinguishable"
    assert [(p["outcome"], p["reason"]) for p in document["probes"]] == [(INCONCLUSIVE, NO_TEXT)]
    assert openers(ask.prompts) == [PLANNER_OPENER]


def test_the_model_run_says_unavailable_when_the_server_refused_every_call(tmp_path) -> None:
    """An unreachable server produced no model-authored content, and is not `used`.

    `MODEL_UNAVAILABLE` is in the vocabulary for exactly this, and both siblings
    use it: `outputs.build_remediation` records it when `model_client` raises,
    and `checks/planner.py` records it when the ordering call fails. Keying on
    "were there probes" instead wrote `status: used` here, naming the model, its
    digest and its decode settings on a run where nothing was ever answered --
    a false provenance record in the artifact Phase 4 grades.
    """
    document, _surfaces = audited(tmp_path, Refusing(RuntimeError("connection refused")))
    assert [p["outcome"] for p in document["probes"]] == [NOT_RUN]
    assert document["model_run"]["status"] == MODEL_UNAVAILABLE
    assert document["model_run"]["model_identifier"] is None

"""Can the study tell the two prompts it sends apart, by reading them?

`build_findings` drives the planner and the semantic probe through one
`model_ask_fn`, so the wrapper watching that seam sees two kinds of prompt in an
order it does not control. It used to label them all "probe prompt", which made
a run whose only request was the planner's report that it had transmitted prompt
template source text -- a false statement about what left the machine.

Every prompt here is built by calling the code that sends it. A pasted literal
would keep passing after the template it copies was rewritten, which is the one
failure this file exists to catch. The last two tests pin the assumption the
whole classifier rests on: `.format()` leaves each first line alone.
"""

import pytest
from artifacts.surface import PROMPT_TEMPLATE, Surface
from checks import planner, semantic_probe
from checks.permissions import CHECK_NAME as PERMISSION_CHECK
from checks.taint import CHECK_NAME as TAINT_CHECK
from parsing.languages import PYTHON
from prompt_kinds import FIELD_KINDS, PLANNER_PROMPT, PROBE_PROMPT, classify

# What the probe would be shown for a real template: text with one interpolation
# point in it, which is the only kind of template the probe ever asks about.
TEMPLATE_TEXT = "You are a support agent. {question}"

# What the planner would be shown: one surface and two check names.
SURFACE = Surface(PROMPT_TEMPLATE, "ChatPromptTemplate.from_template", "agent.py", 5,
                  PYTHON, "prompt", "langchain.prompts")
ELIGIBLE_CHECKS = [PERMISSION_CHECK, TAINT_CHECK]

# Neither template's first line, and nothing either module sends.
FOREIGN_PROMPT = "Summarise this repository in three bullet points."


def probe_prompt() -> str:
    """The exact string `semantic_probe.judge` puts on the wire for one template."""
    return semantic_probe.RED_TEAM_PROMPT.format(template=TEMPLATE_TEXT)


def planner_prompt() -> str:
    """The exact string `planner.order_checks` puts on the wire for one plan."""
    return planner.build_prompt([SURFACE], ELIGIBLE_CHECKS)


def test_classifies_the_probes_own_prompt_as_a_probe_prompt() -> None:
    """The red-team prompt, built by the module that sends it, reads as a probe prompt."""
    assert classify(probe_prompt()) == PROBE_PROMPT


def test_classifies_the_planners_own_prompt_as_a_planner_prompt() -> None:
    """The planner prompt, built by `build_prompt`, reads as a planner prompt."""
    assert classify(planner_prompt()) == PLANNER_PROMPT


def test_the_two_prompts_are_not_classified_the_same_way() -> None:
    """Non-vacuity: the two real prompts land in different buckets, which is the point."""
    assert classify(probe_prompt()) != classify(planner_prompt())


def test_refuses_a_prompt_it_does_not_recognise() -> None:
    """A foreign prompt is refused rather than guessed at."""
    with pytest.raises(ValueError) as raised:
        classify(FOREIGN_PROMPT)
    assert FOREIGN_PROMPT[:20] in str(raised.value)


def test_the_refusal_is_a_value_error_and_not_a_runtime_error() -> None:
    """`RuntimeError` would be caught upstream and filed as an absent model."""
    with pytest.raises(ValueError) as raised:
        classify(FOREIGN_PROMPT)
    assert type(raised.value) is ValueError
    assert not isinstance(raised.value, RuntimeError)


def test_the_probe_prompts_first_line_survives_formatting() -> None:
    """The discriminator holds: `.format()` leaves the red-team prompt's first line alone."""
    assert probe_prompt().splitlines()[0] == semantic_probe.RED_TEAM_PROMPT.splitlines()[0]


def test_the_planner_prompts_first_line_survives_formatting() -> None:
    """The same for the planner, whose first line is filled in by `build_prompt`."""
    assert planner_prompt().splitlines()[0] == planner.PROMPT_TEMPLATE.splitlines()[0]


def test_both_kinds_declare_what_they_transmit() -> None:
    """A kind `classify` can return but `FIELD_KINDS` does not describe would be unusable."""
    assert set(FIELD_KINDS) == {PROBE_PROMPT, PLANNER_PROMPT}
    assert all(FIELD_KINDS[kind] for kind in FIELD_KINDS)

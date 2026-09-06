"""What each prompt sent to a model carries, so exposure is measured and not asserted.

`build_findings` drives both the planner and the semantic probe through one
`model_ask_fn`, so a wrapper watching that seam sees two kinds of prompt and
cannot tell them apart by position -- it has to read them. Filing every prompt
as a probe prompt is what made a measured run claim it had transmitted prompt
template source text on a run that transmitted none: the only request that left
the machine was the planner's.

The first line is the discriminator. Neither template carries a `{}` placeholder
on its first line, so `.format()` leaves both untouched and the match is exact.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from checks import planner, semantic_probe                       # noqa: E402

PROBE_PROMPT = "probe prompt"
PLANNER_PROMPT = "planner prompt"

# What each prompt actually puts on the wire, read off the two templates rather
# than guessed: the probe sends the template's own text and nothing else, while
# the planner sends surface ids, and a surface id spells file, line, kind and
# name. A blanket list covering both is how a run overstates what it sent.
FIELD_KINDS: dict[str, tuple[str, ...]] = {
    PROBE_PROMPT: ("prompt template source text",),
    PLANNER_PROMPT: ("surface ids: file paths, line numbers, kinds and names",
                     "check names, and which checks may be narrowed"),
}

# Each kind's first line, taken from the module that sends it. Never a copy:
# an edit to either prompt must move this with it or fail loudly here.
FIRST_LINES = ((semantic_probe.RED_TEAM_PROMPT.splitlines()[0], PROBE_PROMPT),
               (planner.PROMPT_TEMPLATE.splitlines()[0], PLANNER_PROMPT))


def classify(prompt: str) -> str:
    """Say which kind of prompt this is, or refuse to guess.

    `ValueError`, never `RuntimeError`: `planner.order_checks` and
    `semantic_probe.judge` both catch `RuntimeError` from the ask function and
    file it as "the model could not be reached", so raising that here would
    write this study's own wiring bug into the artifact as an absent model.
    """
    for first_line, kind in FIRST_LINES:
        if prompt.startswith(first_line):
            return kind
    raise ValueError(
        "a prompt reached the model that this study cannot classify, so what it "
        f"transmitted cannot be stated: {prompt[:60]!r}...")


def field_kinds(kinds: list[str]) -> list[str]:
    """Every field kind the recorded prompts actually carried, sorted and deduplicated."""
    return sorted({field for kind in kinds for field in FIELD_KINDS[kind]})

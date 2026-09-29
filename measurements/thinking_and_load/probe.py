"""Two probes of one council prompt: does `think` change a reply, and does the model's load state?

`council.ollama` pins `think` to false for every member, and these probes are the
evidence for that pin and for the precondition on reproducibility they turned
up. Both ask one prompt, `build_prompt("AV", ADVISORY)`, built and pinned by the
product's own `build_request`, and vary only the `think` field and whether the
models were unloaded first. Every envelope is written whole, but for its token ids.

    thinking     per model: from a fresh load, `think` absent, then `think` false
    load-state   per model: cold absent, warm absent, warm false, cold false,
                 warm false again -- and with --with-true, then warm true

**Cold** is the first call after every probed model was unloaded. **Warm** is a
call straight after the one before it, on the model that call left loaded.

The two `.jsonl` files beside this script are what it records; `README.md`
says when they were taken, on what, and how they differ from a run of this file.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO

from council.ollama import LocalModel, build_request, generate_url
from council.prompt import build_prompt
from council.transport import post_json

# `tests/council/council_samples.ADVISORY`, which the recorded probes asked about.
# Copied rather than imported so a measurement does not lean on the test tree;
# `tests/measurements/thinking_and_load/test_probe.py` holds the two equal.
ADVISORY = (
    "A flaw was found in the web console. An unauthenticated remote attacker can\n"
    "send a crafted request to the management port and read arbitrary files from\n"
    "the host's filesystem. The component does not validate the supplied path."
)
METRIC = "AV"

ABSENT = "absent"
FALSE = "false"
TRUE = "true"
THINKING = "thinking"
LOAD_STATE = "load-state"
# The recorded files name a step under a different field in each probe.
LABEL_FIELD = {THINKING: "think", LOAD_STATE: "label"}
UNLOADED = "unload"
# The token ids of the prompt and the reply: long, and nothing reads them.
DROPPED_FIELDS = ("context",)

Post = Callable[[str, dict[str, Any]], Any]


@dataclass(frozen=True)
class Step:
    """One call of a probe: its name, the `think` it sends, and whether it starts cold."""

    label: str
    think: str
    cold: bool


STEPS = {
    THINKING: (Step(ABSENT, ABSENT, cold=True), Step(FALSE, FALSE, cold=False)),
    LOAD_STATE: (
        Step("cold, field absent", ABSENT, cold=True),
        Step("warm, field absent", ABSENT, cold=False),
        Step("warm, think false", FALSE, cold=False),
        Step("cold, think false", FALSE, cold=True),
        Step("warm, think false again", FALSE, cold=False),
    ),
}
THINK_TRUE = Step("warm, think true", TRUE, cold=False)


def request_for(think: str, pinning: LocalModel) -> dict[str, Any]:
    """Build the product's request for the probe prompt, with `think` absent, false or true."""
    request = build_request(build_prompt(METRIC, ADVISORY), pinning)
    request.pop("think", None)
    if think == ABSENT:
        return request
    return {**request, "think": think == TRUE}


def unload_every_model(post: Post, models: tuple[str, ...]) -> None:
    """Unload every probed model, so the next call starts from a fresh load."""
    for model in models:
        said = post(generate_url(LocalModel(model=model)), {"model": model, "keep_alive": 0})
        if said.get("done_reason") != UNLOADED:
            raise RuntimeError(f"asked to unload {model}, the server answered {said!r}")


def kept(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Keep an envelope whole, but for the token ids nothing reads."""
    return {name: value for name, value in envelope.items() if name not in DROPPED_FIELDS}


def line_of(probe: str, model: str, step: Step, envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Give one call as a line of the recorded file for its probe."""
    return {"model": model, LABEL_FIELD[probe]: step.label, "envelope": kept(envelope)}


def run(
    probe: str,
    steps: tuple[Step, ...],
    models: tuple[str, ...],
    out: TextIO,
    post: Post = post_json,
) -> None:
    """Ask every model every step in order, writing each envelope as it comes back."""
    for model, step in product(models, steps):
        if step.cold:
            unload_every_model(post, models)
        pinning = LocalModel(model=model)
        envelope = post(generate_url(pinning), request_for(step.think, pinning))
        out.write(json.dumps(line_of(probe, model, step, envelope)) + "\n")
        out.flush()


def main(argv: list[str]) -> int:
    """Run one probe into a new file, never over one already recorded."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("probe", choices=tuple(STEPS))
    parser.add_argument("models", nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--with-true", action="store_true", help="end with warm, think true")
    options = parser.parse_args(argv)
    steps = STEPS[options.probe] + ((THINK_TRUE,) if options.with_true else ())
    with options.out.open("x", encoding="utf-8") as out:
        run(options.probe, steps, tuple(options.models), out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

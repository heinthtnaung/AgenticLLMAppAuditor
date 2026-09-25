"""Reply shapes a newer model may send: recorded where a pulled model showed them, made up if not.

The recorded ones are in `recorded_shapes.json`, taken on 2026-09-25 from this
machine's Ollama 0.34.3 with the product's own request: what
`qwen2.5-coder:7b-instruct` and `gemma4:latest` answered, what the server said
to a model that cannot generate and to a `think` the model does not support,
and `gemma4:latest` asked with `think` true and no `format`, which is the one
envelope here that carries reasoning.

The made-up ones are the shapes no pulled model has sent the product's request,
each named for what it stands in for. Nothing here asks a model.
"""

import json
from pathlib import Path

RECORDED = json.loads((Path(__file__).parent / "recorded_shapes.json").read_text("utf-8"))

ANSWERED = RECORDED["answered"]
REFUSED = RECORDED["refused"]
THINKING_WITHOUT_FORMAT = RECORDED["thinking without format"]

DRAFT = '{"value": "L", "evidence": "the host", "confidence": "low"}'
ANSWER = '{"value": "N", "evidence": "unauthenticated remote attacker", "confidence": "high"}'

# Made up: a model that thinks whatever `think` says, drafting in its reasoning.
THINKS_ANYWAY = {
    "model": "thinks-anyway:1b",
    "thinking": f"The attacker is remote. A first draft: {DRAFT}. No, it is network.",
    "response": ANSWER,
    "done_reason": "stop",
}

# Made up: a model that reasoned until the window ran out and never answered.
REASONED_OUT = {
    "model": "reasons-long:1b",
    "thinking": "The attacker is remote, but " * 200,
    "response": "",
    "done_reason": "length",
}

# Made up: an answer stopped part way, as a window too small for a long reply leaves it.
CUT_OFF = {"model": "cut-off:1b", "response": '{"value": "N", "evid', "done_reason": "length"}

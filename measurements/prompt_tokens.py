"""What a member's prompt really costs each model, counted by the model itself.

Run it: `python measurements/prompt_tokens.py [MODEL ...]`, with the operator's
`AUDITOR_MODEL` when none is named. **This one needs `ollama serve` up with each model pulled**,
unlike the other measurement here. It talks to loopback only, through
`council.transport`, which bypasses the corporate proxy rather than relying on
NO_PROXY being exported.

It answers two questions `council.ollama` states as fact: what the prompt costs
with no advisory in it, and what the worst advisory in the corpus takes it to.
Those two numbers are why the window stays at 8,192 by default and why
`refuse_overlong_prompt` exists. It also prints the error of the four-characters
-to-the-token estimate that guard uses, per model, because every model has its
own tokenizer and the estimate was first checked against Qwen's alone.

The request is the product's own, from `build_request` -- `think` false and the
JSON format included -- with only the window widened so nothing is cut, and one
token generated.
"""

import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advisories import advisory_texts  # noqa: E402
from council_eval.pass_provenance import (  # noqa: E402
    TAGS_PATH,
    VERSION_PATH,
    get_json,
    model_digest,
)
from council.ollama import (  # noqa: E402
    USABLE_CONTEXT_FRACTION,
    LocalModel,
    build_request,
    estimated_tokens,
    generate_url,
)
from council.prompt import PROMPT_VERSION, MemberPrompt, build_prompt  # noqa: E402
from council.settings import current_settings  # noqa: E402
from council.transport import Transport, post_json  # noqa: E402

PROMPT_TOKEN_FIELD = "prompt_eval_count"

Get = Callable[[str], Any]

# The widest definitions of the eight, so a cost measured here is the worst one.
WIDEST_METRIC = "AC"

# Enough advisory to build a prompt, and too little to measure. Subtracting this
# prompt's cost from a real one gives what the advisory itself cost.
ALMOST_NO_ADVISORY = "A flaw was found."

# The whole window, so the model counts a prompt rather than refusing it. This
# is a measurement, not a run: `AUDITOR_CONTEXT_TOKENS` is what a member uses.
MEASURING_CONTEXT_TOKENS = 32_768

GENERATE_ONE_TOKEN = 1


def count_tokens(prompt: MemberPrompt, model: str, post: Transport = post_json) -> int:
    """Ask one model how many tokens a prompt is, sent as a member sends it, generating one."""
    pinning = LocalModel(model=model, context_tokens=MEASURING_CONTEXT_TOKENS)
    request = build_request(prompt, pinning)
    request["options"]["num_predict"] = GENERATE_ONE_TOKEN
    counted = post(generate_url(pinning), request).get(PROMPT_TOKEN_FIELD)
    if not isinstance(counted, int):
        raise ValueError(f"{model} returned no {PROMPT_TOKEN_FIELD} to read")
    return counted


def longest_advisory() -> tuple[str, str]:
    """Give the id and text of the longest advisory in the corpus."""
    texts = advisory_texts()
    advisory_id = max(texts, key=lambda key: len(texts[key]))
    return advisory_id, texts[advisory_id]


def model_lines(
    model: str, fixed: MemberPrompt, worst: MemberPrompt, post: Transport = post_json
) -> list[str]:
    """Say what one model counts both prompts at, and how far the guard's estimate is off."""
    empty, counted = count_tokens(fixed, model, post), count_tokens(worst, model, post)
    estimated = estimated_tokens(worst)
    # What the model would count a prompt at that the guard just lets through.
    window = current_settings().context_tokens
    at_limit = round(window * USABLE_CONTEXT_FRACTION * counted / estimated)
    return [
        f"  a prompt with almost no advisory in it: {empty} tokens",
        f"  the longest advisory's prompt: {counted} tokens, of which the advisory is "
        f"{counted - empty}",
        f"  estimated by the guard: {estimated} tokens, off by {counted - estimated:+d} "
        f"({(counted - estimated) / estimated:+.1%})",
        f"  a prompt at the guard's limit: about {at_limit} of the {window} pinned",
    ]


def main(argv: list[str], post: Transport = post_json, get: Get = get_json) -> int:
    """Print what was asked of which weights, then each model's costs and the estimate's error."""
    advisory_id, text = longest_advisory()
    server = current_settings().server
    tags = get(f"{server}{TAGS_PATH}")
    ollama = get(f"{server}{VERSION_PATH}")["version"]
    print(f"prompt {PROMPT_VERSION}, Ollama {ollama}")
    print(f"the longest advisory, {advisory_id}: {len(text)} characters")
    fixed = build_prompt(WIDEST_METRIC, ALMOST_NO_ADVISORY)
    worst = build_prompt(WIDEST_METRIC, text)
    for model in tuple(argv) or (current_settings().model,):
        print(f"{model} {model_digest(model, tags)}")
        print("\n".join(model_lines(model, fixed, worst, post)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

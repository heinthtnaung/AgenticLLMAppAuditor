"""What a member's prompt really costs the pinned model, counted by the model itself.

Run it: `python measurements/prompt_tokens.py`. **This one needs `ollama serve`
up with the pinned model pulled**, unlike the other measurement here. It talks
to loopback only, through `council.transport`, which bypasses the corporate
proxy rather than relying on NO_PROXY being exported.

It answers two questions `council.ollama` states as fact: what the prompt costs
with no advisory in it, and what the worst advisory in the corpus takes it to.
Those two numbers are why `DEFAULT_CONTEXT_TOKENS` stays at 8,192 and why
`refuse_overlong_prompt` exists. It also prints the error of the four-characters
-to-the-token estimate that guard uses, which is the only thing making a rough
estimate acceptable there.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advisories import advisory_texts  # noqa: E402
from council.ollama import (  # noqa: E402
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_SEED,
    PINNED_TEMPERATURE,
    estimated_tokens,
    generate_url,
    LocalModel,
)
from council.prompt import MemberPrompt, build_prompt  # noqa: E402
from council.transport import post_json  # noqa: E402

PROMPT_TOKEN_FIELD = "prompt_eval_count"

# The widest definitions of the eight, so a cost measured here is the worst one.
WIDEST_METRIC = "AC"

# Enough advisory to build a prompt, and too little to measure. Subtracting this
# prompt's cost from a real one gives what the advisory itself cost.
ALMOST_NO_ADVISORY = "A flaw was found."

# The whole window, so the model counts a prompt rather than refusing it. This
# is a measurement, not a run: `DEFAULT_CONTEXT_TOKENS` is what a member uses.
MEASURING_CONTEXT_TOKENS = 32_768

GENERATE_ONE_TOKEN = 1


def count_tokens(prompt: MemberPrompt) -> int:
    """Ask the pinned model how many tokens a prompt is, generating almost nothing."""
    envelope = post_json(
        generate_url(LocalModel()),
        {
            "model": DEFAULT_MODEL,
            "system": prompt.system,
            "prompt": prompt.user,
            "stream": False,
            "options": {
                "temperature": PINNED_TEMPERATURE,
                "seed": DEFAULT_SEED,
                "num_ctx": MEASURING_CONTEXT_TOKENS,
                "num_predict": GENERATE_ONE_TOKEN,
            },
        },
    )
    counted = envelope.get(PROMPT_TOKEN_FIELD)
    if not isinstance(counted, int):
        raise ValueError(f"{DEFAULT_MODEL} returned no {PROMPT_TOKEN_FIELD} to read")
    return counted


def longest_advisory() -> tuple[str, str]:
    """Give the id and text of the longest advisory in the corpus."""
    texts = advisory_texts()
    advisory_id = max(texts, key=lambda key: len(texts[key]))
    return advisory_id, texts[advisory_id]


def main() -> None:
    """Print the fixed cost of a prompt, the worst advisory's cost, and the estimate's error."""
    fixed = count_tokens(build_prompt(WIDEST_METRIC, ALMOST_NO_ADVISORY))
    print(f"a prompt with almost no advisory in it: {fixed} tokens")

    advisory_id, text = longest_advisory()
    worst = build_prompt(WIDEST_METRIC, text)
    counted = count_tokens(worst)
    estimated = estimated_tokens(worst)
    print(f"the longest advisory, {advisory_id}: {len(text)} characters")
    print(f"  counted by the model: {counted} tokens, of which the advisory is {counted - fixed}")
    print(f"  estimated by the guard: {estimated} tokens, off by {abs(counted - estimated)}")
    margin = DEFAULT_CONTEXT_TOKENS / counted
    print(f"  against {DEFAULT_CONTEXT_TOKENS} pinned: a margin of {margin:.1f}x")


if __name__ == "__main__":
    main()

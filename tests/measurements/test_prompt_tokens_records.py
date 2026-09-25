"""The recorded token counts hold up the guard's two fractions, and name every model they rest on.

These read `measurements/prompt_tokens.2026-09-25.txt` and the council
evaluation's saved passes, and ask no model. A model counted later, or a pass
recorded on one, changes what the fractions in `council.ollama` rest on, and a
test here says so by failing.
"""

import re
import sys
from itertools import chain
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "measurements"))

from cli.council_run import advisory_text  # noqa: E402
from council.ollama import (  # noqa: E402
    CUT_PROMPT_FRACTION,
    USABLE_CONTEXT_FRACTION,
    estimated_tokens,
)
from council.prompt import build_prompt  # noqa: E402
from council_eval.dataset import read_dataset  # noqa: E402
from council_eval.replies import read_replies  # noqa: E402
from council_eval.dataset import Item  # noqa: E402
from council_eval.recording import CallRecord  # noqa: E402
from council_eval.variants import Variant, variant_asked, variant_prompt  # noqa: E402

RECORD = ROOT / "measurements" / "prompt_tokens.2026-09-25.txt"
RUNS = ROOT / "measurements" / "council_eval_runs"
COUNTED = re.compile(
    r"^(\S+) [0-9a-f]{64}\n.*?prompt: (\d+) tokens.*?guard: (\d+) tokens", re.M | re.S
)
# The share of the window a prompt at the guard's limit must leave for the reply.
REPLY_ROOM = 1 / 8
# Ollama cuts an overlong prompt to half the window, so a cut one counts under half.
CUT_TO = 0.5


def worst_prompt_ratios() -> dict[str, float]:
    """Give each model's count of the worst prompt over the guard's estimate of it."""
    found = COUNTED.findall(RECORD.read_text(encoding="utf-8"))
    return {model: int(counted) / int(estimated) for model, counted, estimated in found}


def recorded_ratios() -> list[tuple[str, float]]:
    """Give every saved call's model, and its count over the estimate of the prompt it answered."""
    dataset = read_dataset(RUNS / "pilot-vulnscout" / "vulnscout.dataset.json")
    items = {item.key: item for item in dataset}
    passes = sorted(RUNS.glob("*/*.run1.replies.jsonl"))
    return list(chain.from_iterable(pass_ratios(path, items) for path in passes))


def pass_ratios(path: Path, items: dict[str, Item]) -> list[tuple[str, float]]:
    """Give one saved pass's calls by model, each count over the estimate of its prompt."""
    replies = read_replies((path,))
    variant = variant_asked(replies.headers[0]["prompt_version"])
    calls = replies.calls.items()
    return [
        (model, ratio(call, items[key], metric, variant)) for (key, model, metric), call in calls
    ]


def ratio(call: CallRecord, item: Item, metric: str, variant: Variant) -> float:
    """Give one call's count over the estimate of the prompt it was sent."""
    prompt = variant_prompt(build_prompt(metric, advisory_text(item.finding)), variant)
    return call.envelope["prompt_eval_count"] / estimated_tokens(prompt)


def test_the_worst_prompt_has_been_counted_by_these_models_only():
    # A known gap, asserted: a model not pulled here tokenizes in a way nothing
    # measured, and a new count turns this red and the fractions due a look.
    assert set(worst_prompt_ratios()) == {
        "qwen2.5:7b-instruct", "llama3.2:latest", "gemma4:latest", "qwen2.5-coder:7b-instruct",
    }


def test_a_prompt_at_the_guard_s_limit_leaves_room_to_reply_for_every_model_counted():
    worst = max(worst_prompt_ratios().values())
    assert USABLE_CONTEXT_FRACTION * worst <= 1 - REPLY_ROOM


def test_a_cut_prompt_counts_under_the_cut_line_for_every_model_counted():
    assert CUT_TO * max(worst_prompt_ratios().values()) < CUT_PROMPT_FRACTION


def spread(model: str) -> tuple[float, float]:
    """Give the lowest and highest count-over-estimate of one model's saved calls, to 3 places."""
    own = [value for asked, value in recorded_ratios() if asked == model]
    return round(min(own), 3), round(max(own), 3)


def test_no_saved_call_to_a_whole_prompt_would_be_read_as_cut():
    ratios = [value for _, value in recorded_ratios()]
    assert len(ratios) == 1152
    assert min(ratios) > CUT_PROMPT_FRACTION


def test_the_saved_calls_count_their_prompts_within_these_spreads():
    # 576 calls per model: each model's first pilot pass and the three variant
    # cells'. Qwen runs from 17% under the estimate to 15% over it.
    assert spread("qwen2.5:7b-instruct") == (0.831, 1.152)
    assert spread("llama3.2:latest") == (0.844, 1.098)

"""What Qwen answered to a prompt Ollama cut, held to the recordings `docs/COUNCIL.md` cites.

Sent to a 256-token window, the AV prompt for `council_samples.ADVISORY`, 532
tokens read whole, was cut to 130, and Qwen still answered: a value the whole
advisory does not get, at medium confidence, quoting a sentence of the advisory.
So the answer reads like any other and the quotation check passes it; only the
count the server reports gives the cut away, which `test_ollama_context.py`
holds `refuse_cut_prompt` to. These read the recordings and ask no model.
"""

import json
from pathlib import Path

from council.answer import Confidence, MemberReply
from council.evidence import is_quotation_from
from council.ollama import estimated_tokens
from council.prompt import build_prompt
from council.reply import read_reply

from council_samples import ADVISORY, identity
from model_shapes import CUT_PROMPTS

PROBE_STATE = (
    Path(__file__).resolve().parents[2] / "measurements" / "thinking_and_load" / "probe_state.jsonl"
)
QWEN = "qwen2.5:7b-instruct"
CUT_IN_256 = f"{QWEN} in 256"
METRIC = "AV"
# What the recording says it sent, so the prompt rebuilt here is known to be that one.
RECORDED_PROMPT = f"build_prompt({METRIC!r}, council_samples.ADVISORY)"


def read_as_the_council_would(envelope: dict) -> MemberReply:
    """Read one recorded envelope's reply into what the council would weigh."""
    return read_reply(envelope["response"], METRIC, identity(QWEN, model=QWEN))


def whole_prompt_envelopes() -> list[dict]:
    """Give every envelope Qwen returned to the same AV prompt in the 8,192 window."""
    records = [json.loads(line) for line in PROBE_STATE.read_text("utf-8").splitlines()]
    return [record["envelope"] for record in records if record["model"] == QWEN]


def test_cut_to_130_tokens_in_a_256_window_qwen_answered_attack_vector_p_at_medium():
    """The cut answer the document quotes: `P`, where the whole advisory gets `N`."""
    cut = CUT_PROMPTS[CUT_IN_256]
    assert (cut["num_ctx"], cut["envelope"]["prompt_eval_count"]) == (256, 130)
    answer = read_as_the_council_would(cut["envelope"])
    assert (answer.value, answer.confidence) == ("P", Confidence.MEDIUM)


def test_read_whole_the_same_prompt_gets_attack_vector_n_from_qwen_every_time():
    """The whole prompt, counted at 532, gets `N` in every load state recorded."""
    envelopes = whole_prompt_envelopes()
    assert envelopes, f"no {QWEN} envelope in {PROBE_STATE}"
    assert {one["prompt_eval_count"] for one in envelopes} == {532}
    assert {read_as_the_council_would(one).value for one in envelopes} == {"N"}


def test_the_cut_answer_s_quotation_passes_the_council_s_quotation_check():
    """Nothing in the cut answer's evidence would stop the council weighing it."""
    cut = CUT_PROMPTS[CUT_IN_256]
    shown = build_prompt(METRIC, ADVISORY)
    assert (cut["prompt"], cut["estimated"]) == (RECORDED_PROMPT, estimated_tokens(shown))
    answer = read_as_the_council_would(cut["envelope"])
    assert is_quotation_from(answer.evidence, shown.advisory_shown)

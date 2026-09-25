"""The one test that really asks the model, skipped unless it is asked for.

Everything else in `tests/council` runs against recordings. This one is here so
that a recording can be checked against the thing it recorded, and it is off by
default because a suite that needs a 4.7GB model running is a suite nobody runs:

    COUNCIL_LIVE_OLLAMA=1 python -m pytest tests/council/test_ollama_live.py

It asks the default model unless `COUNCIL_LIVE_MODEL` names another, so a newer
model is checked the same way before it joins a council:

    COUNCIL_LIVE_OLLAMA=1 COUNCIL_LIVE_MODEL=gemma4:latest python -m pytest ...

It needs `ollama serve` up with that model pulled, and skips naming the model
when it is not. It cannot be caught by the proxy that answers 502 for loopback,
because `council.transport` bypasses the proxy rather than relying on NO_PROXY
being exported.
"""

import json
import os

import pytest

from council.answer import MemberAnswer, MemberFoundNoEvidence, MemberIdentity
from council.evidence import is_quotation_from
from council.ollama import LocalModel, ask, generate_url
from council.prompt import PROMPT_VERSION, build_prompt
from council.reply import read_reply
from council.settings import current_settings
from council.transport import NO_PROXY_OPENER, post_json
from council_samples import ADVISORY

LIVE = "COUNCIL_LIVE_OLLAMA"
# Not a flag: which model to ask, for an operator trying one the pair is not.
MODEL_VARIABLE = "COUNCIL_LIVE_MODEL"
# Otherwise the default in `council.settings`: no test reads the operator's `.env`.
MODEL = os.environ.get(MODEL_VARIABLE) or current_settings().model
FAMILY_SEPARATOR = ":"
# The tag Ollama assumes when a name carries none, as `llama3.2` for `llama3.2:latest`.
DEFAULT_TAG = ":latest"
TAGS_PATH = "/api/tags"
TAGS_TIMEOUT_SECONDS = 10
# What Ollama answers a request to keep a model loaded for no time.
UNLOADED = "unload"

pytestmark = pytest.mark.skipif(
    not os.environ.get(LIVE), reason=f"set {LIVE}=1 to ask the local model for real"
)

MEMBER = MemberIdentity(
    name=MODEL,
    provider="ollama",
    model=MODEL,
    family=MODEL.split(FAMILY_SEPARATOR)[0],
    ran_local=True,
    prompt_version=PROMPT_VERSION,
)


def held_models() -> set[str]:
    """Name the models this machine's Ollama holds, failing loudly if it is not there."""
    url = f"{current_settings().server}{TAGS_PATH}"
    try:
        with NO_PROXY_OPENER.open(url, timeout=TAGS_TIMEOUT_SECONDS) as response:
            tags = json.loads(response.read().decode("utf-8"))
    except OSError as fault:
        pytest.fail(f"{url} could not be reached, so no model can be asked: {fault}")
    return {entry["name"] for entry in tags.get("models", [])}


@pytest.fixture(autouse=True, scope="module")
def model_is_pulled() -> None:
    """Skip, naming the model, when the one asked for is not pulled here."""
    held = held_models()
    if MODEL in held or f"{MODEL}{DEFAULT_TAG}" in held:
        return
    pytest.skip(f"{MODEL} is not pulled here; pull it, or set {MODEL_VARIABLE} to one that is")


def test_the_model_answers_a_metric_in_the_shape_the_council_reads():
    reply = ask(build_prompt("AV", ADVISORY), LocalModel(model=MODEL))
    answer = read_reply(reply.text, "AV", MEMBER)
    assert isinstance(answer, (MemberAnswer, MemberFoundNoEvidence))


def test_a_real_answer_quotes_the_advisory_it_was_given():
    asked = build_prompt("AV", ADVISORY)
    answer = read_reply(ask(asked, LocalModel(model=MODEL)).text, "AV", MEMBER)
    if isinstance(answer, MemberFoundNoEvidence):
        pytest.skip("the model declined this metric, which is a result and not a failure")
    assert is_quotation_from(answer.evidence, asked.advisory_shown)


def cold_answer(asked, pinning: LocalModel) -> str:
    """Ask once from a freshly loaded model, the state every council member's turn starts in."""
    unloaded = post_json(generate_url(pinning), {"model": pinning.model, "keep_alive": 0})
    assert unloaded.get("done_reason") == UNLOADED, f"{pinning.model} was not unloaded: {unloaded}"
    return ask(asked, pinning).text


def test_the_same_question_twice_gets_the_same_answer():
    """Two calls that each start from a fresh load give the same reply, byte for byte.

    The one thing a local member has that a hosted one does not, and it holds
    **for one load state**. Measured on Ollama 0.34.3 on this machine's GPU, the
    pinned model answers this prompt with a different confidence straight after
    the same prompt than from a fresh load, each state repeating itself. So both
    calls here start cold, as every member's turn does in the recorded council
    runs; before they did, this test passed only because the tests above had
    warmed the model.

    Not tested: that a warm call agrees with a cold one. It does not always, and
    whether it does depends on the hardware, so nothing asserts either way; a run
    is reproducible only against a run in the same load state. What this catches
    is the pinning failing -- a temperature that samples, a seed not sent, a
    request that varies between calls -- which would make two cold calls differ.
    """
    asked = build_prompt("AV", ADVISORY)
    pinning = LocalModel(model=MODEL)
    assert cold_answer(asked, pinning) == cold_answer(asked, pinning)

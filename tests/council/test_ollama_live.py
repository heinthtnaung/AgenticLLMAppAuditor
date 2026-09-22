"""The one test that really asks the model, skipped unless it is asked for.

Everything else in `tests/council` runs against recordings. This one is here so
that a recording can be checked against the thing it recorded, and it is off by
default because a suite that needs a 4.7GB model running is a suite nobody runs:

    COUNCIL_LIVE_OLLAMA=1 python -m pytest tests/council/test_ollama_live.py

It needs `ollama serve` up with the pinned model pulled. It cannot be caught by
the proxy that answers 502 for loopback, because `council.transport` bypasses
the proxy rather than relying on NO_PROXY being exported.
"""

import os

import pytest

from council.answer import MemberAnswer, MemberFoundNoEvidence, MemberIdentity
from council.evidence import is_quotation_from
from council.ollama import DEFAULT_MODEL, LocalModel, ask
from council.prompt import PROMPT_VERSION, build_prompt
from council.reply import read_reply
from council_samples import ADVISORY

LIVE = "COUNCIL_LIVE_OLLAMA"

pytestmark = pytest.mark.skipif(
    not os.environ.get(LIVE), reason=f"set {LIVE}=1 to ask the local model for real"
)

MEMBER = MemberIdentity(
    name="small-local",
    provider="ollama",
    model=DEFAULT_MODEL,
    family="qwen",
    ran_local=True,
    prompt_version=PROMPT_VERSION,
)


def test_the_pinned_model_answers_a_metric_in_the_shape_the_council_reads():
    reply = ask(build_prompt("AV", ADVISORY), LocalModel())
    answer = read_reply(reply.text, "AV", MEMBER)
    assert isinstance(answer, (MemberAnswer, MemberFoundNoEvidence))


def test_a_real_answer_quotes_the_advisory_it_was_given():
    asked = build_prompt("AV", ADVISORY)
    answer = read_reply(ask(asked, LocalModel()).text, "AV", MEMBER)
    if isinstance(answer, MemberFoundNoEvidence):
        pytest.skip("the model declined this metric, which is a result and not a failure")
    assert is_quotation_from(answer.evidence, asked.advisory_shown)


def test_the_same_question_twice_gets_the_same_answer():
    # The one thing a local member has that a hosted one does not. If this fails
    # the pinning is not pinning anything and `docs/COUNCIL.md`'s reproducibility
    # claim is wrong.
    asked = build_prompt("AV", ADVISORY)
    assert ask(asked, LocalModel()).text == ask(asked, LocalModel()).text

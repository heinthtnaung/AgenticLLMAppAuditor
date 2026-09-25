"""Guards on the local member: pinned, loopback only, and never called in a test."""

import pytest

import recorded_replies as recorded
from council.ollama import (
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_MODEL,
    GENERATE_PATH,
    LocalModel,
    ask,
    build_request,
    generate_url,
)
from council.prompt import build_prompt
from council.reply import read_reply
from council.transport import ModelUnavailable
from council_samples import ADVISORY, identity

PROMPT = build_prompt("AV", ADVISORY)
MEMBER = identity()

# The longest advisory of the 1,187 read off this machine's database snapshot,
# in characters. The pinned model counted its prompt at 4,897 tokens.
LONGEST_ADVISORY_CHARACTERS = 17_893


class Recorded:
    """A transport stand-in: it answers from a recording and remembers the call."""

    def __init__(self, envelope) -> None:
        """Hold the envelope this fake server will answer with."""
        self.envelope = envelope
        self.url = None
        self.payload = None

    def __call__(self, url, payload):
        """Answer one request, keeping what was asked."""
        self.url = url
        self.payload = payload
        return self.envelope


def answering(text: str, model: str = DEFAULT_MODEL) -> Recorded:
    """Build a transport that answers with one reply, as Ollama envelopes it."""
    return Recorded({"model": model, "response": text, "done": True})


def test_the_model_is_pinned_and_not_left_to_a_default():
    request = build_request(PROMPT, LocalModel())
    assert request["model"] == DEFAULT_MODEL
    assert request["options"]["seed"] == LocalModel().seed


def test_a_member_does_not_sample():
    # The literal 0 is the test. Asserting against `PINNED_TEMPERATURE` compares
    # the constant with itself and passes at 0.8 as readily as at 0, and
    # temperature is the one pinning that is deliberately not configurable: a
    # member that samples is a different instrument and the record would still
    # call the run reproducible. `seed` and `num_ctx` are fields, so reading them
    # off `LocalModel()` is the right check there -- it is plumbing that is under
    # test, not a value.
    assert build_request(PROMPT, LocalModel())["options"]["temperature"] == 0


def test_a_member_is_asked_not_to_think():
    # The literal False is the test, as with temperature. Left out, each model's
    # default decides, and `gemma4:latest`'s is to think: its reply moves.
    assert build_request(PROMPT, LocalModel())["think"] is False


def test_the_thinking_setting_is_sent_where_the_server_reads_it():
    # Ollama's API takes `think` at the top of the request, not among the options.
    assert "think" not in build_request(PROMPT, LocalModel())["options"]


def test_the_context_length_is_set_so_a_long_advisory_is_not_silently_cut():
    assert build_request(PROMPT, LocalModel())["options"]["num_ctx"] == LocalModel().context_tokens


def test_the_worst_advisory_yet_measured_still_fits_and_is_not_refused():
    # The guard below must not fire on anything real. If this fails, an advisory
    # in the corpus has outgrown the pinned window and the number is the
    # evidence for raising it -- which is a decision, not a default.
    longest = "word " * (LONGEST_ADVISORY_CHARACTERS // len("word "))
    assert build_request(build_prompt("AC", longest), LocalModel())["prompt"]


def test_a_prompt_too_long_for_the_window_is_refused_and_not_quietly_cut():
    # The failure this guard exists for: Ollama truncates without saying so, the
    # member assesses part of an advisory, and the record shows a confident
    # answer with nothing to say most of the text was missing.
    overlong = "word " * DEFAULT_CONTEXT_TOKENS
    with pytest.raises(ValueError, match="would assess part of the advisory"):
        build_request(build_prompt("AV", overlong), LocalModel())


def test_the_refusal_says_how_much_too_long_the_prompt_was():
    overlong = "word " * DEFAULT_CONTEXT_TOKENS
    with pytest.raises(ValueError, match=r"roughly \d+ tokens, about \d+ more than"):
        build_request(build_prompt("AV", overlong), LocalModel())


def test_nothing_is_sent_to_the_server_when_the_prompt_will_not_fit():
    # Refusing after the call would still have truncated the advisory.
    transport = answering(recorded.ATTACK_VECTOR)
    with pytest.raises(ValueError, match="pinned to"):
        ask(build_prompt("AV", "word " * DEFAULT_CONTEXT_TOKENS), LocalModel(), transport)
    assert transport.url is None


def test_a_smaller_window_refuses_what_the_pinned_one_accepts():
    # The guard reads the member's own pinning, not the default.
    asked = build_prompt("AV", "word " * 400)
    assert build_request(asked, LocalModel())["prompt"]
    with pytest.raises(ValueError, match="is pinned to"):
        build_request(asked, LocalModel(context_tokens=256))


def test_the_reply_is_asked_for_as_json_and_not_streamed():
    request = build_request(PROMPT, LocalModel())
    assert request["format"] == "json"
    assert request["stream"] is False


def test_both_halves_of_the_prompt_are_sent():
    request = build_request(PROMPT, LocalModel())
    assert request["system"] == PROMPT.system
    assert request["prompt"] == PROMPT.user


def test_a_member_is_asked_at_the_generate_endpoint():
    transport = answering(recorded.ATTACK_VECTOR)
    ask(PROMPT, LocalModel(), transport)
    assert transport.url == f"http://127.0.0.1:11434{GENERATE_PATH}"


def test_what_came_back_is_the_text_and_the_model_that_wrote_it():
    reply = ask(PROMPT, LocalModel(), answering(recorded.ATTACK_VECTOR))
    assert reply.text == recorded.ATTACK_VECTOR
    assert reply.model == DEFAULT_MODEL


def test_the_model_the_server_names_is_kept_over_the_one_that_was_asked_for():
    # A pinning is only worth what the record says actually answered.
    reply = ask(PROMPT, LocalModel(), answering(recorded.ATTACK_VECTOR, "qwen2.5:7b-instruct-q4"))
    assert reply.model == "qwen2.5:7b-instruct-q4"


def test_a_server_that_names_no_model_leaves_the_pinned_name_standing():
    # The one case where `ModelReply.model` is a claim and not an observation,
    # and nothing downstream can tell which it is holding. Ollama has named the
    # model on every reply seen, so this is the path that opens if it stops.
    transport = Recorded({"response": recorded.ATTACK_VECTOR, "done": True})
    assert ask(PROMPT, LocalModel(), transport).model == DEFAULT_MODEL


def test_a_member_answers_end_to_end_into_the_council_s_own_contract():
    reply = ask(PROMPT, LocalModel(), answering(recorded.ATTACK_VECTOR))
    answer = read_reply(reply.text, PROMPT.metric, MEMBER)
    assert (answer.metric, answer.value) == ("AV", "N")


def test_a_server_that_refused_is_reported_and_not_parsed():
    transport = Recorded({"error": "model 'qwen9' not found"})
    with pytest.raises(ModelUnavailable, match="refused the request"):
        ask(PROMPT, LocalModel(), transport)


def test_an_envelope_with_no_answer_in_it_is_refused():
    with pytest.raises(ModelUnavailable, match="answered with no text"):
        ask(PROMPT, LocalModel(), Recorded({"model": DEFAULT_MODEL, "response": "  "}))


def test_an_envelope_that_is_not_an_object_is_refused():
    with pytest.raises(ModelUnavailable, match="returned list, not an object"):
        ask(PROMPT, LocalModel(), Recorded([1, 2, 3]))


@pytest.mark.parametrize("host", ["http://localhost:11434", "http://127.0.0.1:11434"])
def test_this_machine_is_where_a_local_member_runs(host):
    assert generate_url(LocalModel(host=host)).endswith(GENERATE_PATH)


def test_a_model_somewhere_else_is_not_a_local_member():
    # `ran_local` on the record would otherwise be a lie, and the record is the
    # only thing that says whether the advisory text left this machine.
    with pytest.raises(ValueError, match="is not this machine"):
        LocalModel(host="http://ollama.example.com:11434")


def test_a_member_that_names_no_model_is_refused():
    with pytest.raises(ValueError, match="must name the model"):
        LocalModel(model="")


def test_a_member_with_no_context_to_read_in_is_refused():
    with pytest.raises(ValueError, match="needs a context length"):
        LocalModel(context_tokens=0)

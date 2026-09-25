"""Guards on rebuilding a roster offline: the record the product would write asking it live."""

from itertools import chain

import pytest

import eval_samples as samples
from cli.council_run import OLLAMA_PROVIDER, assess_one, build_roster
from council.prompt import PROMPT_VERSION
from council_eval.collect import ask_item
from council_eval.compose import pass_models, replay_roster, rosters
from council_eval.recording import RecordingClient
from council_eval.replies import Replies
from council_eval.variants import BASELINE, LIBRARY, REVERSED, Variant

# The second member disagrees on AV with a verified quotation, and declines UI.
OTHER_ANSWERS = samples.ANSWERS | {"AV": samples.reply("L"), "UI": samples.DECLINED}
ANSWERS_BY_MODEL = {samples.MODEL: samples.ANSWERS, samples.OTHER_MODEL: OTHER_ANSWERS}


class TwoModels:
    """A fake server holding two models, each answering from its own table."""

    def __init__(self) -> None:
        """Give each model its own fake server."""
        pairs = ANSWERS_BY_MODEL.items()
        self.servers = {model: samples.FakeServer(answers) for model, answers in pairs}

    def __call__(self, url, payload):
        """Answer a request from the server of the model it names."""
        return self.servers[payload["model"]](url, payload)


def passes(variant: Variant = BASELINE) -> Replies:
    """Take one pass per model over the sample item, as `collect` takes them."""
    calls = {}
    for model in ANSWERS_BY_MODEL:
        calls.update(pass_of(model, variant))
    headers = tuple(samples.header(model, variant) for model in ANSWERS_BY_MODEL)
    return Replies(headers=headers, calls=calls)


def pass_of(model: str, variant: Variant) -> dict:
    """Take one model's pass over the sample item, keyed as a replies file keys it."""
    records = ask_item(samples.item(), model, TwoModels(), variant)
    return {(samples.KEY, model, one.metric): one for one in records}


def asked_live(models: tuple[str, ...], variant: Variant = BASELINE):
    """Put the sample finding to a roster the product's own way, every member asked live."""
    client = RecordingClient(post=TwoModels(), clock=lambda: 0.0, variant=variant)
    return assess_one(samples.finding(), build_roster(models), {OLLAMA_PROVIDER: client})


def test_a_pair_rebuilt_from_two_passes_is_the_record_the_product_writes_asking_both():
    models = (samples.MODEL, samples.OTHER_MODEL)
    assert replay_roster((samples.item(),), models, passes()) == (asked_live(models),)


def test_a_member_alone_rebuilt_from_its_pass_is_the_product_s_single_assessor_record():
    (alone,) = replay_roster((samples.item(),), (samples.OTHER_MODEL,), passes())
    assert alone == asked_live((samples.OTHER_MODEL,))
    assert alone.single_assessor


def test_every_roster_is_each_model_alone_then_each_pair_then_all():
    assert rosters(("a", "b", "c")) == (
        ("a",), ("b",), ("c",), ("a", "b"), ("a", "c"), ("b", "c"), ("a", "b", "c"),
    )


def test_the_pass_models_are_named_in_the_order_the_passes_were_given():
    assert pass_models(passes()) == (samples.MODEL, samples.OTHER_MODEL)


def test_a_pair_asked_in_a_variant_s_words_is_rebuilt_as_it_was_asked():
    models = (samples.MODEL, samples.OTHER_MODEL)
    rebuilt = replay_roster((samples.item(),), models, passes(LIBRARY))
    assert rebuilt == (asked_live(models, LIBRARY),)


def test_passes_asked_under_two_variants_cannot_form_one_roster():
    library, reversed_pass = passes(LIBRARY), passes(REVERSED)
    mixed = Replies(headers=(library.headers[0], reversed_pass.headers[1]), calls=library.calls)
    with pytest.raises(ValueError, match="cannot form one roster"):
        replay_roster((samples.item(),), (samples.MODEL, samples.OTHER_MODEL), mixed)


def test_a_pass_whose_version_no_variant_asks_under_is_refused():
    unknown = Replies(headers=({"kind": "header", "model": samples.MODEL},), calls={})
    with pytest.raises(ValueError, match="no variant asks under"):
        replay_roster((samples.item(),), (samples.MODEL,), unknown)


def test_a_variant_s_record_names_the_product_s_prompt_version_on_its_members():
    # A known gap, asserted so that closing it turns this red. The product's
    # runner names each member by the prompt it built, which is the product's;
    # the variant is carried by the pass's header and each request's fingerprint.
    (outcome,) = replay_roster((samples.item(),), (samples.MODEL,), passes(LIBRARY))
    everyone = chain.from_iterable(ruling.said for ruling in outcome.rulings)
    named = {said.member.prompt_version for said in everyone}
    assert named == {PROMPT_VERSION}

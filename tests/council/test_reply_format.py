"""Guards on the reply contract the prompt states and the parser reads."""

from council.answer import Confidence
from council.reply_format import (
    CONFIDENCE_BY_WORD,
    CONFIDENCE_WORDS,
    NO_EVIDENCE_VALUE,
    REQUIRED_FIELDS,
    VALUE_FIELD,
)
from cvss.metrics import BASE_METRICS


def test_declining_cannot_be_mistaken_for_a_metric_value():
    # Every legal Base value is one uppercase letter, so a word can never
    # collide with one. If that ever stopped being true, a member declining
    # would be read as a member answering.
    legal = set().union(*(metric.values for metric in BASE_METRICS))
    assert NO_EVIDENCE_VALUE not in legal


def test_every_confidence_the_contract_offers_is_one_the_council_has():
    assert set(CONFIDENCE_BY_WORD.values()) == set(Confidence)


def test_the_words_offered_are_the_words_read():
    assert set(CONFIDENCE_WORDS) == set(CONFIDENCE_BY_WORD)


def test_a_reply_is_required_to_carry_a_value():
    assert VALUE_FIELD in REQUIRED_FIELDS

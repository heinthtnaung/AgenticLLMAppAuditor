"""Guards on reading a member's reply: the ugly ones refused, the real ones read."""

import pytest

import recorded_replies as recorded
from council.answer import Confidence, MemberAnswer, MemberFoundNoEvidence, MemberGuessed
from council.evidence import is_quotation_from
from council.reply import MalformedReply, read_reply
from council_samples import ADVISORY, identity

MEMBER = identity()

REFUSED = (
    (recorded.TRUNCATED, "AV", "No complete JSON object"),
    (recorded.NO_JSON_AT_ALL, "AV", "No complete JSON object"),
    (recorded.MISSING_CONFIDENCE, "AV", "has no confidence"),
    (recorded.MISSING_VALUE, "AV", "has no value"),
    (recorded.ANSWERS_ANOTHER_METRIC, "AV", "answers 'AC', but AV was asked"),
    (recorded.VALUE_OF_ANOTHER_METRIC, "AV", "not a value of Attack Vector"),
    (recorded.INVENTED_VALUE, "AV", "not a value of Attack Vector"),
    (recorded.CONFIDENCE_NOT_OFFERED, "AV", "not a confidence"),
    (recorded.VALUE_IS_NOT_TEXT, "AV", "answered with int, not a value"),
    (recorded.EVIDENCE_IS_NOT_TEXT, "AV", "quoted as list, not text"),
    ("", "AV", "answered with nothing at all"),
)


def test_a_recorded_reply_becomes_the_answer_the_model_gave():
    answer = read_reply(recorded.ATTACK_VECTOR, "AV", MEMBER)
    assert isinstance(answer, MemberAnswer)
    assert (answer.metric, answer.value) == ("AV", "N")
    assert answer.confidence is Confidence.HIGH
    assert answer.member is MEMBER


def test_a_recorded_quotation_verifies_against_the_advisory_it_was_read_from():
    # The two halves meeting: the model reflows the advisory's line breaks when
    # it quotes, and the quotation check folds whitespace, so this holds.
    answer = read_reply(recorded.ATTACK_VECTOR, "AV", MEMBER)
    assert is_quotation_from(answer.evidence, ADVISORY)


def test_a_member_that_declined_is_an_absence_and_not_an_answer():
    found = read_reply(recorded.DECLINED, "S", MEMBER)
    assert found == MemberFoundNoEvidence(metric="S", member=MEMBER)


def test_a_recorded_value_with_no_quotation_is_read_as_a_guess():
    # Measured behaviour, not a hypothetical: asked about a metric the advisory
    # is silent on, this model answers the value with an empty quotation. It
    # carries no weight, and it is not the same fact as declining -- which way a
    # member leans with nothing to go on is a fact about that member.
    guess = read_reply(recorded.SILENT_METRIC, "A", MEMBER)
    assert guess == MemberGuessed(metric="A", value="N", member=MEMBER)


def test_prose_wrapped_around_the_json_is_read_through():
    answer = read_reply(recorded.PROSE_AROUND_JSON, "AV", MEMBER)
    assert answer.value == "N"


def test_a_code_fence_around_the_json_is_read_through():
    answer = read_reply(recorded.CODE_FENCED, "AV", MEMBER)
    assert answer.confidence is Confidence.MEDIUM


def test_a_value_written_as_its_whole_pair_is_the_value():
    # 'AV:N' answers AV with N. Refusing it would measure formatting.
    answer = read_reply(recorded.WHOLE_PAIR, "AV", MEMBER)
    assert answer.value == "N"


def test_a_confidence_in_capitals_is_the_same_word():
    assert read_reply(recorded.WHOLE_PAIR, "AV", MEMBER).confidence is Confidence.HIGH


def test_a_fabricated_quotation_parses_and_is_caught_by_the_quotation_check():
    # Parsing is not verification, and this is the division of labour: the
    # parser reads what was said, `council.evidence` decides whether it is true.
    answer = read_reply(recorded.FABRICATED_QUOTATION, "AV", MEMBER)
    assert answer.value == "L"
    assert not is_quotation_from(answer.evidence, ADVISORY)


@pytest.mark.parametrize("reply, metric, complaint", REFUSED)
def test_a_reply_that_cannot_be_read_exactly_is_refused(reply, metric, complaint):
    with pytest.raises(MalformedReply, match=complaint):
        read_reply(reply, metric, MEMBER)


def test_a_refusal_quotes_the_reply_so_a_record_says_what_was_said():
    with pytest.raises(MalformedReply, match="the reply began"):
        read_reply(recorded.TRUNCATED, "AV", MEMBER)


def test_a_malformed_reply_is_a_value_error_a_caller_already_catches():
    assert issubclass(MalformedReply, ValueError)


def test_a_quotation_of_nothing_but_whitespace_is_a_guess():
    # Whitespace is not a quotation, and it supports a value no better than an
    # empty string does.
    blank = '{"value": "N", "evidence": "   ", "confidence": "high"}'
    assert read_reply(blank, "AV", MEMBER) == MemberGuessed(metric="AV", value="N", member=MEMBER)


def test_the_second_object_in_a_reply_is_not_read_instead_of_the_first():
    two = (
        '{"value": "N", "evidence": "unauthenticated remote attacker", "confidence": "high"} '
        '{"value": "P", "evidence": "nonsense", "confidence": "low"}'
    )
    assert read_reply(two, "AV", MEMBER).value == "N"


def test_a_declining_member_that_quotes_something_anyway_is_still_declining():
    # It named no value, so there is nothing for the quotation to support.
    said = '{"value": "NO_EVIDENCE", "evidence": "unauthenticated remote attacker"}'
    assert read_reply(said, "AV", MEMBER) == MemberFoundNoEvidence(metric="AV", member=MEMBER)


@pytest.mark.parametrize("value", ["REMOTE", "Z", "AV"], ids=["a word", "no value", "a metric"])
def test_an_unquotable_value_the_metric_forbids_is_malformed_and_not_a_guess(value):
    # A guess has to be a guess at something real, or the count of guesses is
    # polluted by broken replies -- and that count is the only reason the type
    # exists. The value is validated before the empty quotation is noticed.
    said = f'{{"value": "{value}", "evidence": "", "confidence": "low"}}'
    with pytest.raises(MalformedReply, match="not a value of Attack Vector"):
        read_reply(said, "AV", MEMBER)


def test_a_reply_that_left_the_quotation_field_out_is_malformed_and_not_a_guess():
    # Leaving the field out is not following the format; leaving it empty is
    # following it and having nothing to put there.
    assert isinstance(read_reply('{"value": "N", "evidence": ""}', "AV", MEMBER), MemberGuessed)
    with pytest.raises(MalformedReply, match="has no evidence"):
        read_reply('{"value": "N", "confidence": "low"}', "AV", MEMBER)


def test_a_guess_needs_no_confidence_because_it_supports_nothing():
    said = '{"value": "N", "evidence": ""}'
    assert read_reply(said, "AV", MEMBER) == MemberGuessed(metric="AV", value="N", member=MEMBER)

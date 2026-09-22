"""Reading what a member said into an answer, or refusing it loudly.

Models put prose around their JSON, stop mid-object, answer a metric nobody
asked about and invent fields. None of that may become an answer: a reply this
module cannot read exactly raises `MalformedReply`, naming what was wrong and
quoting the reply, so a run records a member that failed rather than a value
nobody said.

**What is tolerated is only what cannot change the meaning.** JSON surrounded by
prose, because the object is still the object. Case, because `high` and `High`
are the same word. A value written as its whole pair, `AV:N`, because the member
was asked about AV and said N. Nothing else -- and in particular a value that is
not legal for the metric is refused rather than repaired.

**Three things a member can do, so three types.** It can say `NO_EVIDENCE`,
which is an absence. It can give a value and quote nothing for it, which is a
guess -- measured behaviour on this model, not a hypothetical. Or it can give a
value with a quotation, which is an answer. A guess whose value the metric does
not allow is refused rather than recorded: a guess has to be a guess at
something real, or the count of guesses is polluted by broken replies, and that
count is the only reason the type exists.
"""

import json
from typing import Any, Mapping

from council.answer import (
    Confidence,
    MemberAnswer,
    MemberFoundNoEvidence,
    MemberGuessed,
    MemberIdentity,
    MemberReply,
)
from council.reply_format import (
    CONFIDENCE_BY_WORD,
    CONFIDENCE_FIELD,
    CONFIDENCE_WORDS,
    EVIDENCE_FIELD,
    METRIC_FIELD,
    NO_EVIDENCE_VALUE,
    REQUIRED_FIELDS,
    VALUE_FIELD,
)

OBJECT_START = "{"
PAIR_SEPARATOR = ":"

# Enough of a reply to see what went wrong, without a page of prose in a message.
REPLY_EXCERPT_CHARACTERS = 300


class MalformedReply(ValueError):
    """A member's reply was not the JSON object the prompt asked for."""


def read_reply(text: str, metric: str, member: MemberIdentity) -> MemberReply:
    """Read one member's reply into an answer, a guess at a value, or an absence."""
    fields = extract_object(text)
    refuse_other_metric(fields, metric, text)
    refuse_missing_fields(fields, text, (VALUE_FIELD,))
    value = read_value(fields, metric)
    if value == NO_EVIDENCE_VALUE:
        # A quotation alongside it changes nothing. The member named no value,
        # so there is nothing for a quotation to support and nothing to record
        # beyond the absence itself.
        return MemberFoundNoEvidence(metric=metric, member=member)
    if quoted_nothing(fields):
        return build_guess(metric, value, member, text)
    refuse_missing_fields(fields, text, REQUIRED_FIELDS)
    return build_answer(fields, metric, value, member, text)


def quoted_nothing(fields: Mapping[str, Any]) -> bool:
    """Say whether the reply offered a quotation field and left it empty."""
    # Measured on qwen2.5:7b-instruct, on one advisory, for the two metrics it
    # is silent on: the value came back with an empty quotation -- `A:N`, `UI:N`
    # -- and no wording in the prompt changed that. Leaving the field out
    # altogether is a different fault and stays malformed.
    quotation = fields.get(EVIDENCE_FIELD)
    return isinstance(quotation, str) and not quotation.strip()


def build_guess(metric: str, value: str, member: MemberIdentity, text: str) -> MemberGuessed:
    """Record a value nothing was quoted for, refusing one the metric does not allow."""
    try:
        return MemberGuessed(metric=metric, value=value, member=member)
    except (TypeError, ValueError) as fault:
        raise MalformedReply(f"{fault} -- {excerpt(text)}") from fault


def build_answer(
    fields: Mapping[str, Any],
    metric: str,
    value: str,
    member: MemberIdentity,
    text: str,
) -> MemberAnswer:
    """Build the answer, turning the contract's own refusals into malformed replies."""
    try:
        return MemberAnswer(
            metric=metric,
            value=value,
            evidence=read_evidence(fields, metric, text),
            confidence=read_confidence(fields, text),
            member=member,
        )
    except (TypeError, ValueError) as fault:
        raise MalformedReply(f"{fault} -- {excerpt(text)}") from fault


def extract_object(text: str) -> Mapping[str, Any]:
    """Find the one JSON object in a reply, ignoring any prose wrapped around it."""
    if not isinstance(text, str) or not text.strip():
        raise MalformedReply("A member answered with nothing at all")
    decoder = json.JSONDecoder()
    for start in range(len(text)):
        if text[start] != OBJECT_START:
            continue
        found = decode_at(decoder, text, start)
        if found is not None:
            return found
    raise MalformedReply(f"No complete JSON object in the reply -- {excerpt(text)}")


def decode_at(decoder: json.JSONDecoder, text: str, start: int) -> Mapping[str, Any] | None:
    """Decode a JSON object starting at one offset, or say it is not one."""
    try:
        found, _ = decoder.raw_decode(text, start)
    except ValueError:
        return None
    return found if isinstance(found, Mapping) else None


def refuse_missing_fields(fields: Mapping[str, Any], text: str, names: tuple[str, ...]) -> None:
    """Refuse a reply that left out a field the prompt asked for."""
    missing = [name for name in names if name not in fields]
    if not missing:
        return
    raise MalformedReply(f"The reply has no {', '.join(missing)} -- {excerpt(text)}")


def refuse_other_metric(fields: Mapping[str, Any], metric: str, text: str) -> None:
    """Refuse a reply that names a metric other than the one it was asked about."""
    answered = fields.get(METRIC_FIELD)
    if answered is None or str(answered).strip().upper() == metric:
        return
    raise MalformedReply(
        f"The reply answers {str(answered)!r}, but {metric} was asked -- {excerpt(text)}"
    )


def read_value(fields: Mapping[str, Any], metric: str) -> str:
    """Read the value, allowing the letter alone or the whole 'AV:N' pair."""
    value = fields[VALUE_FIELD]
    if not isinstance(value, str):
        raise MalformedReply(f"{metric} was answered with {type(value).__name__}, not a value")
    spelled = value.strip().upper()
    if spelled == NO_EVIDENCE_VALUE:
        return NO_EVIDENCE_VALUE
    name, separator, letter = spelled.partition(PAIR_SEPARATOR)
    return letter.strip() if separator and name == metric else spelled


def read_evidence(fields: Mapping[str, Any], metric: str, text: str) -> str:
    """Read the quotation, refusing a reply that put something other than text there."""
    evidence = fields[EVIDENCE_FIELD]
    if isinstance(evidence, str):
        return evidence
    raise MalformedReply(
        f"{metric} was quoted as {type(evidence).__name__}, not text -- {excerpt(text)}"
    )


def read_confidence(fields: Mapping[str, Any], text: str) -> Confidence:
    """Read the confidence word, refusing a level the prompt never offered."""
    said = str(fields[CONFIDENCE_FIELD]).strip().lower()
    level = CONFIDENCE_BY_WORD.get(said)
    if level is None:
        allowed = ", ".join(CONFIDENCE_WORDS)
        raise MalformedReply(
            f"{said!r} is not a confidence; the prompt offers {allowed} -- {excerpt(text)}"
        )
    return level


def excerpt(text: str) -> str:
    """Quote the start of a reply, so a refusal says what was actually said."""
    shown = " ".join(str(text).split())[:REPLY_EXCERPT_CHARACTERS]
    return f"the reply began {shown!r}"

"""The advisory, members and answers the council tests read, built by hand.

No test calls a model. Every reply is constructed in the shape the model-facing
half is required to parse into, so what is tested is the reconciliation and not
anybody's prompt.

Named `council_samples` and not `samples`: pytest puts each test directory on
the path and imports by basename, so a second `samples.py` would be shadowed by
`tests/deps/samples.py`.
"""

import json

from council.answer import (
    Confidence,
    MemberAnswer,
    MemberFoundNoEvidence,
    MemberGuessed,
    MemberIdentity,
)
from council.roster import Member

# Wrapped the way a feed wraps it, so a quotation spanning a line break is a
# normal case rather than an awkward one.
ADVISORY = (
    "A flaw was found in the web console. An unauthenticated remote attacker can\n"
    "send a crafted request to the management port and read arbitrary files from\n"
    "the host's filesystem. The component does not validate the supplied path."
)

NETWORK_QUOTATION = "unauthenticated remote attacker"

# Deliberately not `council.prompt.PROMPT_VERSION`, and deliberately not shaped
# like it. These are the deterministic half's fixtures and they run without the
# model-facing modules loaded, so the real constant is not importable here
# without dragging the prompt builder into a test of the roster. It drifted once
# while pretending to be a copy of the real one; looking nothing like a real one
# is what stops that. What a run actually records is the prompt's own version,
# and `tests/council/test_runner.py` pins that end to end.
SAMPLE_PROMPT_VERSION = "sample-prompt-version"
ACROSS_A_LINE_BREAK = "remote attacker can send a crafted request"
NOT_IN_THE_ADVISORY = "the attacker must already hold local credentials"


def identity(name: str = "small-local", **overrides) -> MemberIdentity:
    """Build one member identity in the shape an answer carries it."""
    fields = {
        "name": name,
        "provider": "ollama",
        "model": "qwen2.5:7b",
        "family": "qwen",
        "ran_local": True,
        "prompt_version": SAMPLE_PROMPT_VERSION,
    }
    fields.update(overrides)
    return MemberIdentity(**fields)


def answer(
    metric: str = "AV",
    value: str = "N",
    evidence: str = NETWORK_QUOTATION,
    confidence: Confidence = Confidence.HIGH,
    name: str = "small-local",
) -> MemberAnswer:
    """Build one member's answer about one metric."""
    return MemberAnswer(
        metric=metric,
        value=value,
        evidence=evidence,
        confidence=confidence,
        member=identity(name),
    )


def found_nothing(metric: str = "AV", name: str = "small-local") -> MemberFoundNoEvidence:
    """Build one member reporting that the advisory says nothing about a metric."""
    return MemberFoundNoEvidence(metric=metric, member=identity(name))


def guessed(metric: str = "AV", value: str = "N", name: str = "small-local") -> MemberGuessed:
    """Build one member offering a value it could not quote anything for."""
    return MemberGuessed(metric=metric, value=value, member=identity(name))


def member(name: str = "small-local", **overrides) -> Member:
    """Build one roster member as an operator would configure it."""
    fields = {
        "name": name,
        "provider": "ollama",
        "model": "qwen2.5:7b",
        "family": "qwen",
        "runs_local": True,
    }
    fields.update(overrides)
    return Member(**fields)


def hosted(name: str = "hosted-other-family", **overrides) -> Member:
    """Build one hosted member, which does not run unless egress is opted in."""
    fields = {
        "provider": "openrouter",
        "model": "anthropic/claude-sonnet-5",
        "family": "claude",
        "runs_local": False,
    }
    fields.update(overrides)
    return member(name, **fields)


# An advisory carrying a CVE id and a published vector, so the prompt builder
# has something to redact and the quotation check something to span.
RAW_ADVISORY = (
    "CVE-2021-44228: A flaw in Apache Log4j2. An unauthenticated remote attacker "
    "who can control log messages can execute arbitrary code. "
    "Scored CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H by the vendor."
)
QUOTABLE = "unauthenticated remote attacker"
DECLINED = json.dumps({"value": "NO_EVIDENCE", "evidence": ""})

# A value each metric allows, and a second one. "N" is legal for AV and not for
# AC or S, so a client saying one thing everywhere would test the refusal path.
LEGAL_VALUE = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}
OTHER_VALUE = {"AV": "L", "AC": "H", "PR": "L", "UI": "R", "S": "C", "C": "L", "I": "L", "A": "L"}


def replying(evidence: str = QUOTABLE):
    """A client answering each metric with a value that metric allows."""
    return lambda asked, prompt: json.dumps(
        {"value": LEGAL_VALUE[prompt.metric], "evidence": evidence, "confidence": "high"}
    )


def guessing(asked, prompt):
    """A client that leans the other way with nothing to quote for it."""
    return json.dumps({"value": OTHER_VALUE[prompt.metric], "evidence": "", "confidence": "low"})


def clients_of(ask):
    """Put one client behind the local provider."""
    return {"ollama": ask}

"""The advisory, members and answers the council tests read, built by hand.

No test calls a model. Every reply is constructed in the shape the model-facing
half is required to parse into, so what is tested is the reconciliation and not
anybody's prompt.

Named `council_samples` and not `samples`: pytest puts each test directory on
the path and imports by basename, so a second `samples.py` would be shadowed by
`tests/deps/samples.py`.
"""

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
        # The real one, from `council.prompt.PROMPT_VERSION`. Written out rather
        # than imported: these tests are the deterministic half and run without
        # the model-facing modules.
        "prompt_version": "member-base-metric-1",
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

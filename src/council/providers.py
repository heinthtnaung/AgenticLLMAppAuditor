"""Which providers this machine can reach, and the client that speaks to each.

Separated from the runner because the two change for different reasons. This
file grows when a provider is added -- an OpenRouter client, a member's own
temperature and seed -- and the dispatch beside it does not. The runner grows
when the policy changes, from asking every member to escalating a contested
metric, and this file does not.

**A member with no client is reported, never stubbed.** There is no hosted
client here, and a stub would answer: its answer would be fiction, recorded as
an assessment. So a member nothing can reach is named as skipped with the
reason, beside the ones `egress` stopped, and the two reasons stay
distinguishable -- "not configured" and "refused by policy" are different facts
about a run.
"""

from typing import Callable, Mapping

from council.ollama import LocalModel, ask
from council.prompt import MemberPrompt
from council.roster import (
    OLLAMA_PROVIDER,
    Member,
    Roster,
    SkippedMember,
    members_skipped,
    members_to_ask,
)

# Ask one member one prompt and give back what it said, verbatim.
AskMember = Callable[[Member, MemberPrompt], str]

NO_CLIENT_FOR_PROVIDER = "no client for provider {provider!r} exists on this machine"


def ask_local_model(member: Member, prompt: MemberPrompt) -> str:
    """Put a prompt to a member running on the local Ollama server."""
    return ask(prompt, LocalModel(model=member.model)).text


# Ollama and nothing else, which is why a hosted member is reported rather than
# asked. Adding a provider is adding an entry here and its adapter above.
PROVIDER_CLIENTS: Mapping[str, AskMember] = {OLLAMA_PROVIDER: ask_local_model}


def reachable_members(
    members: tuple[Member, ...], clients: Mapping[str, AskMember]
) -> tuple[Member, ...]:
    """Give the members a client exists for, refusing a run that can reach nobody."""
    reachable = tuple(member for member in members if member.provider in clients)
    if reachable:
        return reachable
    raise ValueError(
        "No member of this roster has a provider client here, so nobody can be asked"
    )


def unreachable_members(
    roster: Roster, clients: Mapping[str, AskMember]
) -> tuple[SkippedMember, ...]:
    """Name everyone who will not be asked, whether egress or a missing client stopped them."""
    no_client = tuple(
        SkippedMember(member=member, reason=no_client_reason(member))
        for member in members_to_ask(roster)
        if member.provider not in clients
    )
    return members_skipped(roster) + no_client


def no_client_reason(member: Member) -> str:
    """Say why a member with no provider client here was not asked."""
    return NO_CLIENT_FOR_PROVIDER.format(provider=member.provider)

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

**An Ollama member is recorded where its server is.** Every one is asked of the
one server the settings name, so `ollama_member` reads its place off that
server's host: this machine, or another the operator opted in to with
`AUDITOR_REMOTE_SERVER=yes`, which is the member's egress. `ask_local_model`
refuses a member whose record says otherwise, before anything is sent.
"""

from typing import Callable, Mapping

from council.model_name import family_of
from council.ollama import LocalModel, ask
from council.question import Question
from council.roster import (
    OLLAMA_PROVIDER,
    Member,
    Roster,
    SkippedMember,
    members_skipped,
    members_to_ask,
)
from council.settings import current_settings, on_this_machine

# Ask one member one question and give back what it said, verbatim.
AskMember = Callable[[Member, Question], str]

NO_CLIENT_FOR_PROVIDER = "no client for provider {provider!r} exists on this machine"


def ollama_member(model: str) -> Member:
    """Describe one model on the settings' Ollama server as a council member, wherever it is."""
    # The family is guessed from the model's own name, which is what a roster file
    # would carry properly. It is only read to judge how much a roster's agreement
    # is worth, never by the chairman, so a wrong guess costs a reader and not a number.
    here = on_this_machine(current_settings().server)
    return Member(
        name=model,
        provider=OLLAMA_PROVIDER,
        model=model,
        family=family_of(model),
        runs_local=here,
        # Elsewhere only with `AUDITOR_REMOTE_SERVER=yes`: that opt-in is this member's egress.
        egress=not here,
    )


def ask_local_model(member: Member, prompt: Question) -> str:
    """Put a prompt to a member on the settings' Ollama server, here or elsewhere."""
    pinning = LocalModel(model=member.model)
    refuse_mislabelled(member, pinning.host)
    return ask(prompt, pinning).text


def refuse_mislabelled(member: Member, host: str) -> None:
    """Refuse a member whose record would say it ran local and its server is not, or the reverse."""
    if member.runs_local == on_this_machine(host):
        return
    said = "this machine" if member.runs_local else "another machine"
    raise ValueError(
        f"{member.name} would be recorded as run on {said}, but its server is {host}; it is "
        "not asked, so the record cannot misstate where the advisory text went"
    )


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

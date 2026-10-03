"""Any roster, rebuilt offline from the passes, through the product's own runner and chairman.

A member is shown nothing of any other member's answer -- the panel rule -- and
the chairman is code. So what a roster decides on an item is fixed by what each
of its members said, and each member's words are in its own pass. Replaying
them through `cli.council_run.assess_one` gives the record the audit itself
would have written, without asking any model again -- with its order check
off, since a pass holds one order, and with no escalation model, since no pass
holds one; `order_checked` rebuilds a checked roster from two passes.

That rests on one more thing: a member's reply must not depend on what else
was loaded or asked before it. Measured, it can -- `qwen2.5:7b-instruct` answers
differently cold and warm -- which is why every pass starts each member's turn
from a fresh load, and why the first use of this module is the gate against a
run recorded the product's own way.

A pasted pass, whose replies a person brought back from a chat, is replayed the
same way by `chat_replay`: its members are hosted, and each call answers the
prompt the person pasted rather than a request this machine sent.

**A member is rebuilt where its pass ran, not where this machine's settings point.**
A pass headed with a `remote_host` was asked of a server elsewhere, so its member
replays as run there; a pass with none ran here.
"""

from itertools import chain, combinations
from typing import Any, Mapping

from cli.council_run import assess_one
from council.providers import AskMember, ollama_member_on
from council.roster import Member, Roster
from council_eval.chat_replay import PastedReplayClient, chat_member
from council_eval.dataset import Item
from council_eval.pass_provenance import REMOTE_HOST_FIELD
from council_eval.replies import PROMPT_VERSION_FIELD, WINDOW_FIELD, ReplayClient, Replies
from council_eval.variants import PASS_ESCALATION, PASS_ORDER_CHECK, Variant, variant_asked
from report.council_record import CouncilOutcome

# What answers one item's calls: a local pass's recorded requests, or a pasted pass's replies.
ItemClient = ReplayClient | PastedReplayClient


def replay_roster(
    items: tuple[Item, ...], models: tuple[str, ...], replies: Replies
) -> tuple[CouncilOutcome, ...]:
    """Rebuild what one roster decides on every item, from the calls its members' passes saved."""
    variant = pass_variant(replies)
    roster = pass_roster(models, variant, replies)
    return tuple(
        replay_item(item, roster, item_client(item.key, replies, variant)) for item in items
    )


def replay_item(item: Item, roster: Roster, client: AskMember) -> CouncilOutcome:
    """Rebuild one item's council record, every member answering from its recorded calls."""
    return assess_one(
        item.finding, roster, clients_for(roster, client),
        order_check=PASS_ORDER_CHECK, escalation=PASS_ESCALATION,
    )


def clients_for(roster: Roster, client: AskMember) -> dict[str, AskMember]:
    """Hand one client every provider the roster's members name, as the runner looks them up."""
    return {member.provider: client for member in roster.members}


def pass_roster(models: tuple[str, ...], variant: Variant, replies: Replies) -> Roster:
    """Build the roster the passes' models form: members where they ran, or asked in a chat."""
    if variant.chat:
        return Roster(tuple(chat_member(model) for model in models))
    return Roster(tuple(pass_member(model, pass_places(replies)) for model in models))


def pass_member(model: str, places: Mapping[str, bool]) -> Member:
    """Describe one model as the member its pass asked, on this machine or on another."""
    if model not in places:
        raise ValueError(f"no pass names {model}, so nothing says where it ran")
    return ollama_member_on(model, this_machine=places[model])


def pass_places(replies: Replies) -> dict[str, bool]:
    """Say of each pass's model whether it ran on this machine, as its header records."""
    return {header["model"]: ran_here(header) for header in replies.headers}


def ran_here(header: Mapping[str, Any]) -> bool:
    """Say whether a pass ran on this machine: one headed with a remote host did not."""
    if REMOTE_HOST_FIELD not in header:
        return True
    host = header[REMOTE_HOST_FIELD]
    if not isinstance(host, str) or not host:
        raise ValueError(f"the pass of {header['model']} names its remote host as {host!r}")
    return False


def item_client(key: str, replies: Replies, variant: Variant) -> ItemClient:
    """Give the client that answers one item from the passes, as the passes were asked."""
    if variant.chat:
        return PastedReplayClient(key, replies.calls, variant.reversed_options)
    return ReplayClient(key, replies.calls, variant, pass_window(replies))


def pass_variant(replies: Replies) -> Variant:
    """Give the one variant the passes were asked under, refusing passes asked differently."""
    # A chairman weighing answers to two different questions is not a council.
    versions = {header.get(PROMPT_VERSION_FIELD, "") for header in replies.headers}
    if len(versions) != 1:
        raise ValueError(f"passes asked under {sorted(versions)} cannot form one roster")
    return variant_asked(versions.pop())


def pass_window(replies: Replies) -> int:
    """Give the one window the passes were recorded at, whatever this machine's settings say."""
    # The request carries the window, so a replay at another one is refused call by call.
    windows = {header.get(WINDOW_FIELD) for header in replies.headers}
    if len(windows) != 1 or not isinstance(next(iter(windows)), int):
        named = sorted(map(str, windows))
        raise ValueError(f"passes recorded at windows {named} cannot form one roster")
    return windows.pop()


def rosters(models: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """Give every roster the passes can build: each model alone, then each pair, up to all."""
    sizes = range(1, len(models) + 1)
    return tuple(chain.from_iterable(combinations(models, size) for size in sizes))


def pass_models(replies: Replies) -> tuple[str, ...]:
    """Name the models the passes asked, in the order the passes were given."""
    return tuple(header["model"] for header in replies.headers)

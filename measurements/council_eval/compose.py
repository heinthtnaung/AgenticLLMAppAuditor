"""Any roster, rebuilt offline from the passes, through the product's own runner and chairman.

A member is shown nothing of any other member's answer -- the panel rule -- and
the chairman is code. So what a roster decides on an item is fixed by what each
of its members said, and each member's words are in its own pass. Replaying
them through `cli.council_run.assess_one` gives the record the audit itself
would have written, without asking any model again.

That rests on one more thing: a member's reply must not depend on what else
was loaded or asked before it. Measured, it can -- `qwen2.5:7b-instruct` answers
differently cold and warm -- which is why every pass starts each member's turn
from a fresh load, and why the first use of this module is the gate against a
run recorded the product's own way.
"""

from itertools import chain, combinations

from cli.council_run import OLLAMA_PROVIDER, assess_one, build_roster
from council.roster import Roster
from report.council_record import CouncilOutcome

from council_eval.dataset import Item
from council_eval.replies import PROMPT_VERSION_FIELD, WINDOW_FIELD, ReplayClient, Replies
from council_eval.variants import Variant, variant_asked


def replay_roster(
    items: tuple[Item, ...], models: tuple[str, ...], replies: Replies
) -> tuple[CouncilOutcome, ...]:
    """Rebuild what one roster decides on every item, from the calls its members' passes saved."""
    roster = build_roster(models)
    variant, window = pass_variant(replies), pass_window(replies)
    return tuple(replay_item(item, roster, replies, variant, window) for item in items)


def replay_item(
    item: Item, roster: Roster, replies: Replies, variant: Variant, window: int
) -> CouncilOutcome:
    """Rebuild one item's council record, every member answering from its recorded calls."""
    client = ReplayClient(item.key, replies.calls, variant, window)
    return assess_one(item.finding, roster, {OLLAMA_PROVIDER: client})


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

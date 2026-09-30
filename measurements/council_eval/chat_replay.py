"""A pasted pass replayed: each metric answered from the reply a person saved from a chat.

It stands where `replies.ReplayClient` stands for a local pass, and refuses what
that refuses, differently checked. There is no request to rebuild, since nobody
sent one: what a pasted call records as its request is the SHA-256 of the prompt
the person pasted, so the replay rebuilds that prompt from the advisory the
member is shown and refuses a reply to any other words.

The member is recorded as what it was: hosted, not reached by this machine, its
text taken off the machine by hand.
"""

from dataclasses import dataclass
from typing import Mapping

from council.envelope import RESPONSE_FIELD
from council.prompt import MemberPrompt
from council.roster import Member

from council_eval.chat_prompt import chat_prompt_body, text_digest
from council_eval.recording import CallRecord
from council_eval.replies import CallKey, ReplayMismatch, recorded_call

CHAT_PROVIDER = "chat"


@dataclass(frozen=True)
class PastedReplayClient:
    """A provider client answering one item's prompts from the replies pasted back for it."""

    key: str
    calls: Mapping[CallKey, CallRecord]
    reversed_options: bool

    def __call__(self, member: Member, prompt: MemberPrompt) -> str:
        """Answer as the pasted reply did, or refuse one that answered other words."""
        recorded = recorded_call(self.calls, self.key, member.model, prompt.metric)
        pasted = chat_prompt_body(prompt.advisory_shown, self.reversed_options)
        if recorded.request_sha256 != text_digest(pasted):
            raise ReplayMismatch(f"{self.key} {prompt.metric}: {member.model} was asked otherwise")
        return recorded.envelope[RESPONSE_FIELD]


def chat_member(model: str) -> Member:
    """Describe a model a person asked through a chat interface as a council member."""
    # Hosted, and its egress was taken: the advisory left this machine, by hand.
    # The family is the name as typed, since nothing here can tell one apart.
    return Member(
        name=model, provider=CHAT_PROVIDER, model=model, family=model,
        runs_local=False, egress=True,
    )

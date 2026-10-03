"""The prompts and saved replies the chat steps' tests share. Every reply here is a fixture.

The two files in `fixtures/` are hand-written replies to the sample advisory's
two prompts, shaped as a person would save them. Nothing here, and nothing in
them, is a measurement of any model.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Mapping

import eval_samples as samples
from council_eval.chat_pass_lines import pass_lines
from council_eval.chat_passes import AnsweredPrompt, answered_prompts
from council_eval.chat_prompt import PROMPT_ID_FIELD
from council_eval.chat_prompt_set import ChatPrompt, chat_prompts
from council_eval.chat_reply import read_chat_reply
from council_eval.chat_reply_file import read_saved_reply
from council_eval.dataset import Item, write_dataset
from council_eval.replies import CALL_KIND, Replies, calls_by_key
from council_eval.variants import CHAT, CHAT_REVERSED, Variant
from findings.finding import build_finding

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FORWARD_FIXTURE = FIXTURES / "chat_reply_forward.txt"
REVERSED_FIXTURE = FIXTURES / "chat_reply_reversed.txt"
FIXTURE_MODEL = "fixture-model (hand-written, not a measurement)"
FIXTURE_INTERFACE = "fixture chat"

HEADER = f"model: {FIXTURE_MODEL}\ndate: 2026-10-01\ninterface: {FIXTURE_INTERFACE}\n---\n"

# A reply on every metric, each field as the reply format asks.
READINGS = {
    "AV": {"value": "N", "evidence": samples.REMOTE, "confidence": "high"},
    "AC": {"value": "L", "evidence": samples.REMOTE, "confidence": "medium"},
    "PR": {"value": "N", "evidence": samples.REMOTE, "confidence": "medium"},
    "UI": {"value": "N", "evidence": samples.NO_INTERACTION, "confidence": "high"},
    "S": {"value": "U", "evidence": "the scope does not change", "confidence": "low"},
    "C": {"value": "NO_EVIDENCE", "evidence": "", "confidence": "low"},
    "I": {"value": "N", "evidence": "", "confidence": "low"},
    "A": {"value": "H", "evidence": samples.CRASH, "confidence": "high"},
}


def item_reading(key: str, text: str) -> Item:
    """Build a sample item whose advisory reads as given."""
    finding = samples.finding(key)
    advisory = replace(finding.advisory, details=text)
    rebuilt = build_finding(finding.component, advisory)
    return Item(split="V", published=samples.PUBLISHED, finding=rebuilt)


# Two items whose advisories read differently, so their prompts do.
TWO_ITEMS = (samples.item(), item_reading("CVE-2026-0002", samples.ADVISORY_TEXT + " Upgrade."))


def prompts(items: tuple[Item, ...] = (samples.item(),)) -> tuple[ChatPrompt, ...]:
    """Build the prompts of the sample items, forward then reversed for each."""
    return chat_prompts(items)


def block(prompt_id: str, readings: Mapping[str, object] = READINGS) -> str:
    """Write the fenced JSON block a reply is asked for."""
    fields = {PROMPT_ID_FIELD: prompt_id, **readings}
    return f"```json\n{json.dumps(fields, indent=2)}\n```\n"


def saved_text(
    prompt_id: str, readings: Mapping[str, object] = READINGS, header: str = HEADER
) -> str:
    """Write a whole saved reply: the person's header, a line of prose, the block."""
    return f"{header}Here is my assessment.\n\n{block(prompt_id, readings)}"


def write_reply(folder: Path, name: str, text: str) -> Path:
    """Save one reply into a replies folder, making the folder if need be."""
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def dataset_file(folder: Path, items: tuple[Item, ...] = (samples.item(),)) -> Path:
    """Freeze the sample items to a dataset file."""
    path = folder / "dataset.json"
    write_dataset(items, {"repository": "example"}, path)
    return path


def answer_both(folder: Path, items: tuple[Item, ...] = (samples.item(),)) -> Path:
    """Save a reply to every prompt of the items, each in a file named after its prompt."""
    for one in prompts(items):
        write_reply(folder, one.file, saved_text(one.prompt_id))
    return folder


def fixtures_answered() -> tuple[AnsweredPrompt, ...]:
    """Match the two hand-written fixtures to the sample advisory's prompts."""
    saved = (read_saved_reply(one) for one in (FORWARD_FIXTURE, REVERSED_FIXTURE))
    replies = tuple(read_chat_reply(one) for one in saved)
    return answered_prompts(prompts(), replies)


def no_git(command: tuple[str, ...]) -> str:
    """Stand in for git: one commit, and nothing uncommitted."""
    return "abc123\n" if command[1] == "rev-parse" else ""


def fixture_pass(variant: Variant = CHAT, model: str = FIXTURE_MODEL) -> Replies:
    """Give one order of the fixtures as a pasted pass, read as `score` reads a pass."""
    answered = tuple(as_model(one, model) for one in fixtures_answered())
    lines = pass_lines(answered, variant, "d" * 64, no_git)
    calls = [line for line in lines if line["kind"] == CALL_KIND]
    return Replies(headers=(lines[0],), calls=calls_by_key(calls))


def fixture_passes() -> tuple[Replies, Replies]:
    """Give the fixtures as a forward and a reversed pasted pass."""
    return fixture_pass(CHAT), fixture_pass(CHAT_REVERSED)


def as_model(answered: AnsweredPrompt, model: str) -> AnsweredPrompt:
    """Give a matched reply as though another model had written it."""
    saved = replace(answered.reply.saved, model=model)
    return replace(answered, reply=replace(answered.reply, saved=saved))

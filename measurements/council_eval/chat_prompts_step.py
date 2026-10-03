"""The `chat-prompts` step: write every advisory's prompt, in both orders, for a person to paste.

Nothing is asked here. The files go into a new folder that holds prompts and
nothing else, so anything in it is safe to paste; the manifest, which names each
file's advisory, is refused anywhere inside that folder for that reason. The same
dataset gives the same bytes: no clock, no path and no machine's name is in any file.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from council_eval.chat_outputs import refuse_inside, refuse_unwritable
from council_eval.chat_prompt_set import ChatPrompt, chat_prompts
from council_eval.dataset import read_dataset
from council_eval.pass_provenance import file_digest
from council_eval.variants import chat_variant

MANIFEST_INDENT = 1
TEXT_ENCODING = "utf-8"


def add_chat_prompts(commands: Any) -> None:
    """Add the step that writes the prompts a person pastes into a chat."""
    helped = "write each advisory's prompt, both orders, to paste into a chat"
    step = commands.add_parser("chat-prompts", help=helped)
    step.add_argument("--dataset", type=Path, required=True)
    step.add_argument("--out", type=Path, required=True, help="a new folder for the prompts")
    step.add_argument("--manifest", type=Path, required=True, help="a new file, never pasted")
    step.set_defaults(run=run_chat_prompts)


def run_chat_prompts(options: argparse.Namespace) -> int:
    """Write every prompt into a new folder and the manifest beside it, refusing to overwrite."""
    prompts = chat_prompts(read_dataset(options.dataset))
    manifest = manifest_text(prompts, file_digest(options.dataset))
    refuse_inside(options.out, options.manifest)
    refuse_unwritable((options.out, options.manifest))
    options.out.mkdir()
    for prompt in prompts:
        (options.out / prompt.file).write_bytes(prompt.text.encode(TEXT_ENCODING))
    options.manifest.write_bytes(manifest.encode(TEXT_ENCODING))
    print(written_line(prompts, options.out, options.manifest))
    return 0


def manifest_text(prompts: tuple[ChatPrompt, ...], dataset_sha256: str) -> str:
    """Give the manifest: the dataset, and each file's advisory, order, ID and size."""
    entries = [manifest_entry(one) for one in prompts]
    document = {"dataset_sha256": dataset_sha256, "prompts": entries}
    return json.dumps(document, indent=MANIFEST_INDENT, sort_keys=True) + "\n"


def manifest_entry(prompt: ChatPrompt) -> dict[str, Any]:
    """Describe one prompt file in the manifest."""
    return {
        "file": prompt.file,
        "advisory": prompt.key,
        "order": prompt.order,
        "prompt_id": prompt.prompt_id,
        "prompt_sha256": prompt.sha256,
        "prompt_version": chat_variant(prompt.reversed_options).prompt_version,
        "bytes": len(prompt.text.encode(TEXT_ENCODING)),
    }


def written_line(prompts: tuple[ChatPrompt, ...], out: Path, manifest: Path) -> str:
    """Say how many prompts were written, how large they are, and where the manifest is."""
    size = sum(len(one.text.encode(TEXT_ENCODING)) for one in prompts)
    advisories = len({one.key for one in prompts})
    return (
        f"{len(prompts)} prompts for {advisories} advisories, {size} bytes in all, "
        f"written to {out}; {manifest} names their advisories and is not for pasting"
    )

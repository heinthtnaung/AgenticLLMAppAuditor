"""Ask the explainer alone about each disputed finding of the frozen vulnscout data, per seed.

The product's own path: `council.explanation.explain` over `cli.council_run.advisory_text`
and `cli.explanation_run.published_on`, asked through `council.ollama.ask`. Only the seed
differs from what `council.providers.ask_local_model` sends. No council and no scan.

The first line names the weights, the server -- its address, and its host as `remote_host`
where it is another machine, as `council_eval.pass_provenance` heads a pass -- the pinning,
the prompt version, the dataset and the code. Each line after it is one call: the request,
Ollama's envelope without its token ids, and what `explain` kept and dropped, with why.

    python measurements/explainer_vulnscout/probe.py gemma4:latest glm-4.7-flash:latest \\
        --out /tmp/explain.jsonl
"""

import argparse
import json
import sys
import time
from itertools import product
from pathlib import Path
from typing import Any, Callable, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cli.council_run import advisory_text  # noqa: E402
from cli.explanation_run import published_on  # noqa: E402
from cli.model_identity import Read  # noqa: E402
from council.explanation import Explained, Explanation, explain  # noqa: E402
from council.explanation_prompt import EXPLANATION_PROMPT_VERSION  # noqa: E402
from council.ollama import PINNED_TEMPERATURE, PINNED_THINKING, LocalModel, ask  # noqa: E402
from council.providers import ollama_member, refuse_mislabelled  # noqa: E402
from council.question import Question  # noqa: E402
from council.roster import Member  # noqa: E402
from council.settings import current_settings  # noqa: E402
from council.transport import get_json, post_json  # noqa: E402
from council_eval.dataset import read_dataset  # noqa: E402
from council_eval.pass_provenance import (  # noqa: E402
    GIT_CHANGES,
    GIT_COMMIT,
    Run,
    file_digest,
    git_output,
    held_listing,
    held_version,
    model_digest,
    now,
    server_named,
)
from findings.finding import Finding  # noqa: E402

RUNS = Path(__file__).resolve().parents[1] / "council_eval_runs"
DATASET = RUNS / "pilot-vulnscout" / "vulnscout.dataset.json"
SEEDS = (11, 12)
# The token ids of the prompt and the reply: long, and nothing reads them.
DROPPED_FIELDS = ("context",)

Post = Callable[[str, dict[str, Any]], Any]


def disputed(path: Path) -> tuple[Finding, ...]:
    """Give the dataset's findings whose readable sources disagree, in the dataset's order."""
    return tuple(one.finding for one in read_dataset(path) if one.finding.disputed_metrics())


def header(
    models: tuple[str, ...], seeds: tuple[int, ...], findings: tuple[Finding, ...],
    get: Read = get_json, run_git: Run = git_output,
) -> dict[str, Any]:
    """Describe the probe before it starts: weights, server, pinning, prompt, data and code."""
    settings = current_settings()
    listing = held_listing(settings.server, get)
    return {
        "ollama_version": held_version(settings.server, get),
        **server_named(settings.server),
        "digests": {model: model_digest(model, listing) for model in models},
        "prompt_version": EXPLANATION_PROMPT_VERSION,
        "temperature": PINNED_TEMPERATURE,
        "think": PINNED_THINKING,
        "context_tokens": settings.context_tokens,
        "seeds": list(seeds),
        "timeout_seconds": settings.timeout_seconds,
        "findings": [one.advisory.advisory_id for one in findings],
        "dataset_sha256": file_digest(DATASET),
        "commit": run_git(GIT_COMMIT).strip(),
        "changes": run_git(GIT_CHANGES).splitlines(),
        "started": now(),
    }


def keeping(post: Post, kept: list[dict[str, Any]]) -> Post:
    """Post as given, and keep each request, its envelope without token ids, and its time."""
    def recorded(url: str, payload: dict[str, Any]) -> Any:
        """Post one request, and keep it with its envelope and how long it took."""
        started, began = now(), time.monotonic()
        envelope = post(url, payload)
        body = {name: value for name, value in envelope.items() if name not in DROPPED_FIELDS}
        kept.append({"started": started, "request": payload, "seconds": time.monotonic() - began,
                     "envelope": body})
        return envelope
    return recorded


def outcome_of(said: Explanation) -> dict[str, Any]:
    """Put what `explain` gave into plain data: the items kept, and those dropped with why."""
    dropped = [vars(one.item) | {"reason": one.reason, "quotation_found": one.quotation_found}
               for one in said.dropped]
    if not isinstance(said, Explained):
        return {"explained": False, "because": said.because, "kept": [], "dropped": dropped}
    return {"explained": True, "kept": [vars(one) for one in said.items], "dropped": dropped}


def one_call(finding: Finding, model: str, seed: int, post: Post) -> dict[str, Any]:
    """Ask one model under one seed about one finding, and give the line that records it."""
    kept: list[dict[str, Any]] = []
    transport = keeping(post, kept)

    def ask_member(member: Member, prompt: Question) -> str:
        """Ask as `council.providers.ask_local_model` does, under this seed."""
        pinning = LocalModel(model=member.model, seed=seed)
        refuse_mislabelled(member, pinning.host)
        return ask(prompt, pinning, transport).text

    clients = {"ollama": ask_member}
    said = explain(advisory_text(finding), published_on(finding), ollama_member(model), clients)
    metrics = finding.disputed_metrics()
    return {"advisory_id": finding.advisory.advisory_id, "metrics": list(metrics),
            "one_metric": len(metrics) == 1, "model": model, "seed": seed,
            "prompt_version": said.prompt_version, "outcome": outcome_of(said),
            **(kept[0] if kept else {})}


def run(
    models: tuple[str, ...], seeds: tuple[int, ...], out: TextIO,
    post: Post = post_json, get: Read = get_json, run_git: Run = git_output,
) -> None:
    """Ask every model under every seed about every disputed finding, writing each line at once."""
    findings = disputed(DATASET)
    described = header(models, seeds, findings, get, run_git)
    out.write(json.dumps({"header": described}) + "\n")
    for model, seed, finding in product(models, seeds, findings):
        line = one_call(finding, model, seed, post) | {"digest": described["digests"][model]}
        out.write(json.dumps(line) + "\n")
        out.flush()


def main(argv: list[str]) -> int:
    """Run the probe into a new file, never over one already recorded."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("models", nargs="+")
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args(argv)
    with options.out.open("x", encoding="utf-8") as out:
        run(tuple(options.models), tuple(options.seeds), out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

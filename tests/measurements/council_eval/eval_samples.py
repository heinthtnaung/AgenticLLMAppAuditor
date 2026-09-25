"""The finding, item and fake model server the council evaluation's tests share.

Named `eval_samples` and not `samples`: pytest imports test helpers by basename,
and `tests/deps/samples.py` already holds that name.
"""

import json
import sys
from pathlib import Path
from typing import Any, Mapping

# The evaluation is a package beside the other measurement scripts, not in `src/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "measurements"))

from council.reply_format import NO_EVIDENCE_VALUE  # noqa: E402
from cvss.metrics import METRIC_ORDER  # noqa: E402
from deps.syft_report import Component  # noqa: E402
from deps.trivy_report import Advisory  # noqa: E402
from findings.finding import Finding, build_finding  # noqa: E402

from council_eval.collect import ask_item  # noqa: E402
from council_eval.recording import CallRecord  # noqa: E402
from council_eval.dataset import Item  # noqa: E402
from council_eval.variants import BASELINE, Variant  # noqa: E402

KEY = "CVE-2026-0001"
MODEL = "small:1b"
OTHER_MODEL = "other:2b"
PUBLISHED = "2026-01-02T00:00:00Z"

ADVISORY_TEXT = (
    "A remote attacker can send a crafted request to the parser and crash the\n"
    "service. No user interaction is required. The flaw is fixed in 2.0.0."
)
REMOTE = "A remote attacker can send a crafted request to the parser"
NO_INTERACTION = "No user interaction is required."
CRASH = "crash the service"

# Red Hat and GHSA agree throughout; NVD reads Availability differently.
VECTORS = {
    "ghsa": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
    "nvd": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L",
    "redhat": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
}


def finding(key: str = KEY, vectors: Mapping[str, str] = VECTORS) -> Finding:
    """Build one finding the way the audit's join builds it."""
    component = Component("parser", "1.0.0", "pkg:npm/parser@1.0.0", "npm", ("package-lock.json",))
    advisory = Advisory(key, component.purl, "2.0.0", "Parser crash", ADVISORY_TEXT, dict(vectors))
    return build_finding(component, advisory)


def item(key: str = KEY, vectors: Mapping[str, str] = VECTORS) -> Item:
    """Build one dataset item around a finding."""
    return Item(split="V", published=PUBLISHED, finding=finding(key, vectors))


def header(model: str = MODEL, variant: Variant = BASELINE) -> dict[str, str]:
    """Give the least of a pass's header a replay reads: its kind, model and prompt version."""
    return {"kind": "header", "model": model, "prompt_version": variant.prompt_version}


def reply(value: str, evidence: str = REMOTE, confidence: str = "high") -> str:
    """Write a member's reply as the prompt asks for it."""
    return json.dumps({"value": value, "evidence": evidence, "confidence": confidence})


DECLINED = reply(NO_EVIDENCE_VALUE, evidence="", confidence="low")

# One of each kind: verified quotations, one not in the advisory, a guess and a decline.
ANSWERS = {
    "AV": reply("N"),
    "AC": reply("L"),
    "PR": reply("N"),
    "UI": reply("N", evidence=NO_INTERACTION),
    "S": reply("U", evidence="the scope does not change"),
    "C": DECLINED,
    "I": reply("N", evidence=""),
    "A": reply("H", evidence=CRASH),
}


def metric_of(payload: Mapping[str, Any]) -> str:
    """Say which metric a request asks about, read off its system turn."""
    return next(metric for metric in METRIC_ORDER if f"({metric}) measures" in payload["system"])


class Asking:
    """Stand in for `collect.ask_item`: each item put to a fresh fake server."""

    def __init__(self, answers: Mapping[str, str] = ANSWERS, variant: Variant = BASELINE) -> None:
        """Hold the answers every fake server will give, and the variant each item is asked in."""
        self.answers = answers
        self.variant = variant

    def __call__(self, item: Item, model: str) -> list[CallRecord]:
        """Ask one item as a pass does, from a fresh load."""
        return ask_item(item, model, FakeServer(self.answers), self.variant)


class FakeServer:
    """A stand-in for Ollama: it unloads when asked, and answers each metric from a table."""

    def __init__(self, answers: Mapping[str, str] = ANSWERS) -> None:
        """Hold the answer to give for each metric, and remember every request."""
        self.answers = dict(answers)
        self.posted: list[dict[str, Any]] = []

    def __call__(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Answer one request as Ollama's generate endpoint would."""
        self.posted.append(payload)
        if "prompt" not in payload:
            return {"model": payload["model"], "done": True, "done_reason": "unload"}
        response = self.answers[metric_of(payload)]
        return {"model": payload["model"], "response": response, "done": True,
                "load_duration": 2_000_000_000, "context": [1, 2, 3]}

"""Turns a model's opinion about what to audit first into a safe check order.

**Pure by construction, and two tests enforce it**: this module never imports
`model_client` (`tests/parsing/test_offline_containment.py`), and the audit
graph attempts no socket (`tests/parsing/test_offline.py`). The model function arrives as an argument, the way
`checks/advise.py` takes its retriever, and it is called at the edge in
`run_checks.build_findings` -- never inside a LangGraph node.
`tests/parsing/test_offline.py` asserts the audit graph *attempts* no socket,
counting attempts rather than successes, so a model call inside the graph would
fail it even where the model is absent and the code degrades correctly.

**The one invariant: the model may reorder, never remove.** Every eligible check
appears in the returned order exactly once, whatever the model says or fails to
say. A model that could drop a check would decide what counts as a finding, and
`docs/FLOW.md` and `docs/HISTORY.md` both forbid exactly that: the absence
would land in `coverage.checks_run`, which `docs/SCHEMAS.md` defines as "could
not look at all" and the scorer reads as `no_check_for_risk_class`. A silent
recall loss wearing coverage vocabulary. So the merge below is monotone, and
`tests/checks/test_planner_monotone.py` tries to break it with every malformed
reply shape rather than trusting this paragraph.
"""

import json
import sys
from typing import Callable

from artifacts.findings_document import (
    MODEL_DISABLED, MODEL_STATUSES, MODEL_UNAVAILABLE, MODEL_USED)
from checks.plan_selection import NARROWABLE_CHECKS, resolve

# The injected model call: prompt in, reply out. Injected rather than imported
# so this module stays pure -- see the module docstring.
Ask = Callable[[str], str]

# What the model is asked to return. One JSON object, because a bare array
# invites prose either side of it and this way there is a key to find.
ORDER_KEY = "order"

# Which surfaces each check should examine. Absent means "all of them".
SELECTION_KEY = "surfaces"

# How many surfaces the prompt describes. A repo with hundreds would otherwise
# push the real question past the context window.
MAX_SURFACES_DESCRIBED = 40

PROMPT_TEMPLATE = """You are planning a security audit of an LLM application.

These checks are available, and every one of them WILL run regardless of your
answer. Say which order they should run in, most valuable first:
{checks}

The application has these LLM surfaces, each given by its exact id:
{surfaces}

You may also narrow a check to the surfaces most worth auditing. Only these
checks can be narrowed: {narrowable}. A check you do not mention examines every
surface, which is the safe default -- narrow one only when you have a reason.
Never narrow a check to an empty list.

Reply with one JSON object and nothing else:
{{"{order_key}": ["check_name", ...],
  "{selection_key}": {{"check_name": ["surface_id", ...]}}}}

Use only the check names and the exact surface ids listed above."""


def describe_surfaces(surfaces: list) -> str:
    """One line per surface, capped, so the prompt stays a readable size."""
    shown = surfaces[:MAX_SURFACES_DESCRIBED]
    lines = [f"- {surface.kind} {surface.name} at {surface.file}:{surface.line}"
             for surface in shown]
    if len(surfaces) > len(shown):
        lines.append(f"- ... and {len(surfaces) - len(shown)} more")
    return "\n".join(lines) or "- none"


def build_prompt(surfaces: list, eligible: list[str]) -> str:
    """Ask the model to order the checks that are going to run anyway."""
    return PROMPT_TEMPLATE.format(
        checks="\n".join(f"- {name}" for name in eligible),
        surfaces=describe_surfaces(surfaces),
        narrowable=", ".join(sorted(NARROWABLE_CHECKS)),
        order_key=ORDER_KEY, selection_key=SELECTION_KEY)


def _json_object(reply: object) -> dict:
    """The first JSON object in a reply, or an empty one when there is none.

    Models wrap JSON in prose and fences. An unreadable reply is not an error
    here: it means no opinion, and no opinion is a safe answer. `object` rather
    than `str` because that promise has to hold for a reply that is not text at
    all -- `model_client` checks that a response *key* is present but never its
    type, so a server answering `"response": null` reaches this.
    """
    if not isinstance(reply, str):
        return {}
    start, end = reply.find("{"), reply.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(reply[start:end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_order(reply: object) -> list[str]:
    """The check names the model asked for, in its order; [] when it said nothing usable."""
    named = _json_object(reply).get(ORDER_KEY)
    if not isinstance(named, list):
        return []
    return [name for name in named if isinstance(name, str)]


def parse_selection(reply: object) -> dict:
    """The per-check surface choice the model asked for; {} when it asked for none.

    Shape only -- `checks/plan_selection.py` decides which of it stands. Anything
    that is not an object of lists is no opinion, and no opinion means every
    check examines every surface.
    """
    asked = _json_object(reply).get(SELECTION_KEY)
    return asked if isinstance(asked, dict) else {}


def merge_monotonically(model_order: list[str], eligible: list[str]) -> list[str]:
    """Reorder `eligible` by the model's preference, keeping every one of them.

    **Every name in `eligible` is in the result**, which is the whole invariant:
    names the model invented are dropped, names it repeated are taken once, and
    names it omitted are appended in their original order. So the model can move
    work earlier and nothing else.

    Exactly stated, because a looser wording was wrong twice: the result is a
    permutation of `eligible` when `eligible` holds distinct names, which is all
    `run_checks` produces. Given a repeated name it depends on the model --
    `merge_monotonically(["a"], ["a", "a"])` is `["a"]` while
    `merge_monotonically([], ["a", "a"])` is `["a", "a"]`, since the tail copies
    what was not preferred. Deliberately not deduplicated: dropping a name the
    caller asked for twice would make this function *subtract*, and never
    subtracting is the reason it exists.
    """
    wanted = set(eligible)
    preferred: list[str] = []
    for name in model_order:
        if name in wanted and name not in preferred:
            preferred.append(name)
    return preferred + [name for name in eligible if name not in preferred]


def planner_run(status: str, order: list[str], identifier: str | None = None,
                selection: dict | None = None, refused: list[dict] | None = None) -> dict:
    """Record what decided the order, so a reader never has to guess.

    The identifier pairing is enforced *here*, where the record is made, not
    only in `artifacts/planner_document.py` where it is written out. Checking it
    only at the far end let this module build a record the document refused.
    """
    if status not in MODEL_STATUSES:
        raise ValueError(f"unknown planner status {status!r}; expected {MODEL_STATUSES}")
    if status == MODEL_USED and not identifier:
        raise ValueError("a planner that used a model must name it")
    if status != MODEL_USED and identifier is not None:
        raise ValueError(f"status {status!r} must not name a model, got {identifier!r}")
    return {"status": status, "identifier": identifier, "order": list(order),
            # What the model asked each check to examine, and what was refused.
            # Both empty on a run with no model, so a reader can tell a planner
            # that narrowed nothing from one that was never consulted.
            "surface_selection": {check: sorted(ids) for check, ids in (selection or {}).items()},
            "refused_narrowing": list(refused or [])}


def order_checks(surfaces: list, eligible: list[str], ask: Ask | None = None,
                 identifier: str | None = None,
                 selectable: list[str] | None = None) -> tuple[list[str], dict]:
    """Return the order to run the eligible checks in, and the record of who chose it.

    `ask` is the model call, injected. Absent, or failing for any reason, the
    order is `eligible` unchanged -- which is exactly what a model-disabled run
    produces, so `findings.json` is byte-identical either way.
    """
    if ask is None:
        return list(eligible), planner_run(MODEL_DISABLED, eligible)
    if not identifier:
        # Refused at the call rather than after the model has answered: a run
        # that used a model without naming it cannot be reproduced, and the
        # artifact would be rejected anyway once it reached the document.
        raise ValueError("order_checks needs the model's identifier when given an `ask`")
    # Built outside the guard on purpose: a bug in this module's own prompt
    # building must not be reported as the model being unavailable.
    prompt = build_prompt(surfaces, eligible)
    try:
        reply = ask(prompt)
    except RuntimeError as error:
        # `RuntimeError` only, the way `checks/advise.py` and `outputs.py` do it:
        # that is what `model_client` raises for every reach failure. Catching
        # `Exception` would file a wiring bug in this repo -- a wrong arity, a
        # `TypeError` -- as "Ollama could not be reached", which is a claim
        # written into an artifact rather than an internal detail.
        print(f"planner: model unavailable, keeping the planned order ({error})",
              file=sys.stderr)
        return list(eligible), planner_run(MODEL_UNAVAILABLE, eligible)
    order = merge_monotonically(parse_order(reply), eligible)
    described = surfaces[:MAX_SURFACES_DESCRIBED]
    # `selectable`, not `eligible`: the edge checks are never in the graph plan
    # but may still be narrowed, and the probe is the one most worth narrowing --
    # it costs a model call per prompt template.
    chosen, refused = resolve(
        parse_selection(reply), list(selectable or eligible), described, surfaces)
    return order, planner_run(MODEL_USED, order, identifier, chosen, refused)

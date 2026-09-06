"""Extends a scope's tainted names to everything derived from them.

The trace used to taint a name only where it was bound *at* a data source, so a
chain died at its second hop: `response = requests.get(url)` was followed and
`page_text = response.text` was not. Real code almost never hands a source
straight to a model -- it parses it, slices it, formats it -- so one hop is the
difference between following a flow and following almost none.

**This is an over-approximation, deliberately, and it has one cost worth naming
before you read a finding.** A name derived from a tainted one is tainted, and
nothing here knows what a sanitiser is: `safe = sanitise(question)` taints
`safe` exactly as `copy = question` does. So a finding can say a value reached
the model "without validation" when a validator was called on the way. For a
tool that reports to a human and never patches, over-approximating is the right
direction -- a missed flow is silent, an extra one is on the page and arguable
-- but it is a positive claim, and `docs/TODO.md` carries it as a known defect.

Pure, and its own module because `checks/taint.py` is at its size limit and this
is a second job: that file decides what to report, this one decides what a name
is derived from.
"""

import ast

from artifacts.surface import Surface


def _plain_targets(node: ast.Assign) -> list[str]:
    """The bare names an assignment binds, looking through a tuple or list unpack.

    An attribute target is skipped: `self.text = page` binds nothing this trace
    can match later, because every later use is `self.text` and the trace reads
    bare names. That is a limit of the trace, not of this function.
    """
    names = []
    for target in node.targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names += [element.id for element in target.elts
                      if isinstance(element, ast.Name)]
    return names


def _source_within(value: ast.expr, tainted: dict[str, Surface]) -> Surface | None:
    """The source this expression derives from, or None if it mentions no tainted name.

    Sorted by surface id when a value mentions two tainted names, so the same
    file always attributes the same one. `f"{a} {b}"` genuinely derives from
    both; the artifact has room for one, and an arbitrary pick would make the
    document differ between runs for no reason.
    """
    mentioned = [tainted[node.id] for node in ast.walk(value)
                 if isinstance(node, ast.Name) and node.id in tainted]
    return min(mentioned, key=lambda surface: surface.id) if mentioned else None


def _derived_in(body: list[ast.stmt], tainted: dict[str, Surface]) -> dict[str, Surface]:
    """Every name this pass newly finds to be derived from a tainted one."""
    found: dict[str, Surface] = {}
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Assign):
                found.update(_from_assignment(node, tainted))
    return {name: surface for name, surface in found.items() if name not in tainted}


def _from_assignment(node: ast.Assign, tainted: dict[str, Surface]) -> dict[str, Surface]:
    """The names one assignment taints, if its value derives from a tainted name."""
    source = _source_within(node.value, tainted)
    if source is None:
        return {}
    return {name: source for name in _plain_targets(node)}


def propagate(body: list[ast.stmt], seeds: dict[str, Surface]) -> dict[str, Surface]:
    """Return the seeds plus every name in this scope derived from one.

    Repeated to a fixpoint rather than read once top to bottom, because a scope
    is not a straight line: a name can be assigned above the line that taints
    it, inside a loop that runs after it, or in a branch. Each pass only ever
    adds names and the set of names in a scope is finite, so `x = f(x)`
    terminates -- `x` is already tainted and adds nothing.
    """
    tainted = dict(seeds)
    while True:
        added = _derived_in(body, tainted)
        if not added:
            return tainted
        tainted.update(added)

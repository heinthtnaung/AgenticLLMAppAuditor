"""Asks the local model whether a prompt template is built to be injected into.

**Pure of the model, deliberately.** This module never imports `model_client`;
the model call arrives as `model_ask_fn`, the way `checks/planner.py` takes its
`ask` and `checks/advise.py` takes its retriever. `tests/parsing/test_offline.py`
asserts the audit graph *attempts* no socket -- counting attempts, not successes
-- so the call is made at the edge in `run_checks.build_findings` and never
inside a LangGraph node. `tests/parsing/test_offline_containment.py` proves the
import is absent rather than trusting this paragraph.

**What a finding here means, and what it does not.** It means the model, asked
to read one template as an attacker would, judged that the template drops an
untrusted value into instruction text with nothing separating the two. It does
**not** mean an injection was demonstrated: this auditor never runs the audited
app, so nothing here was executed, and a model's opinion about a payload is in
part a fact about that model. That is why the rationale is carried as *probe
evidence* rather than asserted in the title, why `model_digest` is recorded
beside it, and why the title names the template's structure.

`detection` is `probe`, the value `finding.py` has always declared for a
conclusion reached by probing rather than by reading the tree. Two guards depend
on it -- `findings_document._check_probe_citations` refuses a probe finding that
cites no confirmed probe, and `report._probe_lines` refuses to render one whose
probe is missing -- so this check cannot report a verdict without also
publishing the evidence a reader needs to weigh it.
"""

import ast
import re
from pathlib import Path
from typing import Callable

from artifacts.finding import (
    CONFIRMED, INCONCLUSIVE, NOT_RUN, PROBE, REFUTED, SURFACE_SUBJECT,
    Finding, Probe)
from artifacts.skipped_file import UnreadableSource
from artifacts.surface import PROMPT_TEMPLATE, Surface
from checks.taint import python_files
from parsing.extractor_python import parse_file

# The injected model call, the way `checks/planner.py` declares its own.
Ask = Callable[[str], str]

CHECK_NAME = "semantic_probe"

# LLM01 in the 2025 OWASP list: prompt injection, direct and indirect.
OWASP_ID = "LLM01"

TITLE = "Prompt template interpolates a value into instruction text without delimiters"

# Why a probe concluded nothing, from `finding.PROBE_REASONS`.
NO_MODEL = "model_unavailable"
NO_TEXT = "trace_left_static_analysis"

# The model answered, and its answer carried no verdict. Same vocabulary word --
# `PROBE_REASONS` is closed -- but a different probe outcome, so a run that was
# answered unusably is never mistaken for one that could not reach the server.
NO_ANSWER = NO_MODEL

# The two words the model may answer with. A closed question, so a verdict is
# read from one token rather than from prose -- and `None` when it said neither,
# which is a third answer and must not collapse into "safe".
VULNERABLE = "VULNERABLE"
SAFE = "SAFE"

# `NOT VULNERABLE` contains the token and means its opposite.
NEGATORS = frozenset({"NOT", "NON", "NO", "ISNT", "NEITHER"})

# Models fence their answers. Stripped rather than read, or the verdict line is
# never the first line.
FENCE = "```"

# How much of the model's answer is kept as evidence. Long enough to carry a
# reason, short enough that a report stays readable.
MAX_RATIONALE = 400

RED_TEAM_PROMPT = """You are a red team security reviewer examining ONE prompt \
template from an LLM application. You are reading it, not running it.

Template:
---
{template}
---

Decide one structural question: does this template place a value that a user or \
an external document controls directly into instruction text, with no \
delimiter, quoting, or system/data separation around it?

Answer on the first line with exactly one word: VULNERABLE or SAFE.
On the second line give one sentence of reasoning, naming the variable if there \
is one."""


def _render(node: ast.expr) -> str:
    """Rebuild one expression as the text the model will actually be shown.

    The interpolation points are the whole question, so they are rendered as
    `{name}` rather than dropped: an earlier version collected string constants
    only, which deleted every f-string variable and joined the halves with a
    newline -- so the tool removed the value and inserted a delimiter, then
    asked whether a value sat there without one. Everything it cannot rebuild
    answers "", which becomes an inconclusive probe rather than a clean bill.
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else ""
    if isinstance(node, ast.JoinedStr):
        return "".join(_render(part) for part in node.values)
    if isinstance(node, ast.FormattedValue):
        return "{" + ast.unparse(node.value) + "}"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _render(node.left) + _render(node.right)
    return "{" + node.id + "}" if isinstance(node, ast.Name) else ""


def _node_at(tree: ast.AST, line: int) -> ast.AST | None:
    """The prompt-building expression on one line: the call if there is one, else the assignment."""
    here = [node for node in ast.walk(tree) if getattr(node, "lineno", None) == line
            and isinstance(node, (ast.Call, ast.Assign))]
    calls = [node for node in here if isinstance(node, ast.Call)]
    return (calls or here or [None])[0]


def _only_placeholders(text: str) -> bool:
    """Say whether the rendered text is interpolation points and nothing else.

    `from_template(TEMPLATE)` renders as `{TEMPLATE}` -- readable-looking, and
    the instruction text nobody ever saw. Asking the model about that and
    recording `the model read the template as structurally safe` would put a
    verdict in the artifact on the strength of one placeholder, which is the
    same defect as reading an empty reply as a clean bill.
    """
    return not re.sub(r"\{[^{}]*\}", "", text).strip()


def template_text(tree: ast.AST, line: int) -> str:
    """The prompt text built on one line, with its interpolation points kept.

    Empty means the text was assembled somewhere this cannot see, which is a
    probe that did not run rather than a template that is safe -- including the
    case where every part of it is a placeholder. Joined with nothing at all,
    because any separator this adds is a delimiter the template does not have.
    """
    node = _node_at(tree, line)
    if isinstance(node, ast.Assign):
        return _render(node.value)
    if not isinstance(node, ast.Call):
        return ""
    written = [_render(arg) for arg in node.args]
    written += [_render(keyword.value) for keyword in node.keywords]
    text = "".join(part for part in written if part.strip())
    return "" if _only_placeholders(text) else text


def _verdict_in(head: str) -> str | None:
    """The verdict one line carries, or None when it carries neither word.

    Not a first-word test and not a substring test. `Answer: VULNERABLE` and
    `The template is VULNERABLE` are both verdicts, and `NOT VULNERABLE` is the
    opposite of one, so the token is looked for anywhere and then checked for a
    negation in front of it.
    """
    words = re.sub(r"[^A-Z]+", " ", head.upper()).split()
    if VULNERABLE in words:
        spoken = words.index(VULNERABLE)
        return SAFE if spoken and words[spoken - 1] in NEGATORS else VULNERABLE
    return SAFE if SAFE in words else None


def read_verdict(reply: object) -> tuple[str | None, str]:
    """Split the model's answer into its verdict and the reasoning behind it.

    `None` for the verdict means the model said neither word. That is a third
    answer, not a safe one: recording an empty or unparseable reply as "the
    model read this template and cleared it" writes a claim into the artifact
    that nothing supports.
    """
    if not isinstance(reply, str) or not reply.strip():
        return None, ""
    said = [line.strip() for line in reply.strip().splitlines()
            if line.strip() and not line.strip().startswith(FENCE)]
    if not said:
        return None, ""
    rationale = " ".join(said[1:]) or said[0]
    return _verdict_in(said[0]), rationale[:MAX_RATIONALE]


def _probe(surface: Surface, outcome: str, detail: str, reason: str | None = None) -> Probe:
    """Record what the model was asked about this surface and what came back."""
    return Probe(CHECK_NAME, SURFACE_SUBJECT, surface.id, outcome, detail, reason)


def _finding_for(surface: Surface, probe: Probe) -> Finding:
    """Build the finding, citing the probe that carries the model's reasoning."""
    return Finding(
        OWASP_ID, CHECK_NAME, TITLE, PROBE,
        surface_id=surface.id, surface_kind=surface.kind, surface_name=surface.name,
        file=surface.file, line=surface.line, probe_id=probe.id,
    )


def judge(surface: Surface, text: str, ask: Ask) -> tuple[Finding | None, Probe]:
    """Ask the model about one template and turn its answer into a record.

    Always a probe, sometimes a finding: "the model said this looks safe" and
    "the model could not be reached" are different answers, and both are worth
    more than silence.
    """
    if not text:
        return None, _probe(surface, INCONCLUSIVE,
                            "the template's text is not written literally at this line", NO_TEXT)
    try:
        reply = ask(RED_TEAM_PROMPT.format(template=text))
    except RuntimeError as error:
        # `RuntimeError` only, as `model_client` raises for every reach failure.
        # Catching more would file this repo's own wiring bug as an absent model.
        return None, _probe(surface, NOT_RUN, f"the model could not be reached: {error}", NO_MODEL)
    verdict, rationale = read_verdict(reply)
    if verdict is None:
        return None, _probe(surface, INCONCLUSIVE,
                            f"the model answered neither {VULNERABLE} nor {SAFE}: "
                            f"{rationale or '(nothing)'}", NO_ANSWER)
    if verdict == SAFE:
        return None, _probe(surface, REFUTED,
                            rationale or "the model read the template as structurally safe")
    probe = _probe(surface, CONFIRMED, rationale or "the model read the template as injectable")
    return _finding_for(surface, probe), probe


def prompt_surfaces(surfaces: list[Surface], file: str) -> list[Surface]:
    """The file's prompt templates, the only surfaces this check reads."""
    return [s for s in surfaces if s.file == file and s.kind == PROMPT_TEMPLATE]


def run_over_repo(repo_path: str, surfaces: list[Surface],
                  model_ask_fn: Ask | None = None) -> tuple[list[Finding], list[Probe]]:
    """Judge every prompt template in the repository, or nothing at all.

    `model_ask_fn` absent means the probe was not asked for: no probes, no
    findings, and `findings.json` byte-identical to a run without this check.
    That default is what keeps every existing artifact and the whole suite
    unchanged; the probe is something a reader opts into.
    """
    if model_ask_fn is None:
        return [], []
    root = Path(repo_path)
    findings: list[Finding] = []
    probes: list[Probe] = []
    for path in python_files(repo_path):
        try:
            tree = parse_file(path)
        except UnreadableSource:
            continue
        for surface in prompt_surfaces(surfaces, path.relative_to(root).as_posix()):
            finding, probe = judge(surface, template_text(tree, surface.line), model_ask_fn)
            probes.append(probe)
            if finding is not None:
                findings.append(finding)
    return findings, probes

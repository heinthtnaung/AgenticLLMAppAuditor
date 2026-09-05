"""The tree, the stand-in model, and the "before this check existed" document.

Shared by every semantic-probe test file: `test_semantic_probe.py` and
`test_semantic_probe_replies.py` cover the check's own answers,
`test_semantic_probe_reading.py` its two pure functions, and
`test_semantic_probe_document.py` and `test_semantic_probe_provenance.py` what
those answers do to `findings.json`. They all have to be talking about one
audit, so the app is written here once rather than copied.

Everything is written into `tmp_path` by the caller. Nothing here reads a
repository this project does not own, and a synthetic tree is weaker than a real
one: no oversized file, no non-UTF-8 source, no malformed syntax, no template
shape nobody thought of. The counts below are literals for the same reason -- an
audit that produced nothing must not be able to pass as a clean one.

The model never runs either. `Answering` and `Refusing` stand in for
`model_client.ask`, which is the whole point of the check taking it as an
argument: `tests/parsing/test_offline_containment.py` bars the module from
importing the client, so a test can hand it any callable at all.
"""

from pathlib import Path

from artifacts.findings_document import (
    ADVISORY_NOT_INGESTED,
    MODEL_DISABLED,
    build_findings_document,
    coverage,
    model_run,
)
from artifacts.finding import Finding, Probe
from artifacts.surface import Surface
from checks import known_advisory, run_checks, semantic_probe, supply_chain, workflow
from checks.run_checks import build_findings
from parsing.extractor import extract_repo

APP_NAME = "probe-app"
FILE = "agent.py"

# An LLM app with one prompt template and two other things worth reporting, so
# the document a probe lands in is never an empty one. The template is on line 5
# rather than line 1, so a finding anchored on the wrong line cannot pass by
# landing on line 1 by accident. `ShellTool` gives the permission check a
# subject and the `AgentExecutor` is built with no `callbacks=`, which gives the
# auditability check one.
PROMPT_APP = '''from langchain.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor
from langchain_community.tools import ShellTool

prompt = ChatPromptTemplate.from_template("You are a support agent. {question}")
shell = ShellTool()
agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[shell])
'''

# Where the template is, what it is called, and the text the check reads off the
# tree at that line. Spelled out so a probe about some other surface, or about a
# template the extractor read wrongly, cannot satisfy an assertion.
PROMPT_LINE = 5
PROMPT_SURFACE_NAME = "ChatPromptTemplate.from_template"
PROMPT_SURFACE_ID = f"{FILE}:{PROMPT_LINE}:PROMPT_TEMPLATE:{PROMPT_SURFACE_NAME}"
PROBE_ID = f"{semantic_probe.CHECK_NAME}:{PROMPT_SURFACE_ID}"
TEMPLATE_TEXT = "You are a support agent. {question}"

# The same app with the template built out of sight and named at the call site.
# The surface is still detected, so the check has a subject and no text -- the
# state that must read as "did not conclude". `template_text` renders it
# `{TEMPLATE}` today, which is why the two tests using it are red.
NON_LITERAL_APP = '''from langchain.prompts import ChatPromptTemplate

TEMPLATE = open("prompt.txt").read()

prompt = ChatPromptTemplate.from_template(TEMPLATE)
'''

# The same idea with the read written into the call, so the expression is one
# `_render` cannot rebuild at all and the text really is "": the same probed
# state, in the shape the check handles as documented today.
HIDDEN_TEMPLATE_APP = '''from langchain.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_template(open("prompt.txt").read())
'''

# An app whose template is an f-string, the shape the rewrite of `_render` was
# about: the interpolation point is the question being asked, so it has to reach
# the model rather than being deleted and replaced by a newline.
F_STRING_APP = '''from langchain.prompts import ChatPromptTemplate

user_role = "support"

prompt = ChatPromptTemplate.from_template(f"You are a {user_role} agent. Answer the user.")
'''

F_STRING_LINE = 5
F_STRING_VARIABLE = "{user_role}"
F_STRING_TEMPLATE = "You are a {user_role} agent. Answer the user."

# An LLM app with no prompt template at all: a model is offered and there is
# still nothing to ask about, which is what `checks_run` must leave out.
NO_PROMPT_APP = '''from langchain.agents import AgentExecutor
from langchain_community.tools import ShellTool

shell = ShellTool()
agent = AgentExecutor.from_agent_and_tools(agent=None, tools=[shell])
'''

# What `PROMPT_APP` yields with no model offered: three surfaces, two findings
# from two static checks, and four checks with something to examine. Asserted as
# literals wherever the probe's own effect is measured against them.
PROMPT_APP_SURFACES = 3
PROMPT_APP_FINDINGS = 2
PROMPT_APP_CHECKS_RUN = 4

# Provenance shaped like `main.probe_inputs`, which is the one place the real
# client is handed to the check. The digest is bare hex the way Ollama reports
# one, and the settings are non-empty because `model_provenance` refuses a used
# model that cannot say how it was decoded.
PROBE_MODEL = {
    "identifier": "qwen2.5-coder:7b-instruct",
    "settings": {"temperature": 0, "seed": 7},
    "digest": "4c1d9b7e2a350f68" + "0" * 48,
}


class Answering:
    """Stands in for `model_client.ask`: answers one fixed reply and keeps every prompt."""

    def __init__(self, reply: object) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> object:
        """Record what was asked and hand back the answer this stand-in was built with."""
        self.prompts.append(prompt)
        return self.reply


class Refusing:
    """Stands in for a model call that fails, with whichever error the test names."""

    def __init__(self, error: BaseException) -> None:
        self.error = error
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        """Raise the error this stand-in was built with, counting the attempt first."""
        self.calls += 1
        raise self.error


def write_app(tmp_path: Path, source: str = PROMPT_APP) -> Path:
    """Write one Python file into an empty repository and return its path.

    `parents=True` so a test wanting several apps can hand a fresh subdirectory
    of `tmp_path` per answer instead of one repository per test function.
    """
    repo = tmp_path / APP_NAME
    repo.mkdir(parents=True)
    (repo / FILE).write_text(source, encoding="utf-8")
    return repo


def surfaces_of(repo: Path) -> list[Surface]:
    """The surfaces a real audit of that repository would have found."""
    return extract_repo(str(repo)).surfaces


def app_and_surfaces(tmp_path: Path, source: str = PROMPT_APP) -> tuple[Path, list[Surface]]:
    """Write the app and extract its surfaces, which is how every test here starts."""
    repo = write_app(tmp_path, source)
    return repo, surfaces_of(repo)


def probe_over(tmp_path: Path, reply: object,
               source: str = PROMPT_APP) -> tuple[list[Finding], list[Probe], Answering]:
    """Audit the app with a stand-in model that always answers `reply`."""
    repo, surfaces = app_and_surfaces(tmp_path, source)
    ask = Answering(reply)
    findings, probes = semantic_probe.run_over_repo(str(repo), surfaces, ask)
    return findings, probes, ask


def only_probe(tmp_path: Path, reply: object,
               source: str = PROMPT_APP) -> tuple[list[Finding], Probe]:
    """The single probe the app's single prompt template produces."""
    findings, probes, _ask = probe_over(tmp_path, reply, source)
    assert len(probes) == 1, f"expected one prompt template, got {len(probes)} probes"
    return findings, probes[0]


def audited(tmp_path: Path, ask: semantic_probe.Ask | None = None, source: str = PROMPT_APP,
            probe_model: dict | None = PROBE_MODEL) -> tuple[dict, list[Surface]]:
    """Assemble the findings document for the app, with whatever model the test offers.

    `build_findings` returns two documents; the planner record is dropped here
    because this file is about the probe. `tests/checks/test_planner_wiring.py`
    owns the other one.
    """
    repo, surfaces = app_and_surfaces(tmp_path, source)
    document, _planner_document = build_findings(
        str(repo), surfaces, None, None, None, ask, probe_model)
    return document, surfaces


def document_without_the_probe(repo: Path, surfaces: list[Surface]) -> dict:
    """Assemble the findings document the way `build_findings` did before this check existed.

    Deliberately not a recorded blob: it is `build_findings` with the three probe
    lines deleted, so the byte-identity test compares today's default audit
    against the code path it replaced rather than against a fixture that would
    quietly agree with whatever the auditor now does. The private planner is
    imported for the same reason -- reimplementing the plan here would compare
    the auditor to a second auditor.
    """
    planned = run_checks._checks_that_examined_something(str(repo), surfaces, None, None)
    state = workflow.audit(str(repo), surfaces, None, planned, None)
    classes = sorted({run_checks.RISK_CLASS_BY_CHECK[name] for name in state["checks_run"]})
    return build_findings_document(
        state["findings"], state["probes"],
        coverage(len(surfaces), state["checks_run"], risk_classes_checked=classes,
                 unresolved_component_count=supply_chain.unresolved_component_count(None),
                 advisory_data=ADVISORY_NOT_INGESTED,
                 advisory_unreached_component_count=(
                     known_advisory.unreached_component_count(None, None)),
                 advisory_unreached_components=known_advisory.unreached_components(None, None)),
        model_run(MODEL_DISABLED),
    )

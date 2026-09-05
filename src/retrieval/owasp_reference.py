"""The reference entry for each risk this project reports, by deterministic lookup.

A finding already carries its `owasp_id`, so the entry that applies to it is
known before any retrieval happens: this is a table, not a search. It is
injected into every remediation prompt whether or not a knowledge index exists,
and it is not a `sources` entry, because it is a constant of this tool rather
than a passage a run retrieved.

Every entry names its edition. Two need care. `AUDITABILITY` is this project's
own risk class, not an OWASP entry, so it cites the project and carries no
owasp.org URL -- a fabricated citation would be the worst thing a security
report can hold. And this project's `LLM02` denotes insecure output handling,
which is the 2023 numbering: the 2025 list files that risk as LLM05, so the
entry says so and cites the 2025 LLM05 page rather than the 2025 LLM02 page,
which is a different risk. The summaries are written in this project's words.
"""

from dataclasses import dataclass

from artifacts.finding import OWASP_IDS

OWASP_2025 = "OWASP Top 10 for LLM Applications 2025"
THIS_PROJECT = "this project"
OWASP_SITE = "https://genai.owasp.org/"
LLM02_NOTE = (f"{OWASP_2025}, entry LLM05 Improper Output Handling -- this project's "
              "LLM02 keeps the 2023 numbering for the same risk")


@dataclass(frozen=True)
class Reference:
    """One risk class: what it is, what a fix must achieve, and who says so."""

    title: str
    summary: str
    mitigations: tuple[str, ...]
    source: str
    url: str | None

    def prompt_text(self) -> str:
        """The entry as the prompt carries it: title, source, summary, mitigations."""
        points = " ".join(f"({number}) {text}" for number, text in enumerate(self.mitigations, 1))
        return f"{self.title} [{self.source}]. {self.summary} Key mitigations: {points}"


REFERENCES = {
    "LLM01": Reference(
        title="Prompt Injection",
        summary=("Text the model reads -- from a user, a document, a web page or a tool "
                 "result -- is interpreted as instruction, so an attacker who controls any "
                 "of it can redirect what the model does."),
        mitigations=(
            "Keep instructions and data apart: mark retrieved or user-supplied text as data "
            "in the prompt and never let it carry system-level directives.",
            "Constrain what the model can do so a hijacked model has little to reach: least "
            "privilege on every tool and no sensitive action without a human in the loop.",
            "Validate the model's output before acting on it, treating it as untrusted.",
        ),
        source=OWASP_2025, url="https://genai.owasp.org/llmrisk/llm01-prompt-injection/"),
    "LLM02": Reference(
        title="Insecure output handling",
        summary=("Model output is passed to another component -- a shell, an interpreter, a "
                 "database, a browser -- without being checked, so anything the model was "
                 "led to say becomes a command."),
        mitigations=(
            "Treat the model's output as untrusted input to whatever consumes it: validate, "
            "encode or parameterise it as you would a user's.",
            "Never execute model-written code or queries directly; go through an allow-list "
            "or a parameterised interface.",
            "Log what was passed on, so a bad output can be traced after the fact.",
        ),
        source=LLM02_NOTE,
        url="https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/"),
    "LLM03": Reference(
        title="Supply Chain",
        summary=("A third-party model, dataset, package or plugin the application depends on "
                 "carries a known vulnerability, a poisoned artefact or an unclear "
                 "provenance, and the application inherits it."),
        mitigations=(
            "Know what is in the application: keep a bill of materials for packages and "
            "for models, and check it against advisory data.",
            "Pin exact versions and verify integrity, so a re-install cannot silently pull "
            "something else.",
            "Review the licence and provenance of every model and dataset before use.",
        ),
        source=OWASP_2025, url="https://genai.owasp.org/llmrisk/llm032025-supply-chain/"),
    "LLM06": Reference(
        title="Excessive Agency",
        summary=("The model can reach tools, permissions or autonomy beyond what its task "
                 "needs, so a wrong or manipulated decision has real consequences."),
        mitigations=(
            "Give the model the narrowest tool that does the job, with the fewest "
            "permissions, and no open-ended shell, code or network access by default.",
            "Require a person to approve any action that changes state or touches sensitive "
            "data.",
            "Check authorisation in the tool itself, from who asked, not from what the model "
            "claims.",
        ),
        source=OWASP_2025, url="https://genai.owasp.org/llmrisk/llm062025-excessive-agency/"),
    "AUDITABILITY": Reference(
        title="Inadequate auditability of agent actions",
        summary=("The application keeps no durable record of which tools the model called, "
                 "with what, and what came back, so an incident cannot be reconstructed and "
                 "a misuse cannot be shown."),
        mitigations=(
            "Record every tool call and its result to an append-only log, with who or what "
            "initiated the session.",
            "Make the record tamper-evident and keep it apart from the application's own "
            "storage.",
            "Review the log: a record nobody reads is not an audit trail.",
        ),
        source=THIS_PROJECT, url=None),
}

if set(REFERENCES) != set(OWASP_IDS):
    raise ValueError(f"REFERENCES {sorted(REFERENCES)} must cover exactly {sorted(OWASP_IDS)}")


def reference_for(owasp_id: str) -> Reference:
    """The entry for one risk id, refusing an id this project does not report."""
    if owasp_id not in REFERENCES:
        raise ValueError(f"no reference for {owasp_id!r}; expected one of {sorted(REFERENCES)}")
    return REFERENCES[owasp_id]

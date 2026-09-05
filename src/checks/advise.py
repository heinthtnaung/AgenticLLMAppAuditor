"""Asks the local model for remediation advice, one finding at a time.

The only place in this project that calls a model during an audit. It builds a
prompt from evidence the tool already gathered -- and, since Phase 6, from the
reference entry for the finding's risk class and any passages a retriever hands
it -- sends it, and hands the raw answer to the rules in `artifacts.advice_rules`
to be accepted or refused. It decides nothing about the answer itself, and it
retrieves nothing itself: the retriever is passed in, so this module never
imports the knowledge base and a test can hand it any passages it likes.

There is no canned fallback. If the server cannot be reached the artifact says
so on every entry, because advice nobody wrote must never be mistaken for advice
a model produced.
"""

import re
from typing import Callable

import model_client
from artifacts.advice_rules import app_identifiers, evidence_line, judge
from artifacts.remediation import MODEL_UNAVAILABLE, SAFER_LABEL, UNAVAILABLE, advice_entry
from parsing.languages import LANGUAGES
from retrieval.owasp_reference import reference_for

MAX_SENTENCES = 4

# A bound on the whole prompt for the fixture findings. Ollama drops the *front*
# of a prompt that overruns its context, silently, and the front is where the
# instructions live; the reference block is placed before the rules below so an
# overrun would cost passages first, and the retriever's own budget keeps the
# block well under this. Not a runtime bound -- `module_names` is unbounded.
PROMPT_BUDGET = 6000

# What a finding's retriever returns: the reference text for the prompt, and
# the attributions to record. `Grounding.passages_for` has this shape.
Retriever = Callable[[dict], tuple[str, list[dict]]]

# Enumerating the forbidden tokens measurably lowers the refusal rate, so the
# prompt does it. It is an efficiency, never the guard: told the same thing in
# general terms, the model quoted the app's own identifier straight back.
# The edition is not asserted here: the reference block names it per risk class,
# and one of them keeps an older numbering.
PROMPT_TEMPLATE = """You are advising a security reviewer on one finding in an \
LLM application. The reviewer applies any change themselves. You are not writing \
a patch.

Finding: {title}
Risk class: {owasp_id}
Evidence: {evidence}

Reference for this risk class: {reference}
{passages}
Write at most {max_sentences} sentences on what is wrong and what a fix must \
achieve. Then give at most one fenced code block showing a safer generic pattern.

The code block must use placeholder names only. It must NOT contain any of these \
strings: {forbidden}. Do not write a diff. Do not mention any OWASP id other than \
{owasp_id}.
"""

PASSAGES_HEADER = ("Guidance retrieved from the knowledge base, each passage labelled with "
                   "its source; ground the advice in it where it applies:")

# Both markers: a model that reaches for ~~~ should have its snippet judged
# like any other, not refused for the shape of the fence it chose.
FENCE = re.compile(r"(?:```|~~~)(\w+)?\n(.*?)(?:```|~~~)", re.S)


def _passages_section(passages: str) -> str:
    """The retrieved passages as a block of the prompt, or nothing when there are none."""
    return f"\n{PASSAGES_HEADER}\n\n{passages}\n" if passages else ""


def build_prompt(finding: dict, module_names: tuple[str, ...] = (), passages: str = "") -> str:
    """Compose the one prompt this finding is advised on. Pure: retrieval is an argument."""
    forbidden = app_identifiers(finding, module_names)
    return PROMPT_TEMPLATE.format(
        title=finding["title"], owasp_id=finding["owasp_id"],
        evidence=evidence_line(finding), max_sentences=MAX_SENTENCES,
        reference=reference_for(finding["owasp_id"]).prompt_text(),
        passages=_passages_section(passages),
        forbidden=", ".join(forbidden) or "any identifier from the audited application",
    )


def split_answer(answer: str, language: str) -> tuple[str, list[dict]]:
    """Separate the prose from the fenced blocks, without judging either."""
    snippets = [
        {"label": SAFER_LABEL,
         "language": fenced if fenced in LANGUAGES else language,
         "code": code.strip()}
        for fenced, code in FENCE.findall(answer)
    ]
    return FENCE.sub("", answer).strip(), snippets


def advise_one(finding: dict, language: str, module_names: tuple[str, ...] = (),
               retriever: Retriever | None = None) -> dict:
    """Ask the model about one finding and return the entry, accepted or refused."""
    passages, sources = retriever(finding) if retriever else ("", [])
    try:
        answer = model_client.ask(build_prompt(finding, module_names, passages))
    except RuntimeError:
        return advice_entry(finding["finding_id"], UNAVAILABLE, MODEL_UNAVAILABLE)
    guidance, snippets = split_answer(answer, language)
    status, reason, rejected_on = judge(finding, guidance, snippets, module_names)
    if reason:
        return advice_entry(finding["finding_id"], status, reason, rejected_on)
    return advice_entry(finding["finding_id"], status, guidance=guidance, snippets=snippets,
                        sources=sources)


def advise_all(findings: list[dict], language: str, module_names: tuple[str, ...] = (),
               retriever: Retriever | None = None) -> list[dict]:
    """Advise on every finding, so the artifact carries one entry per finding."""
    return [advise_one(finding, language, module_names, retriever) for finding in findings]

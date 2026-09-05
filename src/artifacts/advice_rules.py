"""The rules that accept or refuse a model's advice, applied after it has spoken.

Split out of `artifacts/remediation.py`, which keeps the artifact's shape and
vocabulary; this module holds the judging. The two halves were one file until
it outgrew the size cap, and they are two jobs: one says what a record may look
like, the other decides whether an answer earns one.

**The guard runs on the answer, never on the question.** Prompt wording is not a
safety property: measured against `qwen2.5-coder:7b-instruct`, "do not reference
this app's identifiers" produced a snippet naming the audited app's own
`st.chat_input`, while enumerating the forbidden tokens did not. A property that
turns on how a sentence is phrased cannot be what separates an illustration from
a patch, so every rule here is applied after the model has spoken.

**Advice is refused whole, never edited.** A sanitised snippet has two authors
and is testable as neither; a snippet with one identifier stripped can still be
applicable. Refusals are recorded so a reader can tell "the model wrote nothing"
from "the model wrote something and it was refused".

One function here judges nothing: `evidence_line`. It describes a finding, and
it lives here because both callers of the rules need it -- the prompt says what
the evidence is, and the retriever turns the same words into its query -- so
this is the one module both already import.
"""

import re

from artifacts.finding import OWASP_IDS
from artifacts.remediation import (
    CODE_FENCE_IN_GUIDANCE,
    EMPTY_ANSWER,
    GUIDANCE_TOO_LONG,
    NAMES_APP_IDENTIFIER,
    RECLASSIFIES,
    REJECTED,
    SNIPPET_IS_A_DIFF,
    SNIPPET_LABELS,
    SNIPPET_TOO_LONG,
    UNKNOWN_LABEL,
    UNKNOWN_LANGUAGE,
    WRITTEN,
)
from parsing.languages import LANGUAGES

# A snippet long enough to be a replacement module is a patch by volume.
MAX_SNIPPET_LINES = 20
MAX_SNIPPETS_PER_FINDING = 2
MAX_GUIDANCE_CHARS = 1200

# Which evidence fields a snippet may not quote back. Naming the function, the
# file or the module it would be pasted into is what makes a snippet applicable
# to this repository rather than illustrative of the class.
EVIDENCE_FIELDS = ("surface_name", "file", "component_name", "purl", "module")

# Patch form, by any of the shapes a reader could feed to `git apply`.
DIFF_LINE = re.compile(r"^\s*(diff --git|@@|---\s|\+\+\+\s|[+-][^+-])", re.M)
# Both fence markers, and a run of indented lines: prose is the other channel
# the model can write into, and a guard that watches only the snippet field
# stops nothing -- a whole diff fits in a paragraph.
CODE_FENCE = re.compile(r"```|~~~")
INDENTED_BLOCK = re.compile(r"^[ \t]{4,}\S.*\n[ \t]{4,}\S", re.M)

# A dotted name can be split across lines and still call the same thing:
# `cursor.\<newline>    execute(sql)` is valid Python and is the app's own call.
# Matching the raw text alone misses it, so the check also reads a form with
# line continuations and the whitespace around dots removed.
CONTINUATION = re.compile(r"\\\s*\n\s*")
AROUND_DOT = re.compile(r"\s*\.\s*")


def _joined(text: str) -> str:
    """Rejoin a name split across lines, so formatting cannot hide it.

    Only around dots and line continuations. Collapsing all whitespace would
    join words that were never one name -- "Shell Tool" in an error message
    would read as the identifier `ShellTool` -- and refuse advice that names
    nothing.
    """
    return AROUND_DOT.sub(".", CONTINUATION.sub("", text))


def _word_present(needle: str, haystack: str) -> bool:
    """Say whether a token appears as a whole word, so `os` does not match `chosen`."""
    pattern = rf"(?<![\w.]){re.escape(needle)}(?![\w])"
    return bool(re.search(pattern, haystack) or re.search(pattern, _joined(haystack)))


def evidence_line(finding: dict) -> str:
    """Describe the evidence behind one finding, in the words the artifact uses."""
    parts = []
    if finding.get("surface_kind") and finding.get("surface_name"):
        parts.append(f"a {finding['surface_kind']} surface named {finding['surface_name']}")
    if finding.get("file") and finding.get("line"):
        parts.append(f"at {finding['file']}:{finding['line']}")
    if finding.get("component_name"):
        parts.append(f"in the component {finding['component_name']}")
    return ", ".join(parts) or "no code location recorded"


def app_identifiers(finding: dict, module_names: tuple[str, ...] = ()) -> list[str]:
    """The audited app's own symbols, which advice about it must not quote back."""
    found = {str(finding[field]) for field in EVIDENCE_FIELDS if finding.get(field)}
    basenames = {value.rsplit("/", 1)[-1] for value in found if "/" in value}
    return sorted(found | basenames | set(module_names))


def foreign_owasp_ids(text: str, owasp_id: str) -> list[str]:
    """The risk ids a text names other than the finding's own, in vocabulary order.

    Naming its own class is useful; naming another re-classifies the finding.
    Shared with the retriever, which drops a passage that would make the answer
    do exactly that.
    """
    return [one for one in OWASP_IDS if one != owasp_id and _word_present(one, text)]


def _reject_snippet(snippet: dict, identifiers: list[str]) -> tuple[str, str] | None:
    """Return the reason and offending field for one snippet, or None if it passes."""
    if snippet.get("label") not in SNIPPET_LABELS:
        return UNKNOWN_LABEL, "label"
    if snippet.get("language") not in LANGUAGES:
        return UNKNOWN_LANGUAGE, "language"
    code = snippet.get("code", "")
    if len(code.splitlines()) > MAX_SNIPPET_LINES:
        return SNIPPET_TOO_LONG, "code"
    if DIFF_LINE.search(code):
        return SNIPPET_IS_A_DIFF, "code"
    named = [one for one in identifiers if _word_present(one, code)]
    return (NAMES_APP_IDENTIFIER, "code") if named else None


def _reject_guidance(guidance: str, owasp_id: str) -> tuple[str, str] | None:
    """Return the reason prose is refused, or None if it passes.

    Prose is held to the patch rules too. It may still *name* the finding's file
    and surface -- a reader needs to know where to look, and that is the point
    of the advice -- but it may not carry a diff, a fenced block or an indented
    one. Checking only the snippet field would leave the whole mechanism
    walkable: a unified diff reads as a paragraph and renders with none of the
    warnings a snippet gets.
    """
    if not guidance.strip():
        return EMPTY_ANSWER, "guidance"
    if len(guidance) > MAX_GUIDANCE_CHARS:
        return GUIDANCE_TOO_LONG, "guidance"
    if DIFF_LINE.search(guidance):
        return SNIPPET_IS_A_DIFF, "guidance"
    if CODE_FENCE.search(guidance) or INDENTED_BLOCK.search(guidance):
        return CODE_FENCE_IN_GUIDANCE, "guidance"
    return (RECLASSIFIES, "guidance") if foreign_owasp_ids(guidance, owasp_id) else None


def judge(finding: dict, guidance: str, snippets: list[dict],
          module_names: tuple[str, ...] = ()) -> tuple[str, str | None, str | None]:
    """Accept or refuse one answer whole, returning (status, reason, rejected_on)."""
    refusal = _reject_guidance(guidance, finding["owasp_id"])
    if refusal:
        return REJECTED, refusal[0], refusal[1]
    if len(snippets) > MAX_SNIPPETS_PER_FINDING:
        return REJECTED, SNIPPET_TOO_LONG, "snippets"
    identifiers = app_identifiers(finding, module_names)
    for snippet in snippets:
        refusal = _reject_snippet(snippet, identifiers)
        if refusal:
            return REJECTED, refusal[0], refusal[1]
    return WRITTEN, None, None

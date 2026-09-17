"""Drafts a grading key with the local model, when a human has not written one.

**This is circular evaluation and the artifacts say so.** A grading key is
supposed to be the independent answer a run is marked against. One drafted by
the same model the auditor runs measures the model's agreement with itself, not
the tool's recall: a defect the model cannot see when auditing it will also be
absent from the key it writes, and the score comes out flattering for the one
reason a score must never come out flattering. The user asked for it knowingly,
so it ships -- writing `source: "tool_drafted"` and `verified: false`, which
makes the scorer attach `key_ai_drafted`, `key_unverified` and
`key_drafted_by_scored_system` to every figure the key produces. The last of
those is the one that matters: it survives a human verifying every entry,
because verification cannot make the tool's own choice of what to include
independent.

Two things keep it from doing damage. Drafted keys are written to `grading_keys/drafts/`,
never to `grading_keys/` itself, so a key a human maintains cannot be
overwritten and the shipped set stays what a human put in it. And the model is
given the extracted surfaces only, and an entry naming anything else is dropped
by `draft`. Two consequences, both stated here because nothing in the output
records them: a key drafted this way can never contain an entry that falsifies
the surface extractor, and it is bounded above by what the extractor found.
"""

import json
from pathlib import Path

from artifacts.surface import Surface
from checks.advise import Ask
from keys.grading_keys import KEYS_DIR, TOOL_DRAFTED

# Beside the keys, and invisible to every path that looks for one. Three things
# make that true and all three are load-bearing:
#
#   `discover_graded_apps` globs NON-recursively, so a draft one level down is
#   not an enrolled app -- it is not scored, and `check_not_a_graded_app` does
#   not refuse the next fetch of the same URL.
#   `.gitignore` ignores this subfolder while `grading_keys/` itself stays
#   tracked, so a model-written answer key cannot be committed as evidence.
#   A human moving the pair up one level is what accepts the draft.
DRAFTED_KEYS_DIR = KEYS_DIR / "drafts"

# The scorer reads this shape; `harness.KEY_SCHEMA_VERSION` is the authority.
SCHEMA_VERSION = 3

# Not `ai_drafted`. That says a model wrote the key; this says *the system being
# scored* wrote it, which is the stronger warning and the one a reader needs.
# It earns `key_ai_drafted` and `key_drafted_by_scored_system` both.
SOURCE = TOOL_DRAFTED

# A key that does not claim completeness makes false positives unmeasurable
# rather than wrong -- the honest setting for a draft nobody has checked.
COMPLETE = False

# Surfaces shown to the model in one prompt. A prompt naming every surface of a
# large app is both slow and worse: the model starts summarising rather than
# reading. Measured on nothing -- chosen, and worth revisiting.
MAX_SURFACES = 40

PROMPT = """You are drafting a security grading key for an LLM application.

Below are the LLM surfaces a static extractor found. For each one that you \
believe carries a real, reachable defect, write one entry. Skip the ones that \
do not: a key listing everything is worthless.

Surfaces:
{surfaces}

Reply with one JSON array and nothing else. Each element:
{{"id": "K-01", "file": "<file>", "line": <line>, "owasp_id": "<one of \
{risk_classes}>", "llm_surface": "<the surface kind, or null>", \
"surface_name": "<the surface name, or null>", "component": null, \
"detection": "static", "title": "<one line>", "description": "<why this is a \
defect, in terms of what the code does>"}}

Use only the files, lines and names listed above."""


def _describe(surfaces: list[Surface]) -> str:
    """One line per surface, capped, so the prompt stays a size a model reads."""
    return "\n".join(f"- {s.kind} {s.name} at {s.file}:{s.line}"
                     for s in surfaces[:MAX_SURFACES])


def _entries(reply: str) -> list[dict]:
    """The first JSON array in a reply, or none at all.

    A model wraps JSON in prose and fences. An unreadable reply means no
    entries, and an empty key is refused by the caller rather than written:
    scoring against zero entries would report perfect recall over nothing.
    """
    start, end = reply.find("["), reply.rfind("]")
    if start < 0 or end < start:
        return []
    try:
        parsed = json.loads(reply[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [entry for entry in parsed if isinstance(entry, dict)] if isinstance(
        parsed, list) else []


def draft(surfaces: list[Surface], ask: Ask,
          risk_classes: tuple[str, ...]) -> list[dict]:
    """Ask the model which surfaces carry defects, and return the entries it named.

    Entries the model invented are dropped rather than written: a hallucinated
    file, line or risk class reaches `matches_key` and scores against code that
    does not exist. Measured on one run: 12 entries came back, every one
    labelled the same risk class.
    """
    if not surfaces:
        return []
    reply = ask(PROMPT.format(surfaces=_describe(surfaces),
                              risk_classes=", ".join(risk_classes)))
    shown = {(s.file, s.line) for s in surfaces[:MAX_SURFACES]}
    return [entry for entry in _entries(reply if isinstance(reply, str) else "")
            if _is_grounded(entry, shown, risk_classes)]


def _is_grounded(entry: dict, shown: set[tuple[str, int]],
                 risk_classes: tuple[str, ...]) -> bool:
    """True when the entry names a surface that was shown, a real risk class, and an id.

    `id` is bounded here like the other three, and for a sharper reason: it is
    the third element of the `(file, line, id)` sort two lines below, so a reply
    naming one surface twice with ids `1` and `"K-02"` -- the very shape
    `_colliding_pairs` exists to refuse -- raised `TypeError` out of `sorted`.
    That is in neither `pipeline.DRAFTING_FAILURES` nor `main.EXPECTED_FAILURES`,
    so `--draft-key` ended in a traceback *after* the audit had succeeded and
    every artifact was already on disk. Dropped rather than coerced: an entry the
    model labelled with a number is an entry it did not label.
    """
    return (entry.get("owasp_id") in risk_classes
            and isinstance(entry.get("id"), str)
            and (entry.get("file"), entry.get("line")) in shown)


CODE_ANCHOR_LENGTH = 60


def _anchor(app_dir: Path, file: str, line: int) -> str:
    """The trimmed first 60 characters of the source at that line, or empty.

    Read from disk, never asked of the model: an anchor is a quotation, and a
    model asked to quote source it was not shown invents it. An unreadable file
    or a line past the end yields "", which promotion refuses -- absent is a
    fact a human can act on, invented text is not.
    """
    try:
        lines = (app_dir / file).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if not 1 <= line <= len(lines):
        return ""
    return lines[line - 1].strip()[:CODE_ANCHOR_LENGTH]


def _in_documented_order(entries: list[dict]) -> list[dict]:
    """Sorted by (file, line, id), the order two key revisions can be diffed in."""
    return sorted(entries, key=lambda e: (e["file"], e["line"], e.get("id", "")))


def anchored(entries: list[dict], app_dir: Path) -> list[dict]:
    """Every entry with its code anchor filled in from the source it names."""
    return [{**entry, "code_anchor": _anchor(app_dir, entry["file"], entry["line"])}
            for entry in entries]


def key_document(app: str, entries: list[dict], commit: str,
                 surfaces: list[Surface] | None = None) -> dict:
    """Wrap the drafted entries in the shape the scorer reads.

    `expected_surfaces` is what the extractor found, not what the model said:
    the two answer different questions, and a key that conflates them cannot
    say a surface was missed. Neither list claims completeness.
    """
    ordered = _in_documented_order(entries)
    expected = [_expected(s) for s in (surfaces or [])]
    return {
        "app": app, "schema_version": SCHEMA_VERSION, "source": SOURCE,
        "verified": False, "verified_by": None, "verified_date": None,
        "upstream_commit": commit,
        "findings": ordered, "finding_count": len(ordered),
        "expected_surfaces": expected, "expected_surface_count": len(expected),
        # Neither list claims to be complete, so the scorer reports false
        # positives as unmeasurable instead of counting them against a key
        # nobody checked.
        "findings_complete": COMPLETE, "expected_surfaces_complete": COMPLETE,
    }


def _expected(surface: Surface) -> dict:
    """One surface as a key records it, so a miss can be told from a bad find.

    The four fields `expected_surfaces` needs to answer "was this surface
    extracted at all": where it is, what kind it is, and what it is called.
    Deliberately not the whole `Surface` -- an id encodes the other four and
    would make the key's shape move whenever the id format does.
    """
    return {"file": surface.file, "line": surface.line,
            "kind": surface.kind, "name": surface.name}

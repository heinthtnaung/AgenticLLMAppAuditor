"""Renders remediation.json and findings.json as advice a person can read.

A rendering, not a producer: what is wrong comes from the findings, what to do
comes from the model, and this file joins them. Nothing here decides anything.

Every code block carries a fixed note above it saying it is illustrative and
generic by contract. That note is not decoration -- it is the rendering half of
the mechanism that replaced an outright ban on model-written fixes, and it is a
named constant so no caller can render a block without it.
"""

import json
from pathlib import Path

from artifacts.remediation import (
    KNOWLEDGE_INDEXED,
    REJECTED,
    SCHEMA_VERSION,
    UNAVAILABLE,
    WRITTEN,
)
from retrieval.manifest import DIGEST_PREFIX, SOURCES
from retrieval.owasp_reference import reference_for

HEADING = "# How to fix what was found: {app}"

ILLUSTRATION_NOTE = (
    "*Illustrative only. Written by a local model and generic by contract — it names none "
    "of this app's files, modules or identifiers. It is not a patch, and nothing here has "
    "been applied.*"
)

NOTHING_TO_FIX = "No findings, so there is nothing to advise on. That is not a clean bill — see the audit report for what was never examined."

NO_MODEL = ("**No advice was written.** The local model could not be reached, so every "
            "finding below is listed without it. Nothing was substituted in its place.")

# Enough of the digest to identify a build, the way a short commit hash does.
# A tag alone is not provenance: `:latest` names
# a different model next month. Named for the count, not the `sha256:` prefix --
# `retrieval/manifest.py` owns a constant of that name and it is a string.
DIGEST_CHARS = 12

GROUNDED_ON = "**Grounded on**:"
# Reproducing passages obliges the report to name the licence they came under.
LICENCE_NOTE = ("*Retrieved passages are quoted from {names} under their own licences "
                "({licences}); each is linked above.*")


def _provenance_lines(run: dict, knowledge: dict) -> list[str]:
    """Name the model that wrote the advice, so a reader knows whose words these are.

    Nothing when no model ran: the "no advice was written" block below says that
    more usefully, and two lines making the same point read as a stutter.
    """
    if run["status"] != "used":
        return []
    digest = run.get("model_digest")
    pinned = f", build `{digest[:DIGEST_CHARS]}`" if digest else ", build not recorded"
    settings = ", ".join(f"{key} {value}" for key, value in sorted(run["model_settings"].items()))
    return [f"**Advice written by `{run['model_identifier']}`**{pinned}, run at {settings}. "
            "Every word below the findings is that model's; a different model would write "
            f"different advice.{_grounding_clause(knowledge)}", ""]


def _grounding_clause(knowledge: dict) -> str:
    """Say on the same line what grounded the advice, or that nothing did.

    Appended rather than given a line of its own: the provenance line has a
    fixed place in the report, and a reader looking for "whose words are these"
    should find "and what were they based on" in the same breath.
    """
    if knowledge["status"] != KNOWLEDGE_INDEXED:
        return (f" No knowledge base was retrieved from (`{knowledge['reason']}`), so the "
                "advice rests on the evidence and the risk class alone.")
    short = knowledge["manifest_digest"].removeprefix(DIGEST_PREFIX)[:DIGEST_CHARS]
    return (f" It was grounded on {knowledge['source_count']} knowledge "
            f"source(s), indexed with `{knowledge['embed_model']}` at manifest `{short}`.")


def _summary_line(document: dict) -> str:
    """Say how many findings carry advice, and why the rest do not."""
    counts = document["status_counts"]
    parts = [f"{counts[WRITTEN]} of {document['advice_count']} findings carry advice"]
    if counts[REJECTED]:
        parts.append(f"{counts[REJECTED]} were refused because the model's answer broke the "
                     "contract on what advice may contain")
    if counts[UNAVAILABLE]:
        parts.append(f"{counts[UNAVAILABLE]} were not attempted")
    return ". ".join(parts) + "."


def _snippet_lines(snippet: dict) -> list[str]:
    """Render one illustration, always beneath the note that says what it is not."""
    return ["", ILLUSTRATION_NOTE, "", f"```{snippet['language']}", snippet["code"], "```"]


def _grounded_on_lines(entry: dict, owasp_id: str) -> list[str]:
    """List what the advice was based on: the risk class entry, then each passage.

    A flat bullet list rather than a table or a nested one, because
    `markdown_html.py` is a deliberate subset: it refuses tables, has no link
    syntax, and reads a bullet only at column zero. An indented bullet fell
    through to a paragraph there and shipped its `- ` marks as text, so the
    label is a line of its own and the citations are its siblings. The URL is
    rendered plainly so it survives Markdown, HTML and PDF alike.
    """
    reference = reference_for(owasp_id)
    cited = [reference.source + (f" — {reference.url}" if reference.url else "")]
    cited += [f"{source['source']} `{source['path']}`"
              + (f" — {source['heading']}" if source["heading"] else "")
              + f" — {source['url']}" for source in entry["sources"]]
    return ["", GROUNDED_ON, ""] + [f"- {one}" for one in cited]


def _advice_lines(entry: dict, finding: dict) -> list[str]:
    """Render one finding and whatever advice survived the contract."""
    where = f"{finding['file']}:{finding['line']}" if finding.get("file") else "no code location"
    lines = [
        f"### {finding['owasp_id']} — {finding['title']}",
        "",
        f"- **Where**: `{where}`",
        f"- **Finding**: `{entry['finding_id']}`",
    ]
    if entry["status"] == WRITTEN:
        lines += ["", entry["guidance"]]
        for snippet in entry["snippets"]:
            lines += _snippet_lines(snippet)
        lines += _grounded_on_lines(entry, finding["owasp_id"])
    elif entry["status"] == REJECTED:
        lines += ["", f"**No advice is shown here.** The model answered and the answer was "
                      f"refused: `{entry['reason']}`. A refusal is recorded rather than "
                      "hidden, and the answer is not shown even in part."]
    else:
        lines += ["", f"**Not attempted**: `{entry['reason']}`."]
    return lines + [""]


def _licence_lines(remediation: dict) -> list[str]:
    """Name the licence of every source actually cited, once for the whole report."""
    cited = sorted({source["source"] for entry in remediation["advice"]
                    for source in entry["sources"]})
    if not cited:
        return []
    return ["", LICENCE_NOTE.format(
        names=", ".join(cited),
        licences=", ".join(sorted({SOURCES[name].license for name in cited})))]


def _check_readable(remediation: dict) -> None:
    """Refuse a remediation.json older than the fields this report is built on.

    The sibling of `report.py`'s check. A run always renders the file it just
    wrote, so this fires only on a file left on disk by an earlier version --
    which is exactly when a traceback is least useful.
    """
    version = remediation.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"remediation.json is schema_version {version}; this report needs "
            f"{SCHEMA_VERSION}. Regenerate it — an older file records neither what "
            "grounded the advice nor which passages each entry cited.")


def render(app: str, remediation: dict, findings_document: dict) -> str:
    """Return the whole remediation report as Markdown."""
    _check_readable(remediation)
    findings = {finding["finding_id"]: finding for finding in findings_document["findings"]}
    lines = [HEADING.format(app=app), ""] + _provenance_lines(
        remediation["model_run"], remediation["knowledge_base"])
    if not remediation["advice"]:
        return "\n".join(lines + [NOTHING_TO_FIX, ""])
    if remediation["model_run"]["status"] != "used":
        lines += [NO_MODEL, ""]
    lines += [_summary_line(remediation), ""]
    for entry in remediation["advice"]:
        lines += _advice_lines(entry, findings[entry["finding_id"]])
    return "\n".join(lines + _licence_lines(remediation))


def render_from_files(app: str, remediation_path: Path, findings_path: Path) -> str:
    """Render from the two artifacts on disk, which are its only inputs."""
    remediation = json.loads(remediation_path.read_text(encoding="utf-8"))
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    return render(app, remediation, findings)

"""The remediation artifact: its shape, its vocabulary, and the records it holds.

`SCHEMAS.md` once forbade a model-written fix outright, on the grounds that a
patch is one copy-paste from crossing the no-auto-fixing boundary. That decision
was reversed deliberately, so the boundary needs a mechanism rather than a
prohibition. The mechanism has two halves: the rules that accept or refuse an
answer live in `artifacts/advice_rules.py`; this module owns what an accepted
or refused answer is recorded *as*, and refuses a record a reader could not act
on. The rules import the vocabulary from here, never the other way round.

This file lives apart from `findings.json` on purpose. The scorer opens exactly
three files and this is not one of them, so model prose is structurally unable
to reach `matches_key` -- a property of the layout rather than a rule someone
has to remember.
"""

import json

from artifacts.repo_path import is_repo_relative_posix

# Version 2 added `knowledge_base` and each entry's `sources`: the advice is
# grounded on retrieved passages, and both what grounded the run and which
# passages grounded each entry are recorded so a reader can open them.
SCHEMA_VERSION = 2
SOURCE_FIELDS = frozenset({"source", "path", "heading", "url"})
HTTPS = "https://"

WRITTEN = "written"
REJECTED = "rejected"
UNAVAILABLE = "unavailable"
ADVICE_STATUSES = (WRITTEN, REJECTED, UNAVAILABLE)

NAMES_APP_IDENTIFIER = "names_app_identifier"
SNIPPET_IS_A_DIFF = "snippet_is_a_diff"
RECLASSIFIES = "reclassifies_the_finding"
SNIPPET_TOO_LONG = "snippet_too_long"
GUIDANCE_TOO_LONG = "guidance_too_long"
CODE_FENCE_IN_GUIDANCE = "code_fence_in_guidance"
UNKNOWN_LANGUAGE = "unknown_snippet_language"
UNKNOWN_LABEL = "unknown_snippet_label"
EMPTY_ANSWER = "empty_answer"
MODEL_UNAVAILABLE = "model_unavailable"
MODEL_DISABLED = "model_disabled"
ADVICE_REASONS = (
    NAMES_APP_IDENTIFIER, SNIPPET_IS_A_DIFF, RECLASSIFIES, SNIPPET_TOO_LONG,
    GUIDANCE_TOO_LONG,
    CODE_FENCE_IN_GUIDANCE, UNKNOWN_LANGUAGE, UNKNOWN_LABEL, EMPTY_ANSWER,
    MODEL_UNAVAILABLE, MODEL_DISABLED,
)

# One value, because the prompt asks for one snippet and that snippet always
# shows the safer pattern. A second label was defined and never emitted; a
# vocabulary value no producer can write is one no reader can rely on.
SAFER_LABEL = "illustration_of_a_safer_pattern"
SNIPPET_LABELS = (SAFER_LABEL,)

# Where a passage grounding the advice may come from. One value today; the
# manifest, the index and every `sources` entry use this same name, so the
# files join on it. Defined here, with the rest of the vocabulary, because the
# retrieval modules import their vocabulary from the schema and never the
# other way round.
OWASP_CHEATSHEETS = "owasp-cheatsheets"
KNOWLEDGE_SOURCES = (OWASP_CHEATSHEETS,)

# Whether the advice was grounded on the knowledge base, and why not when it
# was not. The same shape as an advice entry's status and reason: a reader can
# tell "no index was built" from "the embedding server was down" by field.
KNOWLEDGE_INDEXED = "indexed"
KNOWLEDGE_NOT_INDEXED = "not_indexed"
KNOWLEDGE_STATUSES = (KNOWLEDGE_INDEXED, KNOWLEDGE_NOT_INDEXED)
NO_INDEX = "no_index"
INDEX_STALE = "index_stale"
EMBED_UNAVAILABLE = "embed_unavailable"
EMBED_MODEL_MISSING = "embed_model_missing"
KNOWLEDGE_REASONS = (NO_INDEX, INDEX_STALE, EMBED_UNAVAILABLE, EMBED_MODEL_MISSING)

# How many passages one finding's advice may be grounded on. The retriever
# takes its k from this, so the two can never disagree.
MAX_SOURCES_PER_FINDING = 3


def knowledge_provenance(status: str, reason: str | None = None,
                         embed_model: str | None = None, embed_model_digest: str | None = None,
                         manifest_digest: str | None = None, source_count: int = 0) -> dict:
    """Record what grounded the advice, refusing a pairing that claims too much or too little.

    Indexed needs the model and the manifest it read from, and no reason; not
    indexed needs a reason and may pin nothing -- the same two-way rule the
    findings document applies to its advisory snapshot.
    """
    if status not in KNOWLEDGE_STATUSES:
        raise ValueError(f"unknown knowledge status {status!r}; expected one of {KNOWLEDGE_STATUSES}")
    pins = (embed_model, manifest_digest)
    if status == KNOWLEDGE_INDEXED and (reason is not None or None in pins or source_count < 1):
        raise ValueError("an indexed run names its embed model and manifest digest, "
                         "counts at least one source, and gives no reason")
    if status == KNOWLEDGE_NOT_INDEXED and (reason not in KNOWLEDGE_REASONS or any(pins)
                                           or embed_model_digest or source_count):
        raise ValueError(f"an ungrounded run needs a reason from {KNOWLEDGE_REASONS} "
                         "and may pin nothing")
    return {
        "status": status, "reason": reason, "embed_model": embed_model,
        "embed_model_digest": embed_model_digest, "manifest_digest": manifest_digest,
        "source_count": source_count,
    }


def _check_source(source: dict) -> None:
    """Refuse an attribution a reader could not follow: wrong shape, source, path or link."""
    if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
        raise ValueError(f"a source carries exactly {sorted(SOURCE_FIELDS)}, got {source!r}")
    if source["source"] not in KNOWLEDGE_SOURCES:
        raise ValueError(f"unknown knowledge source {source['source']!r}; "
                         f"expected one of {KNOWLEDGE_SOURCES}")
    if not isinstance(source["path"], str) or not is_repo_relative_posix(source["path"]):
        raise ValueError(f"a source path is POSIX and relative to its clone, got {source['path']!r}")
    if source["heading"] is not None and not isinstance(source["heading"], str):
        raise ValueError(f"a source heading is text or null, got {source['heading']!r}")
    if not isinstance(source["url"], str) or not source["url"].startswith(HTTPS):
        raise ValueError(f"a source url is an {HTTPS} link to the upstream page, got {source['url']!r}")


def _check_sources(sources: list[dict]) -> None:
    """Sources are tool-written, so a bad one is a producer bug: every flaw raises."""
    if not isinstance(sources, list):
        raise ValueError(f"sources is a list of attributions, got {sources!r}")
    if len(sources) > MAX_SOURCES_PER_FINDING:
        raise ValueError(f"at most {MAX_SOURCES_PER_FINDING} sources per finding, got {len(sources)}")
    seen = set()
    for source in sources:
        _check_source(source)
        key = (source["source"], source["path"], source["heading"])
        if key in seen:
            raise ValueError(f"the same passage is cited twice: {key}")
        seen.add(key)


def advice_entry(finding_id: str, status: str, reason: str | None = None,
                 rejected_on: str | None = None, guidance: str | None = None,
                 snippets: list[dict] | None = None, sources: list[dict] | None = None) -> dict:
    """Build one advice record, refusing a combination a reader could not act on."""
    if status not in ADVICE_STATUSES:
        raise ValueError(f"unknown advice status {status!r}; expected one of {ADVICE_STATUSES}")
    if status != WRITTEN and reason not in ADVICE_REASONS:
        raise ValueError(f"{status} needs a reason from {ADVICE_REASONS}, got {reason!r}")
    if status == WRITTEN and reason is not None:
        raise ValueError("written advice carries no refusal reason")
    if status != WRITTEN and (guidance or snippets or sources):
        raise ValueError(f"{status} advice must carry no text; refusal is whole, not partial")
    _check_sources(sources or [])
    return {
        "finding_id": finding_id, "status": status, "reason": reason,
        "rejected_on": rejected_on,
        "guidance": guidance if status == WRITTEN else None,
        "snippets": list(snippets or []) if status == WRITTEN else [],
        # Injection order, never sorted: the prompt cited them in this order.
        "sources": [dict(source) for source in sources or []] if status == WRITTEN else [],
    }


def build_remediation_document(advice: list[dict], provenance: dict, knowledge: dict,
                               findings_schema_version: int) -> dict:
    """Assemble the remediation document, one entry per finding and none invented."""
    ordered = sorted(advice, key=lambda entry: entry["finding_id"])
    ids = [entry["finding_id"] for entry in ordered]
    if len(set(ids)) != len(ids):
        raise ValueError("two advice entries share a finding_id")
    if knowledge["status"] == KNOWLEDGE_NOT_INDEXED and any(
            entry["sources"] for entry in ordered):
        raise ValueError("no knowledge base was indexed, so no entry may cite a passage")
    return {
        "schema_version": SCHEMA_VERSION,
        "findings_schema_version": findings_schema_version,
        "model_run": provenance,
        # A sibling of model_run, not part of it: that block is shared with
        # findings.json and records the model; this one records the index.
        "knowledge_base": knowledge,
        "advice_count": len(ordered),
        # All three always present, so a reader never subtracts to find a zero.
        "status_counts": {status: sum(1 for entry in ordered if entry["status"] == status)
                          for status in ADVICE_STATUSES},
        "advice": ordered,
    }


def strip_advice_text(document: dict) -> dict:
    """Remove everything the model decided, leaving the skeleton a run must reproduce.

    The sibling of `strip_model_authored`. What survives is byte-identical
    across runs and across model families; what it removes is not, and no test
    should pretend otherwise.
    """
    stripped = json.loads(json.dumps(document))
    stripped.pop("status_counts", None)
    # `sources` go too: not model-authored, but carried only beside a written
    # answer, so their presence follows a field that is. `knowledge_base`
    # stays -- an index is an input, like a reachable server, and a run must
    # reproduce whether one was present.
    for entry in stripped["advice"]:
        for field in ("status", "reason", "rejected_on", "guidance", "snippets", "sources"):
            entry.pop(field, None)
    return stripped


def remediation_to_json(document: dict) -> str:
    """Serialise the remediation to its stable on-disk form."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"

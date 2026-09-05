"""Shared test data for model-written advice: one finding dict, and advice that passes.

`judge` and `advice_entry` are handed a *serialised* finding record rather than
the dataclass, so the fixture below is built through the real producer and then
copied. The clean guidance has to stay clean in four ways at once -- non-empty,
short, fence-free, and naming no foreign risk class -- and the clean snippet in
three more, so both are written once here instead of in every test file.
"""

from artifacts.findings_document import (
    MODEL_UNAVAILABLE,
    MODEL_USED,
    model_provenance,
)
from artifacts.remediation import (
    KNOWLEDGE_INDEXED,
    KNOWLEDGE_NOT_INDEXED,
    MODEL_UNAVAILABLE as ADVICE_UNAVAILABLE_REASON,
    NO_INDEX,
    OWASP_CHEATSHEETS,
    REJECTED,
    SAFER_LABEL,
    UNAVAILABLE,
    WRITTEN,
    advice_entry,
    build_remediation_document,
    knowledge_provenance,
)
from cli_helpers import STUB_MODEL_DIGEST
from findings_fixtures import build_document, static_finding
from parsing.languages import PYTHON

MODEL = "qwen2.5-coder:7b-instruct"
DECODE_SETTINGS = {"temperature": 0, "seed": 0}

# The findings.json this advice would have been written from. A pass-through
# literal, not an assertion: it had drifted from findings.json's own version
# and was corrected when this file gained the knowledge-base fixtures.
FINDINGS_SCHEMA_VERSION = 7

# One attribution in the shape `advice_entry` validates.
SOURCE_PATH = "cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.md"
SOURCE_URL = ("https://cheatsheetseries.owasp.org/cheatsheets/"
              "LLM_Prompt_Injection_Prevention_Cheat_Sheet.html")

# Prose a reader could act on that names nothing belonging to the audited app.
CLEAN_GUIDANCE = (
    "Treat the retrieved value as data rather than as instruction, and put every "
    "tool it can reach behind a check a person approved beforehand."
)

# Placeholder names only, no line in patch form, well under the volume caps.
CLEAN_CODE = "value = fetch_untrusted_text()\nchecked = approve(value)"


def finding_record(**overrides) -> dict:
    """Return one serialised finding, with any field overridden or added.

    Overrides are applied to the dict rather than the dataclass so a test can
    add `module`, which `EVIDENCE_FIELDS` reads and `Finding` does not carry.
    """
    record = build_document([static_finding()])["findings"][0]
    return {**record, **overrides}


def snippet(code: str = CLEAN_CODE, language: str = PYTHON,
            label: str = SAFER_LABEL) -> dict:
    """Build one illustration in the shape `judge` and the report both expect."""
    return {"label": label, "language": language, "code": code}


def used_run(digest: str | None = STUB_MODEL_DIGEST) -> dict:
    """Provenance for a run that reached the model server."""
    return model_provenance(MODEL_USED, MODEL, DECODE_SETTINGS, digest)


def unavailable_run() -> dict:
    """Provenance for a run that could not reach the model server."""
    return model_provenance(MODEL_UNAVAILABLE)


def source(path: str = SOURCE_PATH, heading: str | None = "Input Validation",
           url: str = SOURCE_URL) -> dict:
    """One passage attribution, in the shape an entry records."""
    return {"source": OWASP_CHEATSHEETS, "path": path, "heading": heading, "url": url}


def indexed_knowledge(source_count: int = 1) -> dict:
    """Provenance for a run that retrieved from a built index.

    The two digests are shaped as their producers really write them: the embed
    model's is bare hex, because that is what Ollama's tag listing reports, and
    the manifest's carries `retrieval.manifest.DIGEST_PREFIX`, because that
    module prepends it.
    """
    return knowledge_provenance(KNOWLEDGE_INDEXED, None, "nomic-embed-text",
                                "0" * 64, f"sha256:{'1' * 64}", source_count)


def no_knowledge(reason: str = NO_INDEX) -> dict:
    """Provenance for a run with no knowledge base to retrieve from."""
    return knowledge_provenance(KNOWLEDGE_NOT_INDEXED, reason)


def written_entry(finding_id: str, guidance: str = CLEAN_GUIDANCE,
                  snippets: list[dict] | None = None,
                  sources: list[dict] | None = None) -> dict:
    """One entry whose advice survived the contract."""
    return advice_entry(finding_id, WRITTEN, guidance=guidance,
                        snippets=snippets if snippets is not None else [snippet()],
                        sources=sources)


def rejected_entry(finding_id: str, reason: str, rejected_on: str = "code") -> dict:
    """One entry the model answered and the contract refused."""
    return advice_entry(finding_id, REJECTED, reason, rejected_on)


def unavailable_entry(finding_id: str) -> dict:
    """One entry no model was ever asked about."""
    return advice_entry(finding_id, UNAVAILABLE, ADVICE_UNAVAILABLE_REASON)


def remediation_document(entries: list[dict], provenance: dict | None = None,
                         knowledge: dict | None = None) -> dict:
    """Assemble a remediation document through its real producer.

    The knowledge block follows the entries when a caller does not name one:
    the producer refuses a document whose entries cite passages no index was
    open for, so a test that adds `sources` should not also have to remember to
    say so twice.
    """
    if knowledge is None:
        knowledge = (indexed_knowledge() if any(entry["sources"] for entry in entries)
                     else no_knowledge())
    return build_remediation_document(
        entries, provenance if provenance is not None else used_run(),
        knowledge, FINDINGS_SCHEMA_VERSION)

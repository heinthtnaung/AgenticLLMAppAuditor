"""Builds `remediation.json`: the advice a model gave on each finding.

Split out of `outputs.py`, which was writing artifacts *and* making the only
model call an audit makes. That call is the interesting thing here and it was
buried among file I/O.

**The audit's one model call, and its degradations.** A model that cannot be
reached degrades the artifact rather than failing the run, exactly as a missing
Syft yields no bill of materials. The knowledge base degrades separately and is
probed once, because an unreachable model and an unbuilt index are two different
absences and the document records each on its own block.

Not in `artifacts/`, though it authors an artifact: it composes `checks.advise`
and `retrieval.retrieve`, both of which import `artifacts`, so putting it there
would point the dependency backwards.
"""

from collections import Counter

from artifacts.findings_document import MODEL_UNAVAILABLE, MODEL_USED, model_provenance
from artifacts.remediation import (
    MODEL_UNAVAILABLE as ADVICE_UNAVAILABLE_REASON,
    UNAVAILABLE,
    advice_entry,
    build_remediation_document,
    remediation_to_json,
)
from artifacts.surface import Surface
from checks import advise
from parsing.languages import PYTHON
from retrieval import retrieve
import config
import model_client


def declared_language(surfaces: list[Surface]) -> str:
    """Say which language this app is mostly written in, for a snippet's fence."""
    counted = Counter(surface.language for surface in surfaces)
    return counted.most_common(1)[0][0] if counted else PYTHON


def _unreachable_advice(findings: list[dict]) -> tuple[list[dict], dict]:
    """Record one entry per finding when no model answered, and say so once."""
    entries = [advice_entry(finding["finding_id"], UNAVAILABLE, ADVICE_UNAVAILABLE_REASON)
               for finding in findings]
    return entries, model_provenance(MODEL_UNAVAILABLE)


def _advice_with_provenance(findings: list[dict], language: str,
                            module_names: tuple[str, ...],
                            passages_for: advise.Retriever,
                            advisor: dict | None) -> tuple[list[dict], dict]:
    """Advise with the named model, or the local one, recording whichever answered."""
    if advisor is None:
        digest = model_client.model_digest()
        entries = advise.advise_all(findings, language, module_names, passages_for)
        return entries, model_provenance(
            MODEL_USED, model_client.MODEL, model_client.DECODE_SETTINGS, digest)
    entries = advise.advise_all(findings, language, module_names, passages_for,
                                advisor["ask"])
    if not entries or _nothing_answered(entries):
        # `advise_one` swallows the per-finding RuntimeError, so an unreachable
        # advisor otherwise reaches here looking like a model that answered and
        # gets recorded as `used` -- while every entry beneath it says
        # `model_unavailable`. Raising hands it to the caller's existing
        # degradation path, so remediation.json agrees with findings.json
        # instead of contradicting it. The local branch is spared this because
        # `model_digest` probes reachability before any advice is asked for.
        # `not entries` too: with no findings nothing was asked, and the local
        # branch may claim `used` there only because `model_digest` proved the
        # server was up. An advisor has no such probe, so claiming it would be
        # a provenance record of a call that never happened.
        raise RuntimeError(f"{advisor['identifier']} answered no finding")
    return entries, model_provenance(
        MODEL_USED, advisor["identifier"], advisor["settings"], advisor.get("digest"))


def _nothing_answered(entries: list[dict]) -> bool:
    """True when there were entries and every one of them says the model was unreachable."""
    return bool(entries) and all(
        entry["status"] == UNAVAILABLE and entry.get("reason") == ADVICE_UNAVAILABLE_REASON
        for entry in entries)


def build_remediation(findings_document: dict, language: str,
                      module_names: tuple[str, ...],
                      advisor: dict | None = None) -> str:
    """Ask the model to advise on every finding, and record what it said or did not.

    A model that cannot be reached degrades the artifact rather than failing the
    audit: producing less is a normal outcome here, exactly as a missing Syft
    yields no bill of materials. The knowledge base degrades separately and is
    probed once for the whole run -- an unreachable model and an unbuilt index
    are two different absences, and the artifact records each on its own block.

    `advisor` names a different model and the call that reaches it, as
    `build_findings` takes `probe_model`. Absent -- every ordinary audit -- the
    local client answers and records itself. It exists so the cloud arm of
    `--compare-models` cannot write the local model's identifier into an
    artifact a hosted model produced.
    """
    findings = findings_document["findings"]
    # Probed before the findings are looked at, so an app with nothing found
    # still records whether an index was there. `knowledge_base` describes the
    # run's inputs, not its output: "indexed, and no entries" is a fact worth
    # having, and it costs one embed call that `advise_all([])` would not make.
    grounding = retrieve.probe(config.get_path("AUDITOR_KNOWLEDGE_DIR"))
    try:
        entries, provenance = _advice_with_provenance(
            findings, language, module_names, grounding.passages_for, advisor)
    except RuntimeError:
        entries, provenance = _unreachable_advice(findings)
    document = build_remediation_document(
        entries, provenance, grounding.knowledge, findings_document["schema_version"])
    return remediation_to_json(document)

"""How a council run's local models were asked, in the audit record: pinning, server and weights.

Every setting the run was asked with, then which server answered and which
weights: `ollama_version` once, and a digest per model the run asks, member or
escalation. Each is known, or it says why not, as `advisory_database` does.
"""

from typing import Any

from report.model_identity import ModelDigest, ModelIdentity, OllamaVersion, ServerVersion
from report.provenance import LocalModels


def local_models_of(local: LocalModels | None) -> dict[str, Any] | None:
    """Give how the run's local models were asked, or null where no council ran."""
    if local is None:
        return None
    return {
        "server": local.server,
        "context_tokens": local.context_tokens,
        "timeout_seconds": local.timeout_seconds,
        "temperature": local.temperature,
        "seed": local.seed,
        "think": local.think,
        "order_check": local.order_check,
        "escalation_model": local.escalation_model,
        "ollama_version": version_of(local.ollama_version),
        "models": [model_of(one) for one in local.models],
    }


def version_of(version: ServerVersion) -> dict[str, Any]:
    """Give the server's version, or say plainly that none could be read, and why."""
    if isinstance(version, OllamaVersion):
        return {"version": version.version, "known": True}
    return {"known": False, "reason": version.reason}


def model_of(model: ModelIdentity) -> dict[str, Any]:
    """Give one model the run asks, as what, and the digest of its weights or why it is unknown."""
    named = {"model": model.model, "role": model.role}
    if isinstance(model, ModelDigest):
        return {**named, "digest": model.digest, "known": True}
    return {**named, "known": False, "reason": model.reason}

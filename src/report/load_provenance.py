"""Reading a saved report's `run` block back into the provenance a run recorded.

The inverse of `report.json_report.run_of`, `report.json_risk`'s database view and
`report.json_local_models`: every field the record carries is read back, and a
block of the wrong shape is refused where it sits. The derived counts beside the
provenance (`finding_count` and the rest) are recomputed by the renderers, so
nothing here reads them.
"""

from typing import Any, Mapping

from report.load_json import (
    ReportJsonFault,
    require,
    required_list,
    required_number,
    required_object,
)
from report.model_identity import (
    ModelDigest,
    ModelIdentity,
    OllamaVersion,
    ServerVersion,
    UnknownDigest,
    UnknownOllamaVersion,
)
from report.provenance import (
    AdvisoryDatabase,
    Database,
    LocalModels,
    RunProvenance,
    UnknownAdvisoryDatabase,
)

RUN = "run"


def provenance_from(document: Mapping[str, Any]) -> RunProvenance:
    """Read the `run` block back into the provenance the run recorded."""
    run = required_object(document, RUN, "report")
    return RunProvenance(
        repository=str(require(run, "repository", RUN)),
        syft_version=str(require(run, "syft_version", RUN)),
        trivy_version=str(require(run, "trivy_version", RUN)),
        database=database_from(required_object(run, "advisory_database", RUN)),
        local_models=local_models_from(run.get("local_models")),
        scoring_rules_version=str(require(run, "scoring_rules_version", RUN)),
        answers_source=str(run.get("answers_source") or ""),
    )


def component_count_from(document: Mapping[str, Any]) -> int:
    """Read the number of components the run catalogued, which the record keeps in `run`."""
    run = required_object(document, RUN, "report")
    count = require(run, "component_count", RUN)
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ReportJsonFault(f"run.component_count must be a non-negative integer, not {count!r}")
    return count


def database_from(block: Mapping[str, Any]) -> Database:
    """Read the advisory database back as its build date, or as the reason none was read."""
    if block.get("known"):
        return AdvisoryDatabase(built_at=str(require(block, "built_at", "run.advisory_database")))
    return UnknownAdvisoryDatabase(reason=str(require(block, "reason", "run.advisory_database")))


def local_models_from(block: Any) -> LocalModels | None:
    """Read how the council's local models were asked, or none where no council ran."""
    if block is None:
        return None
    where = "run.local_models"
    models = [model_from(one) for one in required_list(block, "models", where)]
    return LocalModels(
        server=str(require(block, "server", where)),
        context_tokens=required_number(block, "context_tokens", where),
        timeout_seconds=required_number(block, "timeout_seconds", where),
        temperature=required_number(block, "temperature", where),
        seed=required_number(block, "seed", where),
        think=bool(require(block, "think", where)),
        order_check=bool(require(block, "order_check", where)),
        escalation_model=block.get("escalation_model"),
        ollama_version=version_from(required_object(block, "ollama_version", where)),
        models=tuple(models),
        remote_host=str(block.get("remote_host") or ""),
    )


def version_from(block: Mapping[str, Any]) -> ServerVersion:
    """Read the model server's version, or the reason none could be read."""
    where = "run.local_models.ollama_version"
    if block.get("known"):
        return OllamaVersion(version=str(require(block, "version", where)))
    return UnknownOllamaVersion(reason=str(require(block, "reason", where)))


def model_from(block: Mapping[str, Any]) -> ModelIdentity:
    """Read one model the run asked: its weights' digest, or the reason none was known."""
    where = "run.local_models.models"
    named = (str(require(block, "model", where)), str(require(block, "role", where)))
    if block.get("known"):
        return ModelDigest(*named, digest=str(require(block, "digest", where)))
    return UnknownDigest(*named, reason=str(require(block, "reason", where)))

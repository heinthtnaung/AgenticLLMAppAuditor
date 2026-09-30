"""What produced a run, and whether there was a database there to produce it from.

The advisory database's build date is its own type when it is missing, because
Trivy with no database finds nothing and exits 0 -- so "unknown" here is the
difference between a clean repository and a report that means nothing, and a
blank field would read as the former.

Every field is asked of the tool rather than configured. A provenance somebody
types is a claim nobody checked, and the one purpose of these fields is that a
run is checkable. The one exception is how local members were asked: the window
and timeout are the operator's settings, and can change a result, so the record
states the ones the run used beside the three pinned in code.

The scoring rules' version is not asked of a tool either: it is this code's own,
from `scoring.version`, and it is the default because no run scores by any other.
"""

from dataclasses import dataclass

from report.model_identity import ModelIdentity, ServerVersion
from scoring.version import SCORING_RULES_VERSION

# How both pages name the version, so the two cannot drift.
SCORING_RULES_LABEL = "scoring rules"

@dataclass(frozen=True)
class AdvisoryDatabase:
    """The advisory database this scan joined against, by its own build date."""

    built_at: str

    def __post_init__(self) -> None:
        """Refuse a database that names no build date, which is the same as none at all."""
        if not self.built_at.strip():
            raise ValueError("An advisory database must give the date it was built")


@dataclass(frozen=True)
class UnknownAdvisoryDatabase:
    """No build date could be read, so nothing says this scan saw a database at all."""

    reason: str

    def __post_init__(self) -> None:
        """Refuse an unexplained absence of the one check against a silent clean report."""
        if not self.reason:
            raise ValueError("A missing database date must say why it is missing")


Database = AdvisoryDatabase | UnknownAdvisoryDatabase


@dataclass(frozen=True)
class LocalModels:
    """How every local member of the run was asked: server, window, timeout, pinning and orders.

    `order_check` says each metric was asked with the options in order and
    reversed, a value counting only where both gave it. `escalation_model` names
    the local model the metrics the council left open were sent to, and is None
    where `AUDITOR_ESCALATION_MODEL` named none, so nothing was escalated.
    `ollama_version` and `models` say which server and which weights answered
    (`report.model_identity`): a tag names weights only until it is re-pointed.
    """

    server: str
    context_tokens: int
    timeout_seconds: float
    temperature: float
    seed: int
    think: bool
    order_check: bool
    escalation_model: str | None
    ollama_version: ServerVersion
    models: tuple[ModelIdentity, ...]

    def __post_init__(self) -> None:
        """Refuse a record of a council that asked no model, which no real run is."""
        if not self.models:
            raise ValueError("A council run asks at least one model; models cannot be empty")


@dataclass(frozen=True)
class RunProvenance:
    """What produced this report, so a reader can judge whether to believe it.

    `local_models` is None only for a run that named no council member, which
    asked no local model anything.
    """

    repository: str
    syft_version: str
    trivy_version: str
    database: Database
    local_models: LocalModels | None = None
    scoring_rules_version: str = SCORING_RULES_VERSION

    def __post_init__(self) -> None:
        """Refuse provenance a reader could not reproduce the run from."""
        missing = [
            name
            for name in ("repository", "syft_version", "trivy_version", "scoring_rules_version")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"A run's provenance needs {', '.join(missing)}")
        if not isinstance(self.database, (AdvisoryDatabase, UnknownAdvisoryDatabase)):
            raise TypeError(f"A run needs a database, not {type(self.database).__name__}")

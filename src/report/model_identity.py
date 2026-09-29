"""Which weights answered and which server: each local model's digest, and Ollama's version.

A tag such as `gemma4:latest` is a name the server can re-point: pulling again,
or an operator switching models, changes the weights behind it without changing
a word of the record. The digest the server holds is what names the weights, so
a council run records it for every model it asks, and the server's version once.

Each is known or it is not, and a type says which, as the advisory database's
build date does (`report.provenance`): an unknown digest keeps the reason the
server gave none, and is never filled in with a guess.
"""

from dataclasses import dataclass

MEMBER_ROLE = "member"
ESCALATION_ROLE = "escalation"


@dataclass(frozen=True)
class ModelDigest:
    """The digest the server holds for one model the run asks, and what the run asks it as."""

    model: str
    role: str
    digest: str

    def __post_init__(self) -> None:
        """Refuse a digest that names no model or no weights."""
        if not self.model or not self.digest:
            raise ValueError("A model digest must name the model and its digest")


@dataclass(frozen=True)
class UnknownDigest:
    """A model the run asks whose digest the server did not give, and why."""

    model: str
    role: str
    reason: str

    def __post_init__(self) -> None:
        """Refuse an unexplained absence of the one thing that names the weights."""
        if not self.model or not self.reason:
            raise ValueError("An unknown digest must name the model and say why it is unknown")


@dataclass(frozen=True)
class OllamaVersion:
    """The version the local model server reports of itself."""

    version: str

    def __post_init__(self) -> None:
        """Refuse a version that names nothing, which is the same as none at all."""
        if not self.version.strip():
            raise ValueError("An Ollama version must say what it is")


@dataclass(frozen=True)
class UnknownOllamaVersion:
    """No version could be read from the server, and why."""

    reason: str

    def __post_init__(self) -> None:
        """Refuse an unexplained absence."""
        if not self.reason:
            raise ValueError("An unknown Ollama version must say why it is unknown")


ModelIdentity = ModelDigest | UnknownDigest
ServerVersion = OllamaVersion | UnknownOllamaVersion

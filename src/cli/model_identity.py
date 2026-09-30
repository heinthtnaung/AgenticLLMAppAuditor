"""Reading which weights and which server a council run uses, into the record.

Two requests, once per run and only when a council is asked for: the server's
models with their digests (`/api/tags`) and its version (`/api/version`),
through the same no-proxy client every call uses (`council.transport.get_json`),
at the settings' server, which `council.settings` holds to loopback unless
`AUDITOR_REMOTE_SERVER=yes` let it name another machine. Every
model the run asks is looked up -- the members, and the escalation model where
one is named; the explainer is always one of those.

Both reads wait `READ_TIMEOUT_SECONDS`, not the generation timeout: they come
before the scan, and a server that has hung should not hold the audit for
minutes over two lines of the record.

**What the server does not say is recorded as not said, with why.** A server
that cannot be reached, a reply of the wrong shape, or a model it does not list
or lists without a digest gives an unknown digest or version, never a guessed
one, and never stops the audit: the members' calls would fail on their own if
the server were gone.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from council.transport import ModelUnavailable
from report.model_identity import (
    ESCALATION_ROLE,
    MEMBER_ROLE,
    ModelDigest,
    ModelIdentity,
    OllamaVersion,
    ServerVersion,
    UnknownDigest,
    UnknownOllamaVersion,
)

TAGS_PATH = "/api/tags"
VERSION_PATH = "/api/version"
VERSION_FIELD = "version"
MODELS_FIELD = "models"
NAME_FIELD = "name"
DIGEST_FIELD = "digest"
# Ample for two small documents from this machine, and far short of a generation.
READ_TIMEOUT_SECONDS = 30.0
# The tag Ollama assumes when a name carries none, as `llama3.2` for `llama3.2:latest`.
DEFAULT_TAG = ":latest"
TAG_SEPARATOR = ":"
# A tag is only ever in the last part of a path: in `myregistry:5000/model` the
# ":" is the registry's port, and the name carries no tag.
PATH_SEPARATOR = "/"


class Read(Protocol):
    """Read one JSON document from a URL, waiting no longer than the timeout."""

    def __call__(self, url: str, timeout: float) -> Any:
        """Give back the parsed document, or raise saying why none came."""


@dataclass(frozen=True)
class Listing:
    """Every model the server lists by name and the digest of each that gives one, or why not."""

    names: frozenset[str] = frozenset()
    digests: Mapping[str, str] = field(default_factory=dict)
    unread: str = ""


def local_identities(
    members: tuple[str, ...], escalation: str | None, host: str, get: Read
) -> tuple[ServerVersion, tuple[ModelIdentity, ...]]:
    """Give the server's version and the digest of every model the run asks, or why not."""
    asked = [(one, MEMBER_ROLE) for one in members]
    if escalation is not None:
        asked.append((escalation, ESCALATION_ROLE))
    listing = listing_of(host, get)
    return server_version(host, get), tuple(identity_of(*one, listing) for one in asked)


def server_version(host: str, get: Read) -> ServerVersion:
    """Give the version the server reports, or why none could be read."""
    url = f"{host}{VERSION_PATH}"
    try:
        reply = get(url, timeout=READ_TIMEOUT_SECONDS)
    except (ModelUnavailable, ValueError) as fault:
        return UnknownOllamaVersion(f"no version could be read: {fault}")
    version = reply.get(VERSION_FIELD) if isinstance(reply, Mapping) else None
    if not isinstance(version, str) or not version.strip():
        return UnknownOllamaVersion(f"{url} answered without a version")
    return OllamaVersion(version.strip())


def listing_of(host: str, get: Read) -> Listing:
    """Read the models the server holds and their digests, or why the list could not be read."""
    url = f"{host}{TAGS_PATH}"
    try:
        reply = get(url, timeout=READ_TIMEOUT_SECONDS)
    except (ModelUnavailable, ValueError) as fault:
        return Listing(unread=f"no list of models could be read: {fault}")
    models = reply.get(MODELS_FIELD) if isinstance(reply, Mapping) else None
    if not isinstance(models, list):
        return Listing(unread=f"{url} answered without a list of models")
    named = [one for one in models if gives_text(one, NAME_FIELD)]
    digested = [one for one in named if gives_text(one, DIGEST_FIELD)]
    return Listing(
        names=frozenset(one[NAME_FIELD] for one in named),
        digests={one[NAME_FIELD]: one[DIGEST_FIELD] for one in digested},
    )


def gives_text(entry: Any, name: str) -> bool:
    """Say whether one entry of the list gives this field as text that is not empty."""
    if not isinstance(entry, Mapping):
        return False
    return isinstance(entry.get(name), str) and bool(entry[name])


def identity_of(model: str, role: str, listing: Listing) -> ModelIdentity:
    """Give one model's digest from the server's list, or why the list does not give it."""
    if listing.unread:
        return UnknownDigest(model, role, listing.unread)
    listed_as = tagged(model)
    if listed_as in listing.digests:
        return ModelDigest(model, role, listing.digests[listed_as])
    if listed_as in listing.names:
        return UnknownDigest(model, role, f"the server lists {model} without a digest")
    return UnknownDigest(model, role, f"the server lists no model named {model}")


def tagged(model: str) -> str:
    """Name a model as the server lists it, with the tag Ollama assumes where it has none."""
    last_part = model.rsplit(PATH_SEPARATOR, 1)[-1]
    return model if TAG_SEPARATOR in last_part else f"{model}{DEFAULT_TAG}"

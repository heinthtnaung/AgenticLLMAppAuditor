"""Whether the local model server is up, and which models it holds.

Asked through `src/model_client.py`, never with a socket of this module's own.
That module is the one place in `src/` that talks to Ollama and it already
parses `/api/tags` for `model_digest`; a second parse here would be two copies
of one format, and a `urllib` call in `web/` would make "two modules in `src/`
open a connection" harder to state than it is worth.

**Unreachable is an answer, not a failure.** The reply is 200 either way: this
server answered, the *model* server did not, and that is what the body is about.
A 503 would be swallowed by the page's error path, which keeps only `detail` --
turning a stopped model server into a generic failure, which is the gap-as-noise
this body exists to prevent.
"""

from fastapi import FastAPI

import model_client
import run_record

# Named rather than a literal in the route: the reply says what could not be
# established, and "not knowable" is a different answer from "no".
UNKNOWABLE = None


def register(app: FastAPI) -> None:
    """Attach the model-status route to an application."""

    @app.get("/api/model")
    def model_status() -> dict:
        """What the local model server is holding, or why it could not be asked."""
        try:
            pulled = model_client.list_models()
        except RuntimeError as unreachable:
            return _body(reachable=False, error=str(unreachable), models=None)
        return _body(reachable=True, error=None, models=_named(pulled))


def _body(*, reachable: bool, error: str | None, models: list[dict] | None) -> dict:
    """One status reply, with what is knowable only when the server answered.

    `models` is null when the server could not be asked and `[]` when it
    answered and holds nothing -- two different facts, and collapsing them is
    the whole reason this field is nullable. The same rule `findings: null`
    carries against `findings: []`.
    """
    held = {model["name"] for model in models} if models is not None else set()
    return {
        "schema_version": run_record.REPLY_SCHEMA_VERSION,
        "reachable": reachable,
        "error": error,
        "models": models,
        "configured_model": model_client.MODEL,
        # Not knowable without asking, so null rather than false: a configured
        # model that is not pulled raises mid-run, after the tree is cloned, and
        # saying "not pulled" when nobody could look would be the same gap
        # rendered as a result.
        "configured_model_pulled": (model_client.MODEL in held) if models is not None else UNKNOWABLE,
        "embed_model": model_client.EMBED_MODEL,
        "embed_model_pulled": (model_client.EMBED_MODEL in held) if models is not None else UNKNOWABLE,
    }


def _named(pulled: list[dict]) -> list[dict]:
    """The listing reduced to what the page shows, sorted so it does not jump.

    Every entry is an object here because `list_models` refuses a listing where
    one is not -- a filter at this end would answer `[]` for a server that holds
    models, collapsing "holds nothing" into "could not be read".
    """
    return sorted(
        ({"name": model.get("name"), "digest": model.get("digest"),
          "bytes": model.get("size")} for model in pulled),
        key=lambda model: model["name"] or "")

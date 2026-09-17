"""Where a drafted grading key lives on disk, and the three ways to touch it.

Split from the routes because two route modules need it -- correcting a draft
and signing one off are different acts with different rules, so they are
different files -- and a second copy of "which file is this app's draft" is how
one of them ends up reading `grading_keys/` instead of `grading_keys/drafts/`.

**Drafts only, and that is the whole security argument.** `grading_keys/` holds
the answers this tool is scored against; an unauthenticated endpoint that could
rewrite them would let anyone who reaches the port rewrite the project's own
measurements. `DRAFTED_KEYS_DIR` is joined here and nowhere else -- including
the listing, which lived in the routes until a second binding of this constant
left a test fixture redirecting one of the two and writing through the other --
and `discover_graded_apps` globs one level, so a draft is invisible to scoring
until `promote_key.py` publishes it.
"""

import json
import re
from pathlib import Path

from fastapi import HTTPException

from keys import key_promotion
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path
from keys.key_drafting import DRAFTED_KEYS_DIR

# `<app>` reaches a filesystem join, so it is checked rather than trusted --
# the same rule the run routes apply to a run id.
APP_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

NO_SUCH_DRAFT = 404
REFUSED = 400


def path_for(app_name: str) -> Path:
    """Where this app's draft lives, refusing a name that is not one."""
    if not APP_NAME.match(app_name):
        raise HTTPException(status_code=NO_SUCH_DRAFT, detail="no draft has that name")
    return key_path(app_name, GROUND_TRUTH_SUFFIX, DRAFTED_KEYS_DIR)


def _json_object(path: Path) -> dict:
    """One hand-editable json object from disk, naming a corrupt file rather than crashing.

    **Two failures, not one.** Unreadable json is the obvious half; *readable
    json that is not an object* is the half that got through twice, because
    every caller goes straight to `.get()` or a subscript and a three-byte `[]`
    reaches them as a list -- a 500 with a traceback where the file is the thing
    at fault. Both files this store touches are hand-edited by design: a human
    corrects the key, and `key_promotion.GRADED_PIN_FIELDS` says a human types
    the manifest's framework and language.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    # `OSError` beside the parse error: a file that cannot be *opened* is as
    # hand-reachable as one that will not parse -- permissions, or a directory
    # where a file should be -- and it was a 500 while the parse error was a
    # named 400. Same fault, one `except` clause apart.
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=REFUSED,
            detail=f"{path.name} cannot be read as json: {error}. A hand edit "
                   "left it broken; fix the file before this page can use it.") from error
    if not isinstance(document, dict):
        raise HTTPException(
            status_code=REFUSED,
            detail=f"{path.name} holds {type(document).__name__}, not a json object. "
                   "A hand edit left it valid json and the wrong shape; fix the file "
                   "before this page can use it.")
    return document


def read(app_name: str) -> dict:
    """One drafted key from disk, naming a corrupt one rather than crashing on it."""
    path = path_for(app_name)
    if not path.is_file():
        raise HTTPException(status_code=NO_SUCH_DRAFT,
                            detail=f"no drafted key for {app_name}")
    return _json_object(path)


def drafted_apps() -> list[str]:
    """Every app with a draft on disk, by name. Empty when the folder is absent.

    `is_file()` because a *directory* named like a key would otherwise be
    listed as a draft -- the same filter, and the same reason, as
    `grading_keys.discover_graded_apps`.
    """
    if not DRAFTED_KEYS_DIR.is_dir():
        return []
    return sorted(path.name.removesuffix(GROUND_TRUTH_SUFFIX)
                  for path in DRAFTED_KEYS_DIR.glob(f"*{GROUND_TRUTH_SUFFIX}")
                  if path.is_file())


def write(app_name: str, key: dict) -> None:
    """Put one draft back on disk, sorted so two revisions can be diffed."""
    path_for(app_name).write_text(
        json.dumps(key, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(app_name: str, key: dict) -> list[str]:
    """What promotion would say about this draft, asked of promotion itself.

    Reuse, never a second validator: a key this editor accepted and promotion
    refused is the worst of both. It is *reported*, not enforced -- most of what
    it refuses concerns the manifest, which names a framework and a language
    that are human judgements a draft cannot supply and this page cannot edit,
    so gating on those would make a draft impossible to correct at all.
    """
    pin_path = key_path(app_name, MANIFEST_SUFFIX, DRAFTED_KEYS_DIR)
    # Guarded like the key, because it is hand-edited like the key. An absent
    # pin is an ordinary draft and answers `{}`; a *broken* one is a named
    # refusal, not a traceback out of `_pin_refusals` subscripting a list.
    pin = _json_object(pin_path) if pin_path.is_file() else {}
    return key_promotion.refusals(key, pin)

"""Where a drafted grading key lives on disk, and the three ways to touch it.

Split from the routes because two route modules need it -- correcting a draft
and signing one off are different acts with different rules, so they are
different files -- and a second copy of "which file is this app's draft" is how
one of them ends up reading the wrong folder.

**The folder is a parameter now, and it is always a run's own.** This module
used to join `keys.key_drafting.DRAFTED_KEYS_DIR` -- `grading_keys/drafts/` in
the checkout -- and that was wrong in both directions at once. A run started
from the browser drafts into `artifacts/runs/<run_id>/keys/`, which
`web/run_jobs.py` passes as `--drafts-dir` so a forgotten run takes its key with
it; so the editor could never see the key the server had just written, and every
`GET` for one answered 404. Meanwhile a save would have written into the
checkout's own drafts folder, where a human's corrected keys live.

`web/key_scope.py` is the one place a run id becomes a folder, and it can only
answer with `run_files.run_keys(...)`. So the security argument is stronger than
the one it replaces rather than merely moved: **no route here can name a path
outside `artifacts/runs/`.** `grading_keys/` holds the answers this tool is
scored against, and an unauthenticated endpoint that could rewrite those would
let anyone who reaches the port rewrite the project's own measurements. It is
now unreachable from this server at all, not merely one directory away.

A draft stays invisible to scoring until `promote_key.py` publishes it, which
for a run-scoped draft means `promote_key.py <app> --drafts-dir
artifacts/runs/<run_id>/keys`.
"""

import json
import re
from pathlib import Path

from fastapi import HTTPException

from keys import key_promotion
from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path

# `<app>` reaches a filesystem join, so it is checked rather than trusted --
# the same rule the run routes apply to a run id.
APP_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

NO_SUCH_DRAFT = 404
REFUSED = 400


def path_for(keys_dir: Path, app_name: str) -> Path:
    """Where this run's draft lives, refusing an app name that is not one.

    The name comes from the run record rather than from a caller, so this check
    is defence in depth -- but it is the join that would reach the filesystem
    with it, so it is checked here anyway.
    """
    if not APP_NAME.match(app_name):
        raise HTTPException(status_code=NO_SUCH_DRAFT, detail="no draft has that name")
    return key_path(app_name, GROUND_TRUTH_SUFFIX, keys_dir)


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


def read(keys_dir: Path, app_name: str) -> dict:
    """One drafted key from disk, naming a corrupt one rather than crashing on it.

    A run that never drafted one is the ordinary case -- `--draft-key` is off by
    default -- so this 404 is an absence and not a fault.
    """
    path = path_for(keys_dir, app_name)
    if not path.is_file():
        raise HTTPException(status_code=NO_SUCH_DRAFT,
                            detail=f"no drafted key for {app_name}. A key is "
                                   "drafted only when a run asks for one.")
    return _json_object(path)


def write(keys_dir: Path, app_name: str, key: dict) -> None:
    """Put one draft back on disk, sorted so two revisions can be diffed."""
    path_for(keys_dir, app_name).write_text(
        json.dumps(key, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(keys_dir: Path, app_name: str, key: dict) -> list[str]:
    """What promotion would say about this draft, asked of promotion itself.

    Reuse, never a second validator: a key this editor accepted and promotion
    refused is the worst of both. It is *reported*, not enforced -- most of what
    it refuses concerns the manifest, which names a framework and a language
    that are human judgements a draft cannot supply and this page cannot edit,
    so gating on those would make a draft impossible to correct at all.
    """
    pin_path = key_path(app_name, MANIFEST_SUFFIX, keys_dir)
    # Guarded like the key, because it is hand-edited like the key. An absent
    # pin is an ordinary draft and answers `{}`; a *broken* one is a named
    # refusal, not a traceback out of `_pin_refusals` subscripting a list.
    pin = _json_object(pin_path) if pin_path.is_file() else {}
    return key_promotion.refusals(key, pin)

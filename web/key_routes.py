"""Reading and correcting a drafted grading key, and nothing else.

**Addressed by run, not by app.** A run drafts its key into its own folder --
`web/run_jobs.py` passes `--drafts-dir artifacts/runs/<run_id>/keys` so a
forgotten run takes its key with it -- and these routes used to read
`grading_keys/drafts/` in the checkout instead. The two never met: the editor
answered 404 for every key this server had written, and would have saved into
the folder holding a human's own corrected drafts. `key_scope` is the join now,
and the app name comes off the record rather than out of the URL.

**Drafts only.** The folder is resolved in `key_scope`, which says why; nothing
here can name a published key, or any path outside `artifacts/runs/`.

**An edit never upgrades a key's standing, and `source` never moves at all.** A
drafted key stays `tool_drafted` however much of it a person corrects, and
promotion leaves that alone too, because `key_drafted_by_scored_system` is about
*validity, not quality*: a human checking every entry has checked the entries,
and has not made the tool's own choice of what to include independent of the
tool.

**`verified` is the one field a human can move, and it moves somewhere else.**
`key_verify_route` holds `POST /api/keys/{app}/verify` and the reasoning for
keeping it apart from a save; `api.py` mounts it beside this module, so the one
route that writes `verified` is visible to a reader auditing what this server
exposes. Every identity field stays frozen here, so this module cannot move
either half of the pair.

**Validation is `key_promotion.refusals`, never a second copy** -- reached
through `key_draft_store.validate`, and reported rather than enforced, for the
reason recorded there. What this module refuses outright is the two things an
edit must never do: move the key's standing, and invent an anchor.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import key_draft_store as store
import key_scope
from history_store import HistoryStore
from key_edit_guard import (
    FROZEN_FIELDS, anchors_moved, entries_malformed, frozen_moved, settled)


class DraftEdit(BaseModel):
    """The corrected key a person is saving."""

    key: dict


def register(app: FastAPI, history: HistoryStore) -> None:
    """Attach the reading and correcting routes. `api.py` mounts the verify route."""

    @app.get("/api/runs/{run_id}/key")
    def one_draft(run_id: str) -> dict:
        """One run's drafted key, with what an edit may not touch named beside it."""
        keys_dir, app_name = key_scope.for_run(history, run_id)
        held = store.read(keys_dir, app_name)
        return {"app": app_name, "key": held,
                "frozen_fields": list(FROZEN_FIELDS),
                "refusals": store.validate(keys_dir, app_name, held)}

    @app.put("/api/runs/{run_id}/key")
    def save_draft(run_id: str, edit: DraftEdit) -> dict:
        """Save a corrected draft, refusing anything that changes its standing."""
        keys_dir, app_name = key_scope.for_run(history, run_id)
        held = store.read(keys_dir, app_name)
        changed = _guard_frozen(held, edit.key)
        # Asked **before** the write, though the answer only reports. Validating
        # afterwards meant a corrupt manifest raised out of a request that had
        # already changed the file: a failed call that succeeded. Every refusal
        # this module raises now leaves the draft exactly as it found it.
        said = store.validate(keys_dir, app_name, changed)
        store.write(keys_dir, app_name, changed)
        # Saved, then told what promotion would still refuse -- **not** gated on
        # it. The gate is `promote_key.py`, which is the thing that actually
        # publishes, and a draft is invisible to scoring until it runs.
        return {"app": app_name, "key": changed, "refusals": said}


def _guard_frozen(held: dict, edited: dict) -> dict:
    """The edit with its identity taken from disk, refusing any attempt to move it.

    Named rather than silently overwritten: an editor that quietly restored
    `source` would accept a request that meant to launder the key and answer as
    though it had worked.
    """
    # First, because every check below reads the entries. Refused rather than
    # settled to an empty list: a save that quietly dropped a malformed
    # `findings` would answer 200 and delete the draft's real entries.
    malformed = entries_malformed(edited)
    if malformed:
        raise HTTPException(
            status_code=store.REFUSED,
            detail=f"{malformed}. A save corrects entries; it cannot replace them "
                   "with something that is not a list of entries.")
    moved = frozen_moved(held, edited)
    if moved:
        raise HTTPException(
            status_code=store.REFUSED,
            detail=f"a drafted key keeps its own standing; these may not be edited: "
                   f"{', '.join(moved)}. `source` stays tool_drafted however much "
                   "of the key you correct; recording that a human checked it is "
                   "the verify route, which moves `verified` and nothing else.")
    anchored = anchors_moved(held, edited)
    if anchored:
        raise HTTPException(
            status_code=store.REFUSED,
            detail=f"{anchored} entries add or move a file, line or anchor. An "
                   "anchor is a quotation from source this page has not read, so it "
                   "may not be typed here -- redraft against the pinned tree "
                   "instead. An entry this draft never held counts: appending one "
                   "would publish ground truth quoting a line nobody looked at.")
    return settled(held, edited)

"""Recording that a human checked a drafted grading key.

**Its own route and its own module, not part of a save.** Correcting a title and
signing off a key are different acts, and keeping them apart is what lets
`source`, `verified`, `verified_by` and `verified_date` *all* stay frozen for an
ordinary edit -- see `key_edit_guard.FROZEN_FIELDS`. A save free to move the
pair could flip `source` to `manual_review` and `verified` to true together, and
both documents are individually valid, so nothing downstream would object: a
drafted key would have been laundered into one that reads as human-authored.

**What verifying does, exactly.** It clears one qualification, `key_unverified`,
and no other. The key stays `tool_drafted`, so every figure scored against it
still carries `key_ai_drafted` and `key_drafted_by_scored_system` -- reading
every entry confirms the entries, and cannot make the tool's own choice of which
lines were candidates independent of the tool. That is why the pairing
`tool_drafted` + `verified: true` is safe to allow at all; `harness.check_key`
refused it until 2026-09-16, which left a reviewer no way to record a check
except by editing `source` and erasing the warning that matters.

**The claim is a claim.** This server has no authentication, so `verified_by` is
what someone typed, not who they are. `promote_key.py` is where that starts
bounding a published figure, and it refuses a verified draft without
`--accept-verification`.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import key_draft_store as store
from key_edit_guard import FROZEN_FIELDS
from run_record import auditor_refusals, today


class Verification(BaseModel):
    """A claim that a human has checked every entry of a draft."""

    verified_by: str = ""


def register(app: FastAPI) -> None:
    """Attach the one route that records a human check."""

    @app.post("/api/keys/{app_name}/verify")
    def verify(app_name: str, claim: Verification) -> dict:
        """Record that a human checked this draft. Moves `verified` and nothing else."""
        held = store.read(app_name)
        _refuse_bad_name(claim.verified_by)
        _refuse_second_claim(app_name, held)
        checked = {**held, "verified": True,
                   "verified_by": claim.verified_by.strip(),
                   # Observed here, never sent: a date the client supplies could
                   # be backdated through the page.
                   "verified_date": today()}
        # Before the write, and this is the route where that matters most: a
        # corrupt manifest used to raise *after* `verified: true` reached disk,
        # so the caller saw a 500, the claim was recorded anyway, and the retry
        # was refused as a second claim. A refusal here leaves nothing behind.
        said = store.validate(app_name, checked)
        store.write(app_name, checked)
        return {"app": app_name, "key": checked,
                "frozen_fields": list(FROZEN_FIELDS),
                "refusals": said}


def _refuse_bad_name(verified_by: str) -> None:
    """A check names who made it, under the rules an auditor name is held to.

    The rules are reused and the wording is not: `auditor_refusals` says "an
    audit records who asked for it", and this is not an audit.
    """
    refused = auditor_refusals(verified_by)
    if refused:
        raise HTTPException(
            status_code=store.REFUSED,
            detail=f"a recorded check names who made it: {'; '.join(refused)}")


def _refuse_second_claim(app_name: str, held: dict) -> None:
    """One check per draft: a later claim may not quietly replace the first."""
    if not held.get("verified"):
        return
    raise HTTPException(
        status_code=store.REFUSED,
        detail=f"{app_name} is already verified by "
               f"{held.get('verified_by') or 'someone'}. Withdrawing that is a "
               "hand edit, so a second claim cannot quietly replace the first.")

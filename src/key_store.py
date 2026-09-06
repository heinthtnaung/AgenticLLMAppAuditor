"""Puts a drafted grading key on disk, and the pin that makes it reproducible.

Split from `key_drafting`, which shapes what the model said into entries. This
module is the file I/O at the edge: one job each, and neither file grows past
the point where a reader has to scroll to find out what it does.

**The manifest is not a formality.** `emit_vex.product_iri` reads a grading
key's manifest *before* the fetched pin, so a manifest with an empty
`upstream_url` publishes a VEX product of `"@<commit>"` -- a malformed
identifier, in a signed document, with nothing raising. That is why `write`
takes the whole pin rather than the commit alone.
"""

import json
from pathlib import Path

from grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path

# What a drafted pin records. `role` is the fetcher's, because that is what
# actually happened: a tree was fetched for audit and a key drafted over it.
# `framework` and `language` are absent on purpose -- they are human judgements
# about the app, and a promotion step is where a human supplies them.
DRAFTED_ROLE = "fetched_for_audit"

DRAFT_NOTE = ("Drafted by the auditor over the tree at this commit. Not a "
              "hand-written key: read it before scoring anything against it.")


def manifest(app: str, pin: dict) -> dict:
    """The pin a drafted key ships beside it, carrying the fetch's own provenance."""
    return {
        "name": app,
        "role": DRAFTED_ROLE,
        "upstream_url": pin.get("upstream_url", ""),
        "upstream_commit": pin.get("upstream_commit", ""),
        "upstream_commit_date": pin.get("upstream_commit_date", ""),
        "note": DRAFT_NOTE,
    }


def _dump(path: Path, document: dict) -> None:
    """Write one JSON document the way every other artifact is written."""
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def write(app: str, document: dict, pin: dict, keys_dir: Path) -> Path:
    """Write the key and its pin, refusing to overwrite either.

    An unpinned key is refused here rather than written, because
    `grading_keys._check_app` raises on one: without this the failure would
    surface at the next `discover_graded_apps`, several steps later and nowhere
    near the cause.
    """
    if not pin.get("upstream_commit"):
        raise ValueError(
            f"cannot draft a key for {app}: no upstream commit could be read for this "
            "tree, and a key's line numbers mean nothing without the commit they were "
            "read at. Fetch the app by URL, or clone it and keep its .git.")
    ground_truth = key_path(app, GROUND_TRUTH_SUFFIX, keys_dir)
    if ground_truth.exists():
        raise FileExistsError(
            f"{ground_truth} already exists and is not overwritten: a redraft would "
            "discard whatever a human has corrected in it. Delete it to start over.")
    ground_truth.parent.mkdir(parents=True, exist_ok=True)
    _dump(ground_truth, document)
    _dump(key_path(app, MANIFEST_SUFFIX, keys_dir), manifest(app, pin))
    return ground_truth


def existing(app: str, keys_dir: Path) -> Path | None:
    """The key already on disk for this app, drafted or hand-written, or None."""
    path = key_path(app, GROUND_TRUTH_SUFFIX, keys_dir)
    return path if path.is_file() else None

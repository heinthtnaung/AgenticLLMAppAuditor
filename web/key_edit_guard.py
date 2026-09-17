"""What an edit to a drafted key may not do.

Split from the routes because both of them consult it and because it is the
whole security argument of the editor in one place: an edit may not move the
key's standing, and it may not type an anchor.

**`source` and `verified` are both frozen here, and that stays true even though
a key may now be verified.** Verification is its own route and its own act: a
save corrects titles, and flipping the *pair* -- `source` to `manual_review` and
`verified` to true together -- is the laundering this list exists to refuse. A
key verified through the verify route keeps `source: tool_drafted`, so
`key_ai_drafted` and `key_drafted_by_scored_system` both still fire.
"""

FROZEN_FIELDS = (
    "schema_version", "app", "upstream_commit", "source",
    "verified", "verified_by", "verified_date",
    "findings_complete", "expected_surfaces_complete",
    # What the extractor found, not a human judgement. A key that lets a person
    # edit it loses the ability to say a surface was *missed* rather than
    # badly found, which is the one thing this field exists for.
    "expected_surfaces", "expected_surface_count",
)

# Recomputed on every save rather than typed: a human deleting an entry leaves
# a stale count behind, which is what `key_promotion._miscounted` refuses.
DERIVED_COUNTS = {"finding_count": "findings"}

# An anchor is a quotation from source. The browser has not seen that source, so
# it may not supply one -- the same rule the drafting prompt puts on the model.
ANCHORED_FIELDS = ("file", "line", "code_anchor")


def frozen_moved(held: dict, edited: dict) -> list[str]:
    """Which fields an edit tried to move that it may not."""
    return [field for field in FROZEN_FIELDS
            if field in edited and edited[field] != held.get(field)]


def anchors_moved(held: dict, edited: dict) -> int:
    """How many entries carry a field only the source can establish.

    **An entry the draft never held counts too.** Skipping unknown ids let an
    edit *append* a finding with a file, a line and an anchor nobody had read --
    and nothing downstream objects, because such an entry is well-formed and
    carries a non-empty anchor, so promotion would publish ground truth quoting
    a line that was never looked at. The page cannot add entries; this is what
    stops a request doing it anyway.
    """
    before = {entry.get("id"): entry for entry in _entries(held)}
    return sum(1 for entry in _entries(edited)
               if entry.get("id") not in before
               or any(entry.get(field) != before[entry["id"]].get(field)
                      for field in ANCHORED_FIELDS))


def entries_malformed(edited: object) -> str | None:
    """Why this body's `findings` cannot be saved as entries, or None when it can.

    Three ways: the body is not an object, it names no `findings` at all, or
    what it names is not a list of objects.

    **A save must refuse this, not coerce it.** Treating a malformed `findings`
    as "no entries" made `PUT {"key": {"findings": "xy"}}` answer 200 and write
    an empty list over a draft that held real ones -- a correction request
    destroying the thing it was meant to correct, which is worse than the 500 it
    replaced. Coercion is right when *reading* what is already on disk and wrong
    when accepting what someone sent.
    """
    if not isinstance(edited, dict):
        return f"the key must be a json object, not {type(edited).__name__}"
    # Absent is refused; an explicit `[]` is not. Deleting every entry is a
    # legal edit a person may mean, and `test_key_edit_save.py` holds it -- but
    # a body that simply *omits* the field settles to no entries too, so a page
    # bug that dropped it would empty the draft and answer 200. The two cases
    # are one `in` apart and only one of them is someone's decision.
    if "findings" not in edited:
        return ("the key names no findings at all; send the entries you mean to "
                "keep, or an empty list to delete every one of them")
    found = edited["findings"]
    if not isinstance(found, list):
        return f"findings must be a list, not {type(found).__name__}"
    wrong = [str(at) for at, entry in enumerate(found) if not isinstance(entry, dict)]
    if wrong:
        return f"findings entries must be objects; these are not: {', '.join(wrong[:6])}"
    return None


def _entries(document: object) -> list[dict]:
    """A document's findings, as far as they are entries at all.

    **This reads a request body**, so it needs no hand-edited file to be the
    wrong shape: `{"key": {"findings": "xy"}}` iterated a string and `.get` on a
    character raised, and `findings: [1, 2]` did the same on an int. Anything
    that is not a list of objects contributes no entries, and the save is then
    refused by name further down rather than crashing here.
    """
    if not isinstance(document, dict):
        return []
    found = document.get("findings")
    return [entry for entry in found if isinstance(entry, dict)] \
        if isinstance(found, list) else []


def settled(held: dict, edited: dict) -> dict:
    """The edit with its identity taken from disk, its counts recomputed, entries sorted.

    Reads the same request body `anchors_moved` does, so it makes the same
    assumption about nothing: `len("xy")` is 2 rather than an error, and sorting
    a string by `entry.get(...)` raises. Anything that is not a list of objects
    settles to no entries, and `key_promotion.refusals` -- which the route asks
    before it writes -- then refuses the save by name.
    """
    kept = {**edited, **{f: held[f] for f in FROZEN_FIELDS if f in held}}
    kept["findings"] = _entries(kept)
    for count, over in DERIVED_COUNTS.items():
        kept[count] = _length(kept.get(over))
    # Re-sorted because `key_promotion._out_of_order` refuses a key that is not,
    # and so two revisions of one draft can be diffed.
    kept["findings"] = sorted(kept["findings"],
                              key=lambda e: (str(e.get("file", "")), _line(e), str(e.get("id", ""))))
    return kept


def _length(items: object) -> int:
    """How many entries a field holds, counting anything that is not a list as none."""
    return len(items) if isinstance(items, list) else 0


def _line(entry: dict) -> int:
    """An entry's line for sorting only. A hand-typed string must not stop the sort."""
    line = entry.get("line", 0)
    return line if isinstance(line, int) else 0

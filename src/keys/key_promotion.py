"""Decides whether a drafted grading key is fit to become a real one.

Promotion is the moment a drafted key stops being a suggestion and starts being
the answer a run is marked against. Everything a shipped key is held to applies
from that moment, and a draft satisfies almost none of it -- so this refuses,
with the reason, rather than letting the move succeed and the suite explain it
later in six failures a reader has to reverse-engineer.

**What it does not do is edit the key.** It says what is wrong; a human fixes
it. A tool that silently repaired its own draft on the way in would be back to
marking its own homework, which is the one thing this whole path is careful
about. In particular `source` and `verified` are left exactly as they are:
`key_drafted_by_scored_system` is meant to survive promotion, because a human
correcting entries does not undo the tool having chosen which lines were
candidates. Clearing it is a separate, deliberate edit.
"""

from itertools import combinations
from pathlib import Path

from evaluation.grading import line_window
from evaluation.harness import check_key

# A commit is 40 hex characters. Checked because a hand edit that removes one
# does not break this app alone: `discover_graded_apps` raises for the WHOLE
# folder, so one bad promotion makes every graded app unscoreable.
COMMIT_LENGTH = 40

# What a graded app's pin must carry that a fetched one need not. Human
# judgements about the app, which is why a draft cannot supply them.
GRADED_PIN_FIELDS = ("framework", "language")

# The scheme a product identity is built from. `emit_vex.product_iri` joins the
# url and the commit with no validation, so an empty url there publishes a
# product of "@<commit>" in a signed document.
REQUIRED_URL_SCHEME = "https://"

# Every entry needs one, and a model cannot supply it: an anchor is a quotation
# of source, and a model asked to quote text it was not shown invents it. The
# producer reads it from disk, so an empty one means the file or line moved.
ANCHOR_FIELD = "code_anchor"


def _missing_pin_fields(pin: dict) -> list[str]:
    """The graded-pin fields a drafted manifest cannot fill in for itself."""
    return [field for field in GRADED_PIN_FIELDS if not pin.get(field)]


def _entries_without_anchors(key: dict) -> list[str]:
    """Every entry id whose code anchor is missing or empty."""
    return [entry.get("id", "?") for entry in key.get("findings", [])
            if not entry.get(ANCHOR_FIELD)]


def _out_of_order(key: dict) -> bool:
    """True when the entries are not in the (file, line, id) order a key is diffed in."""
    order = [(e["file"], e["line"], e.get("id", "")) for e in key.get("findings", [])]
    return order != sorted(order)


def _colliding_pairs(key: dict) -> list[str]:
    """Pairs one finding could answer twice: same file, same risk class, overlapping windows."""
    entries = key.get("findings", [])
    return [f"{left.get('id')} and {right.get('id')}"
            for left, right in combinations(entries, 2)
            if left["file"] == right["file"]
            and left["owasp_id"] == right["owasp_id"]
            and _windows_overlap(left, right)]


def _windows_overlap(left: dict, right: dict) -> bool:
    """True when one finding could sit in both entries' line windows.

    The window comes from `evaluation.grading`, which is the module that will
    actually join findings to these entries. A copy of the arithmetic here had
    already drifted before anyone read it: it ignored `line_end`, so an entry
    carrying one had a wider window in the scorer than in this check, and the
    double-count this refuses would have passed. `key_promotion` is a top-level
    module on no audit path, so importing the scorer crosses no boundary --
    `test_scorer_boundary.py` guards the five package trees, not this.
    """
    left_open, left_close = line_window(left)
    right_open, right_close = line_window(right)
    return left_open <= right_close and right_open <= left_close


ENTRY_FIELDS = ("id", "file", "line", "owasp_id", "llm_surface", "title", "description")


def _malformed_entries(key: dict) -> list[str]:
    """Entries missing a field the checks below, or the scorer, would subscript.

    The input to promotion is a file a human has been editing, so a deleted
    field is likelier here than anywhere else in the project. Refusing it names
    the entry; subscripting it raises `KeyError`, which is not in
    `promote_key.EXPECTED_FAILURES` and reaches the user as a traceback.
    """
    return [f"{entry.get('id', '?')} ({', '.join(f for f in ENTRY_FIELDS if f not in entry)})"
            for entry in key.get("findings", [])
            if any(field not in entry for field in ENTRY_FIELDS)]


def _miscounted(key: dict) -> list[str]:
    """The count fields a human deleting an entry leaves behind."""
    return [f"{count} says {key.get(count)} but {items} holds {len(key.get(items, []))}"
            for count, items in (("finding_count", "findings"),
                                 ("expected_surface_count", "expected_surfaces"))
            if key.get(count) != len(key.get(items, []))]


def _pin_refusals(pin: dict) -> list[str]:
    """What the pin must carry beyond the fields a fetched manifest already has."""
    said = []
    commit = pin.get("upstream_commit", "")
    if len(commit) != COMMIT_LENGTH or not commit.isalnum():
        said.append(f"the manifest's upstream_commit is not {COMMIT_LENGTH} alphanumeric "
                    "characters; an unpinned key makes EVERY graded app unscoreable, "
                    "because discovery refuses the whole folder")
    missing = _missing_pin_fields(pin)
    if missing:
        said.append(f"the manifest names no {' or '.join(missing)}; both are human "
                    "judgements about the app and a draft cannot supply them")
    if not pin.get("upstream_url", "").startswith(REQUIRED_URL_SCHEME):
        said.append(f"the manifest's upstream_url is not an {REQUIRED_URL_SCHEME} link, "
                    "so the VEX product identity built from it would be malformed")
    return said


def _scorer_refusal(key: dict) -> list[str]:
    """What a scoring run would refuse this key for, asked of the scorer itself.

    Reuse rather than reimplementation: schema version, the `source` vocabulary,
    the tool-drafted/verified pairing and the per-entry fields are all already
    enforced at score time, and a second copy here would drift from them.
    """
    try:
        check_key(key, Path("the promoted key"))
    except ValueError as error:
        return [str(error).replace("the promoted key ", "")]
    return []


def refusals(key: dict, pin: dict) -> list[str]:
    """Every reason this draft is not yet a grading key, in the order to fix them.

    Malformed entries are reported alone: every check after them subscripts the
    fields they are missing, so running those too would raise rather than report.
    """
    malformed = _malformed_entries(key)
    if malformed:
        return [f"entries are missing required fields: {'; '.join(malformed)}"]
    said = _scorer_refusal(key) + _miscounted(key) + _pin_refusals(pin)
    unanchored = _entries_without_anchors(key)
    if unanchored:
        said.append(f"{len(unanchored)} entries carry no {ANCHOR_FIELD} ({', '.join(unanchored[:4])}"
                    f"{'...' if len(unanchored) > 4 else ''}); the line each names may have moved")
    if _out_of_order(key):
        said.append("the entries are not sorted by (file, line, id), so two revisions "
                    "of this key cannot be diffed")
    collisions = _colliding_pairs(key)
    if collisions:
        said.append(f"one finding could be counted against both {' and both '.join(collisions)}, "
                    "which reads as recall the tool did not earn")
    return said

"""The rule for matching a produced finding to a grading-key entry.

One definition, in source, because three test files had grown three different
windows for the same documented rule -- one symmetric, one wider below the
anchor, one ignoring `line_end` entirely. A scorer built on a fourth would
measure something the suite does not certify.

Exact line equality is wrong because a human anchors the construct's first
line while a detector may report a few lines into it -- the call inside a
multi-line expression, or the `def` under a decorator the human anchored. The
window therefore opens *at* the key's line and runs downward; it is not
symmetric, and a finding above the anchor is a different construct.
"""

LINE_TOLERANCE = 3

# The entry fields this module subscripts **only after a `.get()` test**, so a
# key without them matches rather than crashing. Not "the optional fields":
# `SCHEMAS.md` marks `llm_surface` required-but-nullable, and `line_end` is
# genuinely optional yet absent here because nothing subscripts it -- the
# criterion is the guard, not the schema. It has no production reader: it is
# here so a test can tell a guarded read from a crashable one, which an AST
# scan cannot. See `tests/evaluation/test_entry_field_cover.py`, which refuses
# a name added here without its guard.
GUARDED_ENTRY_FIELDS = ("llm_surface", "surface_name", "component")


def line_window(key_entry: dict) -> tuple[int, int]:
    """Return the line range a finding may sit in to match this key entry."""
    first = key_entry["line"]
    last = key_entry.get("line_end") or first
    return first, last + LINE_TOLERANCE


def matches_key(finding: dict, key_entry: dict) -> bool:
    """Say whether a produced finding answers this key entry.

    `detection` is never compared: the key's `either` says what could in
    principle reach the finding, while the produced value says what did this
    run, so neither constrains the other.
    """
    if finding.get("file") != key_entry["file"]:
        return False
    if finding.get("owasp_id") != key_entry["owasp_id"]:
        return False
    first, last = line_window(key_entry)
    if not first <= (finding.get("line") or -1) <= last:
        return False
    if key_entry.get("llm_surface") and finding.get("surface_kind") != key_entry["llm_surface"]:
        return False
    if key_entry.get("surface_name") and finding.get("surface_name") != key_entry["surface_name"]:
        return False
    if key_entry.get("component") and finding.get("purl") != key_entry["component"]:
        return False
    return True

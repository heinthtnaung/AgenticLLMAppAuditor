"""The grading keys this project ships, checked against `docs/SCHEMAS.md`.

A key is committed evidence, and a key nobody validated is worse than no key,
because a score computed from it still looks like a number. `grading_keys/` was
empty until 2026-09-05, so nothing checked one; one ships now, hand-authored and
AI-drafted, and this is that check. The pin beside it is
`test_shipped_grading_pin.py`.

The authority here is `docs/SCHEMAS.md`, not `evaluation/harness.py`. The
harness deliberately checks a *subset* -- the fields the scorer subscripts
unguarded -- so a missing one becomes a message instead of a crash. That is not
the same job as "this key is well-formed", and everything the schema marks
required is required whether a reader guards it or not.
"""

from artifacts.repo_path import is_repo_relative_posix
from artifacts.surface import SURFACE_KINDS
from grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, discover_graded_apps, key_path
from shipped_key_fixtures import SHIPPED_APPS, read, shipped_entries, shipped_keys

# `docs/SCHEMAS.md`, "the hand-written answer key": every field marked required.
REQUIRED_KEY_FIELDS = (
    "schema_version", "app", "upstream_commit", "source", "verified",
    "verified_by", "verified_date", "finding_count", "findings_complete",
    "expected_surfaces", "expected_surface_count", "expected_surfaces_complete",
    "findings",
)

# The eight required of each `findings` entry. `line_end`, `surface_name`,
# `component`, `detection` and `notes` are optional and are not asserted --
# a check stricter than the schema is as wrong as a looser one.
REQUIRED_ENTRY_FIELDS = (
    "id", "owasp_id", "title", "description", "file", "line", "code_anchor",
    "llm_surface",
)

KEY_SCHEMA_VERSION = 2
# `docs/SCHEMAS.md`: a code anchor is the first 60 characters of the trimmed
# source text at `line`.
CODE_ANCHOR_LENGTH = 60
OWASP_IDS = ("LLM01", "LLM02", "LLM03", "LLM06", "AUDITABILITY")
KEY_SOURCES = ("ai_drafted", "upstream_docs", "manual_review")
AI_DRAFTED = "ai_drafted"


# --- What ships -------------------------------------------------------------

def test_the_repository_ships_exactly_the_keys_named_here() -> None:
    """The guard that stops every test below passing over an empty folder."""
    assert discover_graded_apps() == SHIPPED_APPS


def test_each_shipped_key_and_its_pin_are_both_on_disk() -> None:
    """Discovery refuses an unpinned key; this states the pair exists rather than inferring it."""
    for app in SHIPPED_APPS:
        assert key_path(app, GROUND_TRUTH_SUFFIX).is_file(), app
        assert key_path(app, MANIFEST_SUFFIX).is_file(), app


# --- The key's own shape ----------------------------------------------------

def test_every_shipped_key_carries_every_required_field() -> None:
    """`docs/SCHEMAS.md` requires thirteen; the harness checks nine, which is a different job."""
    for app, key in shipped_keys():
        missing = [field for field in REQUIRED_KEY_FIELDS if field not in key]
        assert not missing, f"{app} is missing {missing}"


def test_every_shipped_key_is_at_the_schema_version_the_scorer_reads() -> None:
    """A key at another version would be refused at score time rather than here."""
    for app, key in shipped_keys():
        assert key["schema_version"] == KEY_SCHEMA_VERSION, app


def test_every_shipped_key_names_the_app_its_file_is_named_after() -> None:
    """The app name is the only join key, so the field and the file name must agree."""
    for app, key in shipped_keys():
        assert key["app"] == app


def test_every_shipped_key_agrees_with_its_pin() -> None:
    """Two files, one commit: a key scored against a different one scores the wrong lines."""
    for app, key in shipped_keys():
        manifest = read(app, MANIFEST_SUFFIX)
        assert key["upstream_commit"] == manifest["upstream_commit"], app
        assert manifest["name"] == app


def test_every_shipped_key_counts_its_own_contents() -> None:
    """A count that disagrees with the list makes every rate computed from it wrong."""
    for app, key in shipped_keys():
        assert key["finding_count"] == len(key["findings"]), app
        assert key["expected_surface_count"] == len(key["expected_surfaces"]), app


def test_every_shipped_key_declares_a_known_source() -> None:
    """How a key was written is what qualifies a score computed from it."""
    for app, key in shipped_keys():
        assert key["source"] in KEY_SOURCES, app


def test_an_ai_drafted_key_does_not_claim_to_be_verified() -> None:
    """Drafting a key and checking it are two facts, and this project keeps them apart.

    An unverified key still scores; the score is qualified. A drafted key that
    said `verified: true` would remove the qualification and nothing else would
    notice, which is the one failure that would silently reach the write-up.
    """
    for app, key in shipped_keys():
        if key["source"] != AI_DRAFTED:
            continue
        assert key["verified"] is False, app
        assert key["verified_by"] is None, app
        assert key["verified_date"] is None, app


def test_no_shipped_key_is_verified_by_anyone_yet() -> None:
    """Guards the test above against a key that quietly changed `source` instead."""
    assert [key["verified"] for _, key in shipped_keys()] == [False] * len(SHIPPED_APPS)


# --- Each finding entry -----------------------------------------------------

def test_every_shipped_key_holds_at_least_one_finding() -> None:
    """A key with no entries would make every per-entry test below prove nothing."""
    for app, key in shipped_keys():
        assert key["findings"], app
    assert shipped_entries()


def test_every_finding_entry_carries_every_required_field() -> None:
    """The eight `docs/SCHEMAS.md` marks required, including the ones no reader guards.

    `llm_surface` is required and *may be null*, which is not the same as being
    absent: `null` is a human saying "this finding is not tied to a surface",
    while a missing field is a human who did not consider the question. The
    scorer treats them alike -- `matches_key` reads it with `.get()` -- so
    nothing but this catches the difference.
    """
    for label, entry in shipped_entries():
        missing = [field for field in REQUIRED_ENTRY_FIELDS if field not in entry]
        assert not missing, f"{label} is missing {missing}"


def test_every_finding_entry_has_a_unique_id() -> None:
    """Ids are cited in results tables, so two entries sharing one would misattribute a row."""
    ids = [label for label, _ in shipped_entries()]
    assert len(set(ids)) == len(ids)


def test_every_finding_entry_names_a_risk_class_this_project_scores() -> None:
    """The 2025 OWASP subset plus auditability; anything else cannot be scored."""
    for label, entry in shipped_entries():
        assert entry["owasp_id"] in OWASP_IDS, label


def test_every_finding_entry_anchors_a_repo_relative_posix_path() -> None:
    """`file` is the join key against `surfaces.json`, which uses that same convention."""
    for label, entry in shipped_entries():
        assert is_repo_relative_posix(entry["file"]), f"{label}: {entry['file']!r}"


def test_every_finding_entry_anchors_a_real_line_number() -> None:
    """A line below 1 could match no surface, so it would be a silently unscoreable entry."""
    for label, entry in shipped_entries():
        assert isinstance(entry["line"], int) and entry["line"] >= 1, label


def test_every_code_anchor_is_the_trimmed_source_text_the_schema_describes() -> None:
    """"The first 60 characters of the trimmed source text at `line`", and no more.

    Nothing compares an anchor to the file any more -- the test that did lived
    in `tests/corpus/` and went with the pinned corpus -- so this is what is
    left: the anchor cannot be checked against the source, but it can be held
    to the shape a human would read it in. A leading indent means it was copied
    untrimmed, and over 60 characters means the rule was not applied at all.
    """
    for label, entry in shipped_entries():
        anchor = entry["code_anchor"]
        assert anchor and anchor == anchor.lstrip(), f"{label}: {anchor!r}"
        assert len(anchor) <= CODE_ANCHOR_LENGTH, f"{label}: {len(anchor)} characters"


def test_every_named_surface_kind_is_one_the_extractor_produces() -> None:
    """`llm_surface` joins on `Surface.kind`, so a kind outside the four matches nothing."""
    for label, entry in shipped_entries():
        kind = entry.get("llm_surface")
        assert kind is None or kind in SURFACE_KINDS, f"{label}: {kind!r}"


def test_every_key_lists_its_findings_in_the_documented_order() -> None:
    """Sorted by (file, line, id): a fixed order is what lets two revisions be diffed."""
    for app, key in shipped_keys():
        order = [(e["file"], e["line"], e["id"]) for e in key["findings"]]
        assert order == sorted(order), app

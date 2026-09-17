"""What a grading key and the pin beside it must hold, in one place.

These are rules about *any* key, not about a key that exists. `grading_keys/`
held one until 2026-09-06 and holds none now, so the three files that read the
folder went with it -- but a key written tomorrow must satisfy every line here,
and `promote_key.py` is where most of them are enforced. The constants outlived
their old readers: `tests/compare/test_promoted_key_shipped_rules.py` and its
two companions hold a key they build, promote and read back under `tmp_path` to
exactly this list, which is a subject a test can construct rather than one it
has to find on disk.

**Where the lists come from.** `docs/SCHEMAS.md` still names the fields, but its
required/optional columns went when that file was cut short: `git show
c8de660^:docs/SCHEMAS.md` is the last revision that marks them, and these are
read off it. Nothing below is stricter than that table -- every field it marks
optional is absent here, because a check stricter than the schema is as wrong as
a looser one and harder to spot, since its own tests pass.

Spelled out rather than imported from `src/`, deliberately. A field list taken
from the code it checks agrees with that code by construction; these are read
off the schema, so the two can disagree and a test can say which.
"""

# Every field the key document marks required. Thirteen.
# `evaluation/harness.py` checks nine -- the ones the scorer subscripts
# unguarded, so a missing one becomes a message instead of a crash -- which is a
# different job from "this key is well-formed".
REQUIRED_KEY_FIELDS = (
    "schema_version", "app", "upstream_commit", "source", "verified",
    "verified_by", "verified_date", "finding_count", "findings_complete",
    "expected_surfaces", "expected_surface_count", "expected_surfaces_complete",
    "findings",
)

# The eight required of each `findings` entry. `line_end`, `surface_name`,
# `component`, `detection` and `notes` are optional and are not asserted.
# `test_promotion_requires_exactly_the_entry_fields_the_schema_does` holds
# `key_promotion` to this same eight, in both directions.
REQUIRED_ENTRY_FIELDS = (
    "id", "owasp_id", "title", "description", "file", "line", "code_anchor",
    "llm_surface",
)

# The four the schema marks optional and nullable on an entry, read off the
# "Entry fields" paragraph of today's `docs/SCHEMAS.md` -- the mirror of the
# eight above. A check that *required* one of these would be stricter than the
# schema. Being optional and being typed are different claims: `line_end` is
# the one of the four that also has a type rule, `harness.NULLABLE_TYPED_ENTRY_
# FIELDS`, which says what it may hold when it is there and nothing about
# whether it must be.
OPTIONAL_ENTRY_FIELDS = ("surface_name", "component", "detection", "line_end")

# A code anchor is the first 60 characters of the trimmed source text at `line`.
# `key_drafting` has the same number; this one is the schema's, so the producer
# can be compared against it instead of taken on trust.
CODE_ANCHOR_LENGTH = 60

# The 2025 OWASP subset plus auditability. `artifacts/finding.py` holds the same
# tuple for produced findings; a key naming anything else joins nothing and is
# unscoreable.
OWASP_IDS = ("LLM01", "LLM02", "LLM03", "LLM06", "AUDITABILITY")

# --- the provenance manifest beside the key ----------------------------------

# The five fields a pin carries, in the one shape that serves two producers:
# `fetch_repo.manifest` writes it for a fetched tree, a human writes it for a
# graded app.
REQUIRED_PIN_FIELDS = ("name", "role", "upstream_url", "upstream_commit",
                       "upstream_commit_date")

# Required of a *graded* app's pin only. A fetched manifest omits them because a
# fetcher cannot know either, and a guess in a provenance record is worse than a
# gap -- which is why `key_promotion` refuses a draft that still lacks them.
GRADED_PIN_FIELDS = ("framework", "language")

# The three values `role` may take. It is also the tool-derived marker:
# `fetched_for_audit` is the only one a tool ever writes.
PIN_ROLES = ("deliberately_vulnerable_demo", "open_source_reference", "fetched_for_audit")

HTTPS_PREFIX = "https://"
COMMIT_LENGTH = 40

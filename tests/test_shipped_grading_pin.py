"""The provenance manifest beside each shipped grading key.

Every line number in a key is valid against exactly one commit, so the pin is
the only thing that makes a key reproducible -- and unlike a fetched tree's
manifest, this one is hand-authored, so nothing but a test checks it. The key
itself is `test_shipped_grading_key.py`; this file is only about the record of
where the code it describes came from.

The field list is `docs/SCHEMAS.md`'s provenance-manifest table, which one shape
serves twice: `src/fetch_repo.py` writes it for a fetched tree, a human writes
it for a graded app. The two differ in exactly one place, `framework` and
`language`, and that difference is asserted rather than described.
"""

from shipped_key_fixtures import SHIPPED_APPS, shipped_pins

# `docs/SCHEMAS.md`, the provenance manifest: required of both producers.
REQUIRED_PIN_FIELDS = ("name", "role", "upstream_url", "upstream_commit",
                       "upstream_commit_date")

# Required of a *graded* app's pin only. A fetched manifest omits them because a
# fetcher cannot know either, and a guess in a provenance record is worse than a gap.
GRADED_PIN_FIELDS = ("framework", "language")

# The three values `role` may take. It is also the tool-derived marker:
# `fetched_for_audit` is the only one a tool ever writes.
PIN_ROLES = ("deliberately_vulnerable_demo", "open_source_reference", "fetched_for_audit")

HTTPS_PREFIX = "https://"
COMMIT_LENGTH = 40


def test_there_is_a_pin_to_check() -> None:
    """The guard: with no shipped app, every loop below would pass over nothing."""
    assert shipped_pins() and len(shipped_pins()) == len(SHIPPED_APPS)


def test_every_pin_carries_every_required_field() -> None:
    """The pin is the only surviving evidence of what its key was read against."""
    for app, pin in shipped_pins():
        missing = [field for field in REQUIRED_PIN_FIELDS if field not in pin]
        assert not missing, f"{app} pin is missing {missing}"


def test_every_pin_names_a_full_commit() -> None:
    """An abbreviated sha is ambiguous, and a pin that is ambiguous pins nothing."""
    for app, pin in shipped_pins():
        commit = pin["upstream_commit"]
        assert len(commit) == COMMIT_LENGTH and commit.isalnum(), f"{app}: {commit!r}"


def test_every_pin_is_an_https_url() -> None:
    """The same rule `fetch_repo` enforces, so a pinned commit can really be re-fetched."""
    for app, pin in shipped_pins():
        assert pin["upstream_url"].startswith(HTTPS_PREFIX), f"{app}: {pin['upstream_url']!r}"


def test_every_pin_declares_a_known_role() -> None:
    """`role` has a documented vocabulary of three, and nothing under `src/` enforces it."""
    for app, pin in shipped_pins():
        assert pin["role"] in PIN_ROLES, f"{app}: {pin['role']!r}"


def test_every_graded_apps_pin_says_what_it_exercises() -> None:
    """`framework` and `language` are required of a graded app's pin, absent from a fetched one."""
    for app, pin in shipped_pins():
        missing = [field for field in GRADED_PIN_FIELDS if field not in pin]
        assert not missing, f"{app} pin is missing {missing}"

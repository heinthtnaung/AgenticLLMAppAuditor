"""The pin a drafted key ships beside it, and the VEX product read back out of it.

`key_store.write` takes the whole pin rather than the commit alone, and this is
why. `emit_vex.product_iri` looks for a grading key's manifest **before** the
fetched one and returns `"{upstream_url}@{upstream_commit}"` -- so a manifest
with an empty url publishes a product of `"@<commit>"`: a malformed identifier,
in a signed document about a third party's code, with nothing raising anywhere.
The last test here is that failure, kept as a live demonstration rather than a
comment, so the first one cannot quietly stop meaning anything.

The manifest is read from `tmp_path` in every test: `grading_keys.KEYS_DIR` is
pointed there, which is the seam `key_path` resolves through. A promoted draft
is exactly this -- a human moves the pair up one level, and `product_iri` then
finds it where a hand-written key's manifest would be.
"""

import json

import emit_vex
from keys import grading_keys
from keys import key_store
from drafted_key_fixtures import APP, COMMIT, PIN, UPSTREAM_URL, draft_into
from keys.grading_keys import MANIFEST_SUFFIX, key_path

# What the fetcher records about a tree, and what a drafted pin must carry over.
PIN_FIELDS = ("upstream_url", "upstream_commit", "upstream_commit_date")

# A pin with no url: what `key_store.write` used to be handed when it took a
# commit and nothing else.
URL_LESS_PIN = {"upstream_commit": COMMIT, "upstream_url": "",
                "upstream_commit_date": ""}


def promoted(monkeypatch, tmp_path, pin: dict = PIN):
    """Write the pair where a human promoting a draft would put it, and look there for it."""
    monkeypatch.setattr(grading_keys, "KEYS_DIR", tmp_path)
    draft_into(tmp_path, pin=pin)


# --- what the manifest carries ------------------------------------------------

def test_the_manifest_carries_every_field_the_fetch_pin_recorded() -> None:
    """A drafted key is pinned by the fetch that produced the tree, not by a commit alone."""
    written = key_store.manifest(APP, PIN)
    assert {field: written[field] for field in PIN_FIELDS} \
        == {field: PIN[field] for field in PIN_FIELDS}


def test_the_manifest_carries_the_repository_the_tree_came_from() -> None:
    """The one field a commit-only writer could not supply, stated on its own."""
    assert key_store.manifest(APP, PIN)["upstream_url"] == UPSTREAM_URL


def test_the_manifest_is_named_for_the_app_it_pins() -> None:
    """The app name is the only join key, so the pin spells it too."""
    assert key_store.manifest(APP, PIN)["name"] == APP


def test_the_manifest_says_the_tree_was_fetched_for_audit() -> None:
    """`role` records what actually happened, and no human judgement is invented beside it."""
    written = key_store.manifest(APP, PIN)
    assert written["role"] == key_store.DRAFTED_ROLE
    assert "framework" not in written and "language" not in written


def test_a_pin_that_says_nothing_yields_empty_strings_not_a_crash() -> None:
    """`pin_document` answers `{}` for an unpinned tree; `write` is what refuses that."""
    assert key_store.manifest(APP, {})["upstream_commit"] == ""


# --- what the VEX product comes out as ----------------------------------------

def test_the_product_names_the_repository_and_the_commit(monkeypatch, tmp_path) -> None:
    """The whole reason `write` takes the pin: the product is a resolvable identifier."""
    promoted(monkeypatch, tmp_path)
    assert emit_vex.product_iri(APP) == f"{UPSTREAM_URL}@{COMMIT}"


def test_the_product_does_not_begin_with_the_separator(monkeypatch, tmp_path) -> None:
    """The failure this guards against, stated as its own claim rather than inferred."""
    promoted(monkeypatch, tmp_path)
    assert not emit_vex.product_iri(APP).startswith("@")


def test_the_product_is_read_from_the_manifest_that_was_written(monkeypatch,
                                                                tmp_path) -> None:
    """Guard: the assertions above would pass over a pin some other test had left."""
    promoted(monkeypatch, tmp_path)
    pin = json.loads(key_path(APP, MANIFEST_SUFFIX, tmp_path).read_text(encoding="utf-8"))
    assert emit_vex.product_iri(APP) == f"{pin['upstream_url']}@{pin['upstream_commit']}"


def test_a_pin_with_no_url_publishes_a_product_that_names_no_repository(monkeypatch,
                                                                       tmp_path) -> None:
    """The live demonstration: nothing raises, and the document says `@<commit>`."""
    promoted(monkeypatch, tmp_path, pin=URL_LESS_PIN)
    assert emit_vex.product_iri(APP) == f"@{COMMIT}"

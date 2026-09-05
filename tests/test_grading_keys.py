"""Which apps have a grading key, and what a half-added key does.

A key is `grading_keys/<app>.ground_truth.json`, with the upstream pin beside
it under the same name. **Zero keys is still normal**: the pinned corpus was
removed on 2026-09-04 and the auditor takes any repository by URL, so discovery
answers an empty folder with nothing rather than raising. The one thing it
still refuses is a key with no manifest, because a key's line numbers mean
nothing without the commit they were read at.

Those two outcomes are easy to confuse, and confusing them is expensive in
opposite directions: an empty folder that raised would stop a clean checkout
from running at all, and an unpinned key that passed would be scored against
line numbers nobody can reproduce.

Every tree here is written into `tmp_path` and passed in as `keys_dir`, except
the one test below that points at the repository's own folder -- and that one
only asks whether discovery agrees with what is on disk. **Which keys ship, and
whether they are well-formed, is `test_shipped_grading_key.py`**; one key ships
now, so neither file may assume the folder is empty.
"""

from pathlib import Path

import pytest

from grading_keys import (
    BASELINE_SUFFIX,
    GROUND_TRUTH_SUFFIX,
    KEYS_DIR,
    MANIFEST_SUFFIX,
    discover_graded_apps,
    key_path,
)

APP = "a-graded-app"

# Enough for a key to exist and parse. Discovery never reads a key's contents
# -- the scorer does, and `harness._check_key` is where its shape is checked.
STUB = "{}"

# A manifest that really pins something. Discovery *does* read this one: a
# manifest holding `{}` pins nothing, and the refusal claims it pins a commit.
PIN = '{"upstream_commit": "%s"}' % ("a" * 40)


def write_key(keys_dir: Path, app: str, with_manifest: bool = True,
              manifest_text: str = PIN) -> None:
    """Write one app's grading key, and its pin unless the test is about a missing one."""
    keys_dir.mkdir(parents=True, exist_ok=True)
    (keys_dir / f"{app}{GROUND_TRUTH_SUFFIX}").write_text(STUB, encoding="utf-8")
    if with_manifest:
        (keys_dir / f"{app}{MANIFEST_SUFFIX}").write_text(manifest_text, encoding="utf-8")


def test_a_manifest_that_pins_nothing_is_refused_like_a_missing_one(tmp_path) -> None:
    """`{}` is a manifest by name only: the refusal claims a commit, so one is required."""
    write_key(tmp_path, APP, manifest_text="{}")
    with pytest.raises(RuntimeError, match="names no upstream_commit"):
        discover_graded_apps(tmp_path)


def test_a_manifest_that_is_not_json_says_so_rather_than_blaming_the_field(tmp_path) -> None:
    """A syntax error and a missing field are different faults, so they read differently.

    "names no upstream_commit" would send someone looking for a field their
    file may well contain, when the problem is the JSON around it.
    """
    write_key(tmp_path, APP, manifest_text="not json at all")
    with pytest.raises(RuntimeError, match="is not readable json"):
        discover_graded_apps(tmp_path)


def test_a_manifest_whose_commit_is_an_empty_string_is_refused(tmp_path) -> None:
    """Present but empty pins nothing, so the value is checked and not merely the key."""
    write_key(tmp_path, APP, manifest_text='{"upstream_commit": ""}')
    with pytest.raises(RuntimeError, match="names no upstream_commit"):
        discover_graded_apps(tmp_path)


def test_a_manifest_whose_commit_is_not_text_is_refused(tmp_path) -> None:
    """A null or numeric commit pins nothing either, so the type is checked, not just the key."""
    write_key(tmp_path, APP, manifest_text='{"upstream_commit": null}')
    with pytest.raises(RuntimeError, match="names no upstream_commit"):
        discover_graded_apps(tmp_path)


# --- Where a key lives -------------------------------------------------------

def test_a_key_path_is_the_app_name_and_the_suffix(tmp_path) -> None:
    """The app name is the join key, so it is the whole of the file name."""
    assert key_path(APP, GROUND_TRUTH_SUFFIX, tmp_path) == \
        tmp_path / f"{APP}{GROUND_TRUTH_SUFFIX}"


def test_the_three_suffixes_name_three_different_files(tmp_path) -> None:
    """Key, pin and baseline sit beside each other, so none may collide with another."""
    paths = {key_path(APP, suffix, tmp_path)
             for suffix in (GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, BASELINE_SUFFIX)}
    assert len(paths) == 3


def test_the_default_keys_directory_is_at_the_repository_root() -> None:
    """`evaluate.py` prints this path, so it must be the folder a reader would create."""
    assert KEYS_DIR.name == "grading_keys"
    assert KEYS_DIR.parent == Path(__file__).resolve().parents[1]


# --- Discovery ---------------------------------------------------------------

def test_a_missing_keys_directory_discovers_nothing(tmp_path) -> None:
    """A checkout with no keys folder is normal, so this answers rather than raising."""
    assert discover_graded_apps(tmp_path / "no-such-folder") == ()


def test_an_empty_keys_directory_discovers_nothing(tmp_path) -> None:
    """The folder exists and holds no key: still nothing to score, still not an error."""
    (tmp_path / "grading_keys").mkdir()
    assert discover_graded_apps(tmp_path / "grading_keys") == ()


def test_the_repositorys_own_keys_directory_agrees_with_what_is_on_disk() -> None:
    """Discovery over the real folder must not raise, and must find what is really there.

    It used to assert only that a tuple came back, which was true of the empty
    folder this project then had and would stay true if discovery started
    returning nothing at all. The pinned list of shipped apps lives in
    `test_shipped_grading_key.py`, so it is stated in one place; here the claim
    is only that discovery and the directory listing say the same thing.
    """
    on_disk = sorted(path.name.removesuffix(GROUND_TRUTH_SUFFIX)
                     for path in KEYS_DIR.glob(f"*{GROUND_TRUTH_SUFFIX}") if path.is_file())
    assert discover_graded_apps() == tuple(on_disk)


def test_a_pinned_key_is_discovered(tmp_path) -> None:
    """Guard for the two empty cases: a key that is really there is really found."""
    write_key(tmp_path, APP)
    assert discover_graded_apps(tmp_path) == (APP,)


def test_several_keys_come_back_sorted(tmp_path) -> None:
    """A fixed order keeps the scored app list independent of what the disk gives."""
    for name in ("zebra-app", "alpha-app", "middle-app"):
        write_key(tmp_path, name)
    assert discover_graded_apps(tmp_path) == ("alpha-app", "middle-app", "zebra-app")


def test_the_result_is_an_immutable_tuple(tmp_path) -> None:
    """Callers pass it around, so no caller can edit the set of scored apps in place."""
    write_key(tmp_path, APP)
    assert isinstance(discover_graded_apps(tmp_path), tuple)


def test_a_manifest_on_its_own_enrols_no_app(tmp_path) -> None:
    """A key is what makes an app gradeable; a pin beside no key grades nothing."""
    (tmp_path / f"unkeyed{MANIFEST_SUFFIX}").write_text(STUB, encoding="utf-8")
    assert discover_graded_apps(tmp_path) == ()


def test_a_baseline_file_on_its_own_enrols_no_app(tmp_path) -> None:
    """The same for a regression baseline: only `.ground_truth.json` enrols."""
    (tmp_path / f"unkeyed{BASELINE_SUFFIX}").write_text(STUB, encoding="utf-8")
    assert discover_graded_apps(tmp_path) == ()


def test_a_directory_named_like_a_key_is_not_mistaken_for_one(tmp_path) -> None:
    """A key is a file. A directory of that name is ignored, not read and not refused.

    Discovery globs names, so without an `is_file()` filter a mistyped
    directory came back as an app and then failed the pin check with "has a
    grading key but no manifest" -- a confusing answer to a typo. The real key
    beside it must still be found, or this test would pass on a discovery that
    returned nothing at all.
    """
    write_key(tmp_path, APP)
    (tmp_path / f"a-directory{GROUND_TRUTH_SUFFIX}").mkdir()
    assert discover_graded_apps(tmp_path) == (APP,)


# --- The one thing it still refuses ------------------------------------------

def test_a_key_with_no_manifest_is_refused(tmp_path) -> None:
    """An unpinned key cannot be reproduced, so it is a mistake rather than an absence."""
    write_key(tmp_path, "unpinned", with_manifest=False)
    with pytest.raises(RuntimeError):
        discover_graded_apps(tmp_path)


def test_the_refusal_names_the_app_and_the_file_it_wants(tmp_path) -> None:
    """Whoever added the key reads this, so it says which app and what is missing."""
    write_key(tmp_path, "unpinned", with_manifest=False)
    with pytest.raises(RuntimeError) as raised:
        discover_graded_apps(tmp_path)
    assert "unpinned" in str(raised.value)
    assert MANIFEST_SUFFIX in str(raised.value)


def test_the_refusal_says_why_a_pin_is_needed(tmp_path) -> None:
    """A rule with no reason gets worked around, so the message carries the reason."""
    write_key(tmp_path, "unpinned", with_manifest=False)
    with pytest.raises(RuntimeError, match="line numbers"):
        discover_graded_apps(tmp_path)


def test_one_unpinned_key_refuses_the_whole_folder(tmp_path) -> None:
    """Dropping just the bad one would score a partial set as a complete one."""
    write_key(tmp_path, APP)
    write_key(tmp_path, "unpinned", with_manifest=False)
    with pytest.raises(RuntimeError, match="unpinned"):
        discover_graded_apps(tmp_path)

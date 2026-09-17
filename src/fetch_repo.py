"""Fetches a repository by URL so it can be audited, and pins what arrived.

The one part of this project that reaches the network on purpose. An audit of
a local path still runs with every socket refused; when `main.py` is handed a
link, this fetch runs *first* and the audit that follows opens no socket of its
own -- the network lives in git's child process, and only here. Whether a URL
may be fetched at all is decided in `repo_url.py`.

The size cap bounds what is *scanned*, not what is downloaded: it is checked
once the tree is on disk, and a tree over it is removed rather than audited.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from keys.grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path
from repo_url import REQUIRED_SCHEME, destination_name, validated_url
import config

PROGRAM_NAME = "git"
TIMEOUT_SECONDS = 300

# A source tree, not a data set: anything larger is a tarball or a mistake.
BYTES_PER_MB = 1024 * 1024

# Configurable, because the right answer depends on the repository. A repo
# that ships datasets beside its source can run to gigabytes while holding
# a few thousand lines of Python, and `repo_loader` already skips a file
# over a megabyte and anything that is not source -- so the cost of a large
# tree is disk, not scan time.
MAX_TREE_BYTES = config.get_int("AUDITOR_MAX_TREE_MB") * BYTES_PER_MB

# Its own root, so a fetch never lands on a tree someone is grading: a grading
# key cites line numbers against one commit, and a fetch over it would rot
# every one of them.
DOWNLOAD_ROOT = Path("fetched")
# Removed once the commit is read. Not `repo_url.GIT_SUFFIX`, which trims the
# same four characters off a URL -- a different job with the same spelling.
HISTORY_DIR = ".git"
FETCHED_ROLE = "fetched_for_audit"
DEFAULT_PATH = "/usr/bin:/bin"
# What a reader cannot recover from the tree once the history is gone.
MANIFEST_NOTE = ("Fetched for audit at this commit; the history was removed "
                 "afterwards, so this file is the only record of it.")

# Shallow and tagless: the audit reads a working tree, not a history.
CLONE_ARGUMENTS = ("clone", "--depth", "1", "--no-tags", "--quiet")

# Belt and braces: an allow-list on our side does not bind the program we hand
# the URL to, so the transport is pinned in git's own terms as well. This is
# also what stops an https URL being redirected to http.
PROTOCOL_ARGUMENTS = (
    "-c", "protocol.allow=never",
    "-c", f"protocol.{REQUIRED_SCHEME}.allow=always",
)


def _environment() -> dict[str, str]:
    """A scrubbed environment: no user or system config, no credential prompt.

    An `insteadOf` line in either config rewrites a URL that already passed
    validation, and both are read whatever the arguments say, so pointing them
    at os.devnull is what makes the URL check hold.
    """
    return {
        "PATH": os.environ.get("PATH", DEFAULT_PATH),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }


def _run(arguments: list[str], cwd: Path | None = None) -> str:
    """Run one git command in a scrubbed environment, raising with its own message."""
    if shutil.which(PROGRAM_NAME) is None:
        raise RuntimeError(f"{PROGRAM_NAME} is not installed - see the README prerequisites")
    try:
        done = subprocess.run(
            [PROGRAM_NAME, *PROTOCOL_ARGUMENTS, *arguments],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
            check=False, cwd=cwd, env=_environment(),
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{PROGRAM_NAME} timed out after {TIMEOUT_SECONDS}s") from error
    if done.returncode != 0:
        raise RuntimeError(f"{PROGRAM_NAME} {arguments[0]} failed: {done.stderr.strip()}")
    return done.stdout


def tree_bytes(root: Path) -> int:
    """Total size of every regular file in a tree, without following symlinks."""
    return sum(path.stat().st_size for path in root.rglob("*")
               if path.is_file() and not path.is_symlink())


def _check_size(destination: Path) -> None:
    """Refuse a tree over the cap, so an enormous repository is never scanned."""
    size = tree_bytes(destination)
    if size > MAX_TREE_BYTES:
        raise ValueError(
            f"{destination.name} is {size} bytes ({size // BYTES_PER_MB} MB), over "
            f"the {MAX_TREE_BYTES} byte cap ({MAX_TREE_BYTES // BYTES_PER_MB} MB). "
            "Raise AUDITOR_MAX_TREE_MB in .env or the environment if the repository "
            "is meant to be this large: the scan reads only source files, and skips "
            "any over a megabyte, so a big tree costs disk rather than scan time.")


def read_pin(destination: Path) -> tuple[str, str]:
    """Read the commit and its date, before the history that holds them goes."""
    commit = _run(["rev-parse", "HEAD"], cwd=destination).strip()
    date = _run(["log", "-1", "--format=%cI"], cwd=destination).strip()
    return commit, date


def manifest(name: str, url: str, commit: str, commit_date: str) -> dict:
    """Pin one tree the way grading_keys/<app>.manifest.json does.

    No fetch timestamp: a commit is byte-stable, the time of day is not."""
    return {
        "name": name,
        "role": FETCHED_ROLE,
        "upstream_url": url,
        "upstream_commit": commit,
        "upstream_commit_date": commit_date,
        "note": MANIFEST_NOTE,
    }


def write_manifest(root: Path, document: dict) -> Path:
    """Write one pin beside the tree it describes, and return where it went."""
    path = manifest_path(root, document["name"])
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


def _pin_for(app_dir: Path) -> Path | None:
    """The file that says which commit this tree should be, or None if nothing does.

    The fetch manifest first, because the tool wrote it. Then the grading key's,
    because a key is the stronger claim: it says which commit its line numbers
    were read at, and a hand-cloned tree has no fetch manifest at all -- which
    is exactly the case that went unchecked.
    """
    fetched = manifest_path(app_dir.parent, app_dir.name)
    if fetched.is_file():
        return fetched
    graded = key_path(app_dir.name, MANIFEST_SUFFIX)
    return graded if graded.is_file() else None


def pin_document(app_dir: Path) -> dict:
    """What pins this tree, as a document, or an empty one when nothing does.

    The public form of `_pin_for`, added because drafting a grading key needs
    the commit and must not form a second opinion about where it comes from.
    """
    pin = _pin_for(app_dir)
    if pin is None:
        return {}
    try:
        return json.loads(pin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _pinned_commit(pin: Path) -> str:
    """The commit a pin names, refusing a file that cannot say.

    **Two failures, not one**, and neither may be a traceback: a pin is
    hand-editable -- `grading_keys/<app>.manifest.json` is written by a person,
    and it is the fallback `_pin_for` uses -- so unreadable json and readable
    json that is not an object are both ordinary states of the file. `.get` on a
    list raised `AttributeError`, which is *not* a `ValueError`, so a caller
    catching this function's own refusals caught the first and not the second.
    Both are `ValueError` now, which is what `main.EXPECTED_FAILURES` already
    turns into a printed reason rather than a crash.
    """
    try:
        document = json.loads(pin.read_text(encoding="utf-8"))
    # `OSError` beside the parse error, which is what `pin_document` ten lines
    # above already does for this same file: a pin that cannot be *opened* --
    # permissions, a directory, a dangling link -- fails the tree check exactly
    # as a pin that cannot be parsed does, and both callers were chosen for
    # `ValueError`. Catching only the parse error left the other as a traceback.
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{pin.name} cannot be read as json: {error}. It pins the "
                         "commit this tree is checked against, so it cannot be "
                         "skipped -- fix the file") from error
    if not isinstance(document, dict):
        raise ValueError(f"{pin.name} holds {type(document).__name__}, not a json "
                         "object, so it names no commit for this tree")
    # The *field*, not just the document. Guarding the root and returning
    # whatever the member holds moves the traceback one frame: `upstream_commit:
    # 12345` came back an int and `wanted[:12]` in the caller was a `TypeError`,
    # which escapes both `main.EXPECTED_FAILURES` and `source_routes._pin_note`.
    # `grading_keys._pinned_commit` has had the right line for the same field
    # all along.
    commit = document.get("upstream_commit", "")
    return commit if isinstance(commit, str) else ""


def check_tree_matches_pin(app_dir: Path) -> str:
    """Refuse an audit of a tree that no longer matches the commit its manifest pins.

    A manifest beside a fetched tree says which commit the audit -- and any
    grading key written against it -- is valid at. Nothing checked that the tree
    still *is* that commit, and a hand-edited `requirements.txt` once turned an
    undeclared dependency into a declared, exactly-pinned one: the supply-chain
    finding changed check, the advisory join fired on the injected pin, and the
    emitted OpenVEX document asserted a CVE against a third party's named commit
    that was not true of it. `test_no_mutation.py` could not catch that -- it
    proves the *tool* writes nothing, and a person had done the editing.

    Returns a note when the tree cannot be checked, which is the common case:
    `_fetch_into` deletes `.git` after pinning, so a tool-fetched tree has no
    history to compare against. Silence would read as a passed check.
    """
    pin = _pin_for(app_dir)
    if pin is None:
        return ""
    wanted = _pinned_commit(pin)
    if not (app_dir / HISTORY_DIR).is_dir():
        return (f"{app_dir.name} is pinned to {wanted[:12]} and carries no history, "
                "so the tree cannot be checked against it")
    head, _date = read_pin(app_dir)
    if head != wanted:
        raise ValueError(
            f"{app_dir.name} is at {head[:12]} but {pin.name} pins {wanted[:12]}. "
            "A grading key's line numbers mean nothing against a different commit")
    dirty = _run(["status", "--porcelain"], cwd=app_dir).strip()
    if dirty:
        raise ValueError(
            f"{app_dir.name} is modified against its pinned commit:\n{dirty}\n"
            "An audited repository is input. Restore it before auditing, or the "
            "findings describe a tree nobody else has")
    return ""


def manifest_path(root: Path, name: str) -> Path:
    """Where one fetched tree's pin goes: beside the tree, never inside it."""
    return root / f"{name}{MANIFEST_SUFFIX}"


def check_not_a_graded_app(name: str, keys_dir: Path | None = None) -> None:
    """Refuse a name a grading key already owns.

    `main.py` keys artifacts on the directory name alone, so a tree fetched
    under a graded app's name would write over the artifacts `evaluate.py`
    scores against that app's key. This project ships no keys, so by default
    this refuses nothing; it starts guarding the moment someone adds one.

    `keys_dir` is passed straight through: `key_path` resolves `None` to
    `KEYS_DIR` itself, so the folder is named in exactly one place.
    """
    if key_path(name, GROUND_TRUTH_SUFFIX, keys_dir).is_file():
        raise ValueError(
            f"{name!r} is the name of a graded app. Auditing a fetched tree "
            "under it would overwrite the artifacts scored against that app's "
            "grading key. Fetch it under another name")


def _fetch_into(url: str, destination: Path, root: Path) -> tuple[str, str]:
    """Clone, pin and record, removing everything written if any step fails."""
    try:
        _run([*CLONE_ARGUMENTS, url, str(destination)])
        _check_size(destination)
        commit, commit_date = read_pin(destination)
        shutil.rmtree(destination / HISTORY_DIR)
        write_manifest(root, manifest(destination.name, url, commit, commit_date))
        return commit, commit_date
    except Exception:
        # Never leave a half-fetched tree where an audit could read it and
        # report on a repository it only partly has -- nor a tree with no pin,
        # which is the one state this module refuses to start from.
        shutil.rmtree(destination, ignore_errors=True)
        manifest_path(root, destination.name).unlink(missing_ok=True)
        raise


def fetch(url: str, root: Path = DOWNLOAD_ROOT, keys_dir: Path | None = None) -> Path:
    """Clone one repository shallowly, pin what arrived, and return its directory."""
    checked = validated_url(url)
    name = destination_name(checked)
    check_not_a_graded_app(name, keys_dir)
    destination = root / name
    # Both halves, because the pin is half the artifact: a tree deleted by hand
    # leaving its pin behind would otherwise have that pin silently rewritten.
    existing = next((path for path in (destination, manifest_path(root, destination.name))
                     if path.exists()), None)
    if existing is not None:
        raise FileExistsError(
            f"{existing.resolve()} already exists; a fetch never writes over "
            "anything it did not create. Remove it, or fetch somewhere else")
    root.mkdir(parents=True, exist_ok=True)
    _fetch_into(checked, destination, root)
    return destination


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch a repository by URL so it can be audited.")
    parser.add_argument("url", help=f"{REQUIRED_SCHEME}:// URL of the repository")
    parser.add_argument(
        "--into", type=Path, default=DOWNLOAD_ROOT,
        help=f"where to put the fetched tree (default: {DOWNLOAD_ROOT})")
    return parser


def main() -> int:
    """Fetch one repository. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        destination = fetch(args.url, args.into)
    except (ValueError, FileExistsError, RuntimeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"fetched {destination}\n  audit it with: python src/main.py {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

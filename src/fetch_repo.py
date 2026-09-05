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

from grading_keys import GROUND_TRUTH_SUFFIX, MANIFEST_SUFFIX, key_path
from repo_url import REQUIRED_SCHEME, destination_name, validated_url

PROGRAM_NAME = "git"
TIMEOUT_SECONDS = 300

# A source tree, not a data set: anything larger is a tarball or a mistake.
MAX_TREE_BYTES = 500 * 1024 * 1024

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
        raise ValueError(f"{destination.name} is {size} bytes, over the "
                         f"{MAX_TREE_BYTES} byte cap")


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

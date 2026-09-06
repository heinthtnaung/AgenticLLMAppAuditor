"""One command from repository link to published reports.

`main.py` with a local path stays the pure offline audit, untouched. This
module runs only when the argument is an https:// link, and composes the
stages that already exist: fetch (or reuse a prior fetch of the same URL),
audit, author VEX, export HTML and PDF. Each stage keeps its own guarantees --
the audit itself opens no socket, and nothing here launches a process of its
own.

There is deliberately no second knob for the fetch root: `emit_vex` resolves a
fetched app's pin under `fetch_repo.DOWNLOAD_ROOT`, so a movable root would
break the pipeline's own product lookup between two of its stages.
"""

import json
import sys
from pathlib import Path

from artifacts.finding import OWASP_IDS
from grading_keys import GROUND_TRUTH_SUFFIX, key_path
from parsing.extractor import extract_repo
import fetch_repo
import key_drafting
import key_store
import emit_vex
import export_reports
from fetch_repo import (
    DOWNLOAD_ROOT, check_not_a_graded_app, fetch, manifest_path)
from repo_url import REQUIRED_SCHEME, destination_name, validated_url


def is_url(argument: str) -> bool:
    """Say whether the argument names a repository link rather than a directory.

    Stripped first, so this and `validated_url` (which also strips) agree about
    every argument -- a padded link must not be treated as a directory name.
    """
    return argument.strip().startswith(f"{REQUIRED_SCHEME}://")


def resolve_repo(argument: str) -> Path:
    """A local path as it is; a link fetched, or reused when fetched before.

    Reuse writes nothing, so `fetch_repo`'s rule that a fetch never writes over
    anything it did not create survives untouched. One of tree-and-pin present
    without the other keeps `fetch`'s own refusal.
    """
    if not is_url(argument):
        return Path(argument)
    checked = validated_url(argument)
    name = destination_name(checked)
    # The same refusal fetch makes, on the reuse path too: a tree named after a
    # graded fixture would overwrite that fixture's artifacts on every rerun.
    check_not_a_graded_app(name)
    destination = DOWNLOAD_ROOT / name
    pin = manifest_path(DOWNLOAD_ROOT, name)
    if destination.is_dir() and pin.is_file():
        return _reused(checked, destination, pin)
    return fetch(checked)


def _reused(url: str, destination: Path, pin: Path) -> Path:
    """Audit the tree this URL already fetched -- never a same-named other repo.

    Names collide by construction: the directory is the URL's last segment, so
    two owners' `repo` both land on `fetched/repo`. The pin says which one is
    actually there, and a mismatch is refused rather than silently audited.
    """
    record = json.loads(pin.read_text(encoding="utf-8"))
    # .get throughout: a hand-edited or truncated pin is refused with this
    # message rather than a KeyError traceback.
    held = record.get("upstream_url")
    if held != url:
        raise ValueError(
            f"{destination} holds {held or 'an unreadable pin'}, not {url}; "
            "remove that directory and its pin to fetch this one")
    print(f"reusing {destination}, pinned at commit "
          f"{record.get('upstream_commit', '?')} (remove it to re-fetch)")
    return destination


def publish(app_artifacts: Path, advisories_read: bool) -> None:
    """Author VEX, then export HTML and PDF.

    Each stage degrades with a printed reason. The audit already said *why*
    advisory data was missing, so a skipped VEX is a note here, never a failure
    -- and a vexctl that is installed but errors stays a real failure, because
    that one nobody has explained yet.
    """
    if not advisories_read:
        print("  no VEX: this audit read no advisory data, so there is nothing to state",
              file=sys.stderr)
    elif not emit_vex.is_available():
        print(f"  no VEX: {emit_vex.PROGRAM_NAME} is not installed - see the README "
              "prerequisites", file=sys.stderr)
    else:
        written = emit_vex.emit(app_artifacts)
        print(f"wrote {written}" if written
              else "  no VEX: no advisory findings, so no statement to make")
    exported, reason = export_reports.export_all(app_artifacts)
    for path in exported:
        print(f"wrote {path}")
    if reason:
        print(f"  export note: {reason}", file=sys.stderr)


# Everything drafting a key can fail with. It is the last stage of a run whose
# artifacts are already on disk, so none of these may change the exit code: a
# missing pin, a second run over the same app, an unreachable model and an
# unwritable folder are all reasons to say why and stop, never to lose a report
# that was already produced. `FileExistsError` is an `OSError`, so it is caught
# by the last of these rather than named twice.
DRAFTING_FAILURES = (RuntimeError, ValueError, OSError)


def draft_key(app_dir: Path, ask, keys_dir: Path | None = None) -> Path | None:
    """Draft a grading key for a fetched tree when none exists yet.

    Only for a fetched repository: a key pins line numbers to a commit, and a
    local path this project did not fetch may be at no commit at all.

    The draft goes under `grading_keys/drafts/`, which nothing discovers and git
    ignores, so it is a file a human reads and corrects -- not an answer key the
    tool has enrolled itself against. `key_drafting` says what that costs.
    """
    keys_dir = keys_dir or key_drafting.DRAFTED_KEYS_DIR
    app = app_dir.resolve().name
    already = key_store.existing(app, keys_dir)
    if already is not None:
        print(f"  no key drafted: {app} already has a draft at {already}", file=sys.stderr)
        return None
    if key_path(app, GROUND_TRUTH_SUFFIX).is_file():
        print(f"  no key drafted: {app} already has one a human maintains",
              file=sys.stderr)
        return None
    surfaces = extract_repo(str(app_dir)).surfaces
    entries = key_drafting.draft(surfaces, ask, OWASP_IDS)
    if not entries:
        print("  no key drafted: the model named no defects, and an empty key would "
              "score perfect recall over nothing", file=sys.stderr)
        return None
    pin = fetch_repo.pin_document(app_dir)
    document = key_drafting.key_document(
        app, key_drafting.anchored(entries, app_dir),
        pin.get("upstream_commit", ""), surfaces)
    return key_store.write(app, document, pin, keys_dir)

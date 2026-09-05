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

import ai_report
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
    """Author VEX, export HTML and PDF, then format the optional AI view.

    Each stage degrades with a printed reason. The audit already said *why*
    advisory data was missing, so a skipped VEX is a note here, never a failure
    -- and a vexctl that is installed but errors stays a real failure, because
    that one nobody has explained yet. The AI view comes last and never fails
    the run at all: the authoritative report is written before it is asked for.
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
    _ai_report(app_artifacts)


def _ai_report(app_artifacts: Path) -> None:
    """Format the optional AI view, degrading like the model advice does.

    A no-op when the model is unreachable or its page fails verification -- the
    authoritative report.html is already written, so this one is a bonus, never
    a reason for the run to fail.
    """
    try:
        print(f"wrote {ai_report.format_report(app_artifacts)}")
    # RuntimeError is an unreachable model, ValueError a page that failed
    # verification. A missing directory or report is deliberately NOT caught:
    # the audit wrote both moments ago, so their absence is a bug in this
    # pipeline, not a degraded environment.
    except (RuntimeError, ValueError) as error:
        print(f"  no AI report: {error}", file=sys.stderr)

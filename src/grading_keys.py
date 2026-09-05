"""Where an app's grading key lives, and which apps have one.

A grading key is this project's own hand-written record of what is really in an
audited application: `grading_keys/<app>.ground_truth.json`, with the upstream
pin and the regression baseline beside it under the same name. Nothing here
locates the audited code -- the auditor is pointed at a repository by path or
URL, so no project-owned path holds it.

`<app>` is the artifact directory name, which is the only join key: score an
app by placing a key here under the same name `main.py` wrote its artifacts
under.

**Having no keys at all is normal**, and one key ships. `damn-vulnerable-llm-agent`
was added on 2026-09-05, AI-drafted and unverified; the pinned corpus this project
once carried was removed on 2026-09-04 (see `docs/REPORT.md` Appendix A for
the pins the published numbers were measured against). Discovery therefore
returns nothing rather than raising -- a folder with no keys means there is
nothing to score, which is a different thing from a broken checkout.
"""

import json
from pathlib import Path

KEYS_DIR = Path(__file__).resolve().parents[1] / "grading_keys"

GROUND_TRUTH_SUFFIX = ".ground_truth.json"
MANIFEST_SUFFIX = ".manifest.json"
BASELINE_SUFFIX = ".baseline.json"


def key_path(app: str, suffix: str, keys_dir: Path | None = None) -> Path:
    """Return the path of one grading file for an app.

    `keys_dir` is resolved here rather than bound as a default, so `KEYS_DIR`
    stays the one place the folder is named -- a bound default cannot be
    redirected by pointing that constant somewhere else.
    """
    return (keys_dir or KEYS_DIR) / f"{app}{suffix}"


def _check_app(app: str, keys_dir: Path) -> None:
    """Reject a half-added key, loudly, rather than scoring against nothing.

    A key records line numbers against one exact commit, so a key that is not
    pinned cannot be reproduced. That is a mistake worth failing on, unlike an
    empty folder. The manifest is **read**, not merely counted: an empty or
    unparseable one pins nothing, and this refusal claims it pins something.
    """
    pin = key_path(app, MANIFEST_SUFFIX, keys_dir)
    if not pin.is_file():
        raise RuntimeError(
            f"{app} has a grading key but no {MANIFEST_SUFFIX}, so it is unpinned: "
            "a key's line numbers mean nothing without the commit they were read at")
    if not _pinned_commit(pin):
        raise RuntimeError(
            f"{pin} names no upstream_commit, so {app} is unpinned: a key's line "
            "numbers mean nothing without the commit they were read at")


def _pinned_commit(pin: Path) -> str:
    """The commit a manifest pins, or an empty string when it pins nothing.

    A file that will not parse raises here rather than falling through to
    "names no upstream_commit" -- that message would send someone looking for a
    field their file may well contain, when the problem is the syntax around it.
    """
    try:
        document = json.loads(pin.read_text(encoding="utf-8"))
    except ValueError as error:
        raise RuntimeError(f"{pin} is not readable json: {error}") from error
    except OSError as error:
        raise RuntimeError(f"{pin} cannot be read: {error}") from error
    commit = document.get("upstream_commit") if isinstance(document, dict) else None
    return commit if isinstance(commit, str) else ""


def discover_graded_apps(keys_dir: Path | None = None) -> tuple[str, ...]:
    """Find every app with a grading key, so adding one needs no edit here.

    A key in the folder is what makes an app gradeable. Nothing about the
    audited code is consulted, so an audited repository cannot enrol itself by
    shipping a file of the right name.
    """
    keys_dir = keys_dir or KEYS_DIR
    if not keys_dir.is_dir():
        return ()
    # `is_file()` matters: a *directory* named like a key would otherwise be
    # reported as an unpinned app, which is a confusing answer to a typo.
    apps = sorted(
        path.name.removesuffix(GROUND_TRUTH_SUFFIX)
        for path in keys_dir.glob(f"*{GROUND_TRUTH_SUFFIX}") if path.is_file()
    )
    for app in apps:
        _check_app(app, keys_dir)
    return tuple(apps)

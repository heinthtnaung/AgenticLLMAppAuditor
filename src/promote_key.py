"""Command line: move a corrected draft up into the grading keys a run is scored against.

    python src/promote_key.py <app>

`grading_keys/drafts/` holds keys the auditor drafted with the local model.
Nothing discovers them, git ignores them, and they change no number. This is the
step where a human takes responsibility for one: read it, correct it, then run
this. It refuses a draft that is not yet fit and says why -- see `key_promotion`
for what it checks and, more importantly, for what it deliberately does not fix
on your behalf.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from grading_keys import GROUND_TRUTH_SUFFIX, KEYS_DIR, MANIFEST_SUFFIX, key_path
import key_drafting
import key_promotion

# What the command may fail with that is the user's to fix, reported as a
# message rather than a traceback.
EXPECTED_FAILURES = (FileNotFoundError, FileExistsError, ValueError)


def _read(path: Path) -> dict:
    """One JSON document, refusing an unreadable one by name."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"{path} does not exist") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not readable json: {error}") from error


def _refuse_if_shipped(app: str) -> None:
    """A promoted key never overwrites one already being scored against."""
    if key_path(app, GROUND_TRUTH_SUFFIX).is_file():
        raise FileExistsError(
            f"{app} already has a grading key in {KEYS_DIR.name}/. Promoting over it "
            "would replace the answer every published figure was measured against. "
            "Move the existing one aside first if that is really what you want.")


def promote(app: str, drafts_dir: Path | None = None) -> Path:
    """Move a draft and its pin up a level, or refuse and say what to fix first."""
    drafts_dir = drafts_dir or key_drafting.DRAFTED_KEYS_DIR
    draft = key_path(app, GROUND_TRUTH_SUFFIX, drafts_dir)
    pin = key_path(app, MANIFEST_SUFFIX, drafts_dir)
    key_document, pin_document = _read(draft), _read(pin)
    _refuse_if_shipped(app)
    said = key_promotion.refusals(key_document, pin_document)
    if said:
        raise ValueError(f"{draft} is not ready to be a grading key:\n  - "
                         + "\n  - ".join(said))
    promoted = key_path(app, GROUND_TRUTH_SUFFIX)
    shutil.move(str(draft), str(promoted))
    shutil.move(str(pin), str(key_path(app, MANIFEST_SUFFIX)))
    return promoted


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Promote a corrected drafted grading key so runs are scored against it.")
    parser.add_argument("app", help="the app whose draft to promote")
    return parser


def main() -> int:
    """Promote one draft. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        promoted = promote(args.app)
    except EXPECTED_FAILURES as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"promoted {promoted}")
    print("  source and verified are unchanged on purpose: a key the tool drafted "
          "keeps saying so until you decide otherwise")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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

from keys.grading_keys import GROUND_TRUTH_SUFFIX, KEYS_DIR, MANIFEST_SUFFIX, key_path
from keys import key_drafting
from keys import key_promotion

# What the command may fail with that is the user's to fix, reported as a
# message rather than a traceback.
EXPECTED_FAILURES = (FileNotFoundError, FileExistsError, ValueError)


def _read(path: Path) -> object:
    """One JSON document, refusing an unreadable one by name.

    `object`, not `dict`: json holds lists and scalars too, which is exactly why
    `_object` exists below. A `-> dict` here would be a promise the function
    cannot keep, and the caller that believed it raised `AttributeError`.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    # Absence stays its own answer, because "write the draft first" is different
    # advice from "fix the draft". Everything else that stops the file opening
    # joins the parse error: this reads the same hand-edited pair
    # `key_draft_store` serves, and `EXPECTED_FAILURES` lists `ValueError`, not
    # `PermissionError`.
    except FileNotFoundError:
        raise FileNotFoundError(f"{path} does not exist") from None
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path} cannot be read as json: {error}") from error


def _object(path: Path) -> dict:
    """One json *object*, refusing a document that is readable and the wrong shape.

    `_read` guards the open and the parse; this guards what came back. Without
    it a draft holding `[]` reached `key_document.get("verified")` as an
    `AttributeError`, which `EXPECTED_FAILURES` does not list -- the same fault
    one clause over from the one this file already refuses by name.
    """
    document = _read(path)
    if not isinstance(document, dict):
        raise ValueError(f"{path} holds {type(document).__name__}, not a json object, "
                         "so it is not a grading key or a manifest")
    return document


def _refuse_if_shipped(app: str) -> None:
    """A promoted key never overwrites one already being scored against."""
    if key_path(app, GROUND_TRUTH_SUFFIX).is_file():
        raise FileExistsError(
            f"{app} already has a grading key in {KEYS_DIR.name}/. Promoting over it "
            "would replace the answer every published figure was measured against. "
            "Move the existing one aside first if that is really what you want.")


def _named(key_document: dict) -> str:
    """Who a key says checked it, in brackets, or nothing when it does not say."""
    claimed = key_document.get("verified_by")
    return f" ({claimed})" if claimed else ""


def promote(app: str, drafts_dir: Path | None = None,
            accept_verification: bool = False) -> Path:
    """Move a draft and its pin up a level, or refuse and say what to fix first.

    `accept_verification` is required when the draft claims a human checked it.
    That claim can be recorded through the web UI, which has no authentication,
    and promotion is the moment it starts bounding a figure someone publishes --
    so a local human says so here rather than inheriting it silently.
    """
    drafts_dir = drafts_dir or key_drafting.DRAFTED_KEYS_DIR
    draft = key_path(app, GROUND_TRUTH_SUFFIX, drafts_dir)
    pin = key_path(app, MANIFEST_SUFFIX, drafts_dir)
    key_document, pin_document = _object(draft), _object(pin)
    _refuse_if_shipped(app)
    if key_document.get("verified") and not accept_verification:
        raise ValueError(
            f"{draft} claims a human verified it{_named(key_document)}, and that "
            "claim can be recorded through an endpoint with no authentication. "
            "Promoting it makes it bound a published figure, so pass "
            "--accept-verification to say you stand behind it.")
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
    parser.add_argument(
        "--accept-verification", action="store_true",
        help="promote a draft that claims a human verified it. Required because "
             "that claim can be made through the web UI, which has no "
             "authentication, and promotion is where it starts bounding a "
             "published figure.")
    return parser


def main() -> int:
    """Promote one draft. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        promoted = promote(args.app, accept_verification=args.accept_verification)
    except EXPECTED_FAILURES as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"promoted {promoted}")
    # One line per field, because they are two different facts and a reader who
    # skims takes the first sentence for both.
    print("  source is unchanged: checking the entries cannot make the tool's "
          "own choice of what to include independent of the tool, so every "
          "figure this key bounds still says it was drafted")
    print("  verified is unchanged too: promotion carries the draft's own answer "
          "through rather than ticking it, and --accept-verification is what "
          "lets a draft claiming a human check past")
    return 0


if __name__ == "__main__":
    sys.exit(main())

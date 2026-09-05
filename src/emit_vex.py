"""Emits this project's own OpenVEX document from an audit's advisory findings.

A command of its own, run after an audit exactly as `src/export_reports.py` is,
so an audit needs no vexctl installed and its artifact count keeps meaning what
it meant. What to claim is decided in `artifacts/vex.py`; this module is the
part that runs the tool and touches the disk.

`vexctl` writes the document rather than this project's `json.dumps`, for the
reason that made it the right consumer for `filter`: OpenVEX is a spec this
project does not own, and a standard tool belongs between a claim and its
reader. So the key order, the `version` count and the `@id` are the tool's.

The instant is **pinned** from the advisory database's own date, not from a
clock -- the document then says when the data behind it was taken, which is the
only time it has a fact about. `TZ=UTC` is passed for a measured reason: one
field renders in the local offset without it, so two machines would otherwise
produce different bytes from identical input.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from artifacts.sarif import DRIVER_NAME
from artifacts.vex import (
    EMITTABLE_STATUSES, check_readable, pinned_epoch, to_vex_statements)
from grading_keys import MANIFEST_SUFFIX, key_path

PROGRAM_NAME = "vexctl"
TIMEOUT_SECONDS = 120
DOCUMENT_NAME = "findings.openvex.json"
FINDINGS_NAME = "findings.json"

# Where a fetched tree's pin lives, checked after a graded app's own pin.
# The fetcher's own constant, never a second "fetched" literal to drift from it.
from fetch_repo import DOWNLOAD_ROOT as FETCH_ROOT

DEFAULT_PATH = "/usr/bin:/bin"

# Enough of the digest to identify a document, as a short commit hash does.
ID_DIGEST_LENGTH = 32


def product_iri(app: str) -> str:
    """The audited app, named by where it came from and the commit it was at.

    The product is the thing being assessed, so it is the app -- not the
    component, which is a subcomponent of it.
    """
    for pin in (key_path(app, MANIFEST_SUFFIX), FETCH_ROOT / f"{app}{MANIFEST_SUFFIX}"):
        if pin.is_file():
            manifest = json.loads(pin.read_text(encoding="utf-8"))
            return f"{manifest['upstream_url']}@{manifest['upstream_commit']}"
    raise FileNotFoundError(
        f"no pin found for {app!r} in {key_path(app, MANIFEST_SUFFIX)} or "
        f"{FETCH_ROOT}; a VEX statement names the product it is about, so pass "
        "--product to say what was audited")


def document_id(product: str, epoch: str) -> str:
    """A stable id for the whole document, because vexctl's own is create-time only.

    Measured: appending statements with `add` leaves `@id` untouched, so the
    tool's id identifies the first statement rather than the document. This
    one is derived from what the document is about, so it is stable per app and
    per advisory snapshot without pretending to be a digest of the bytes.
    """
    # sha256, never Python's hash(): that is salted per process, so the id
    # would differ between two runs of the same input.
    seed = f"{product}@{epoch}".encode("utf-8")
    return (f"https://openvex.dev/docs/public/{DRIVER_NAME}-"
            f"{hashlib.sha256(seed).hexdigest()[:ID_DIGEST_LENGTH]}")


def _environment(epoch: str) -> dict[str, str]:
    """Exactly what vexctl needs to be deterministic, and nothing inherited."""
    return {
        "PATH": os.environ.get("PATH", DEFAULT_PATH),
        "TZ": "UTC",
        "SOURCE_DATE_EPOCH": epoch,
    }


def _statement_arguments(statement: dict, product: str) -> list[str]:
    """The flags for one claim: exactly the two statuses this tool may emit.

    An allow-set, not a passthrough -- `not_affected` (and every other status)
    raises here, so it can never reach vexctl however a statement was built.
    `--action-statement` is an `affected`-only field, so it is omitted when the
    status carries no verdict to act on.
    """
    status = statement["status"]
    if status not in EMITTABLE_STATUSES:
        raise ValueError(f"only {EMITTABLE_STATUSES} may be stated, got {status!r}")
    args = [
        "--product", product,
        "--subcomponents", statement["subcomponent"],
        "--vuln", statement["vulnerability"],
        "--status", status,
        "--status-note", statement["status_note"],
    ]
    if statement["action_statement"] is not None:
        args += ["--action-statement", statement["action_statement"]]
    return args


def is_available() -> bool:
    """Say whether vexctl is installed, so a caller can skip rather than crash."""
    return shutil.which(PROGRAM_NAME) is not None


def _run(arguments: list[str], epoch: str) -> str:
    """Run one vexctl command with a pinned environment, raising its own message."""
    if not is_available():
        raise RuntimeError(
            f"{PROGRAM_NAME} is not installed - see the README prerequisites")
    try:
        done = subprocess.run(
            [PROGRAM_NAME, *arguments], capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS, check=False, env=_environment(epoch),
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{PROGRAM_NAME} timed out after {TIMEOUT_SECONDS}s") from error
    if done.returncode != 0:
        raise RuntimeError(f"{PROGRAM_NAME} {arguments[0]} failed: {done.stderr.strip()}")
    return done.stdout


def write_document(statements: list[dict], product: str, epoch: str, target: Path) -> Path:
    """Author the document with vexctl: create the first claim, then append the rest."""
    if not statements:
        raise ValueError("no statements to author; vexctl needs at least one claim")
    first, rest = statements[0], statements[1:]
    _run(["create", "--author", DRIVER_NAME, "--id", document_id(product, epoch),
          "--file", str(target), *_statement_arguments(first, product)], epoch)
    for statement in rest:
        _run(["add", "--document", str(target), "--in-place",
              *_statement_arguments(statement, product)], epoch)
    return target


def emit(app_dir: Path, product: str | None = None) -> Path | None:
    """Write one app's VEX document, or None when it has nothing to state."""
    if not app_dir.is_dir():
        raise NotADirectoryError(f"cannot read {app_dir}: not a directory")
    findings = json.loads((app_dir / FINDINGS_NAME).read_text(encoding="utf-8"))
    check_readable(findings)
    epoch = pinned_epoch(findings["coverage"])
    named = product or product_iri(app_dir.name)
    statements = to_vex_statements(findings)
    if not statements:
        return None
    return write_document(statements, named, epoch, app_dir / DOCUMENT_NAME)


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Emit an OpenVEX document from an audit's advisory findings.")
    parser.add_argument("app_dir", type=Path, help="an app's artifact directory")
    parser.add_argument("--product", help="IRI of the audited app, if it has no pin on disk")
    return parser


def main() -> int:
    """Emit one document. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        written = emit(args.app_dir, args.product)
    except (NotADirectoryError, FileNotFoundError, ValueError, RuntimeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if written is None:
        print("no advisory findings, so no statement to make and no document written")
        return 0
    print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

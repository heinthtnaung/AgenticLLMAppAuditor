"""Loads the artifacts a score is computed from, and refuses to guess.

Separate from `scorer.py`, which is pure: this module is where the file I/O
lives, so the scoring itself stays testable without a filesystem.

Every absence is an error rather than a zero. A missing findings.json scored as
"nothing found" would read as a perfect-precision run over an app that was
never audited, which is the worst number this project could produce.

A grading key is **hand-placed input** since the pinned corpus was removed, so
its shape is checked here rather than trusted. `scorer.py` is pure and reads
the key's fields directly; a key missing one would raise a `KeyError` naming a
field, from inside the scorer, which tells whoever wrote the key nothing.
"""

import json
from pathlib import Path

from evaluation.document import AGENTIC_AUDITOR, build_evaluation
from evaluation.scorer import score_app
from grading_keys import GROUND_TRUTH_SUFFIX, key_path

FINDINGS_NAME = "findings.json"
SURFACES_NAME = "surfaces.json"
EVALUATION_NAME = "evaluation.json"

# What `scorer.py` reads off a key. Listed here, at the I/O edge, so a
# hand-written key is refused with a message naming what it is missing.
KEY_FIELDS = (
    "schema_version", "upstream_commit", "source", "verified", "verified_by",
    "verified_date", "findings", "findings_complete", "expected_surfaces_complete",
)
# The ground_truth.json shape the scorer knows how to read.
KEY_SCHEMA_VERSION = 2

# The entry fields whose absence would raise: `scorer.py` and `grading.py` both
# subscript these unguarded. A deliberate **subset** of the eight `SCHEMAS.md`
# requires -- the job is to turn a crash into a message, not to restate the
# schema, so `title`, `description` and `code_anchor` go unchecked. The guarded
# counterpart is `grading.GUARDED_ENTRY_FIELDS`, beside the reads it describes,
# and `tests/evaluation/test_entry_field_cover.py` enforces the split.
ENTRY_FIELDS = ("id", "file", "line", "owasp_id")

# Every top-level field the scorer subscripts off each artifact. Derived from
# `scorer.py` rather than chosen, and a test asserts the derivation both ways.
# Only the top level: `coverage.advisory_data` and the rest of its members stay
# unguarded, because an artifact this project wrote is trusted below the root.
FINDINGS_FIELDS = ("coverage", "findings", "model_run", "probes", "schema_version")
SURFACES_FIELDS = ("skipped_files", "surfaces")


def _read(path: Path, what: str, system: str = AGENTIC_AUDITOR) -> dict:
    """Read one artifact, saying which one is missing rather than failing vaguely."""
    if not path.is_file():
        raise FileNotFoundError(
            f"cannot score without {what}: {path} does not exist. "
            f"Run {system} over this app first."
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not readable json: {error}") from error


def _check_key(key: object, path: Path) -> dict:
    """Refuse a key the scorer would misread, naming the fault rather than raising deep."""
    if not isinstance(key, dict):
        raise ValueError(f"{path} must hold a grading key object, got {type(key).__name__}")
    missing = [field for field in KEY_FIELDS if field not in key]
    if missing:
        raise ValueError(f"{path} is missing {', '.join(missing)}; see docs/SCHEMAS.md")
    if key["schema_version"] != KEY_SCHEMA_VERSION:
        raise ValueError(
            f"{path} is schema_version {key['schema_version']!r}; the scorer reads "
            f"{KEY_SCHEMA_VERSION}")
    if not isinstance(key["findings"], list):
        raise ValueError(f"{path} has a non-list findings; a key lists what is really there")
    for position, entry in enumerate(key["findings"]):
        _check_entry(entry, position, path)
    return key


def _check_entry(entry: object, position: int, path: Path) -> None:
    """Refuse one malformed finding entry, saying which one and what it lacks."""
    where = f"{path} findings[{position}]"
    if not isinstance(entry, dict):
        raise ValueError(f"{where} must be an object, got {type(entry).__name__}")
    missing = [field for field in ENTRY_FIELDS if field not in entry]
    if missing:
        raise ValueError(f"{where} is missing {', '.join(missing)}; see docs/SCHEMAS.md")


def _check_artifact(document: object, fields: tuple[str, ...], path: Path) -> dict:
    """Refuse an artifact missing a field the scorer reads, rather than failing inside it."""
    if not isinstance(document, dict):
        raise ValueError(f"{path} must hold an object, got {type(document).__name__}")
    missing = [field for field in fields if field not in document]
    if missing:
        raise ValueError(f"{path} is missing {', '.join(missing)}; regenerate it")
    return document


def load_app(app: str, artifacts_dir: Path, system: str = AGENTIC_AUDITOR,
             keys_dir: Path | None = None) -> tuple[dict, dict, dict]:
    """Return the grading key and the two artifacts one app is scored from.

    `system` only names the producer in the error message. The path already
    carries it: the caller passes `artifacts/<system>`, which is what keeps the
    scoring itself identical for every system.
    """
    path = key_path(app, GROUND_TRUTH_SUFFIX, keys_dir)
    findings_path = artifacts_dir / app / FINDINGS_NAME
    surfaces_path = artifacts_dir / app / SURFACES_NAME
    return (
        _check_key(_read(path, f"a grading key for {app}"), path),
        _check_artifact(_read(findings_path, f"{app}'s findings", system),
                        FINDINGS_FIELDS, findings_path),
        _check_artifact(_read(surfaces_path, f"{app}'s surfaces", system),
                        SURFACES_FIELDS, surfaces_path),
    )


def score_apps(apps: list[str], artifacts_dir: Path,
               system: str = AGENTIC_AUDITOR, keys_dir: Path | None = None) -> dict:
    """Score every named app and return the evaluation document.

    Every named app is scored or the whole run fails. An app whose key is there
    and whose artifacts are not is a *hard* error, never a quiet skip: a
    partial run that produced a complete-looking score is the one outcome this
    module exists to prevent.
    """
    if not apps:
        raise ValueError("no grading key found, so there is nothing to score")
    scored = [score_app(app, *load_app(app, artifacts_dir, system, keys_dir))
              for app in sorted(apps)]
    return build_evaluation(scored, system)


def evaluation_to_json(document: dict) -> str:
    """Serialise the evaluation to its stable on-disk form."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def write_evaluation(document: dict, artifacts_dir: Path) -> Path:
    """Write the evaluation beside the per-app artifacts and return where it went.

    One file per system per run, so it sits at `artifacts/<system>/` rather
    than under any one app: a comparison across apps is not a per-app fact.
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / EVALUATION_NAME
    path.write_text(evaluation_to_json(document), encoding="utf-8")
    return path

"""Loads the artifacts a score is computed from, and refuses to guess.

Separate from `scorer.py`, which is pure: this module is where the file I/O
lives, so the scoring itself stays testable without a filesystem.

Every absence is an error rather than a zero. A missing findings.json scored as
"nothing found" would read as a perfect-precision run over an app that was
never audited, which is the worst number this project could produce.
"""

import json
from pathlib import Path

from corpus_paths import GROUND_TRUTH_SUFFIX, evidence_path
from evaluation.document import AGENTIC_AUDITOR, build_evaluation
from evaluation.scorer import score_app

FINDINGS_NAME = "findings.json"
SURFACES_NAME = "surfaces.json"
EVALUATION_NAME = "evaluation.json"


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


def load_app(app: str, artifacts_dir: Path,
             system: str = AGENTIC_AUDITOR) -> tuple[dict, dict, dict]:
    """Return the grading key and the two artifacts one app is scored from.

    `system` only names the producer in the error message. The path already
    carries it: the caller passes `artifacts/<system>`, which is what keeps the
    scoring itself identical for every system.
    """
    key_path = evidence_path(app, GROUND_TRUTH_SUFFIX)
    return (
        _read(key_path, f"a grading key for {app}"),
        _read(artifacts_dir / app / FINDINGS_NAME, f"{app}'s findings", system),
        _read(artifacts_dir / app / SURFACES_NAME, f"{app}'s surfaces", system),
    )


def score_apps(apps: list[str], artifacts_dir: Path,
               system: str = AGENTIC_AUDITOR) -> dict:
    """Score every named app and return the evaluation document."""
    if not apps:
        raise ValueError("no apps to score; the corpus is empty or none is downloaded")
    scored = [score_app(app, *load_app(app, artifacts_dir, system)) for app in sorted(apps)]
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

"""Where the corpus keeps audited code, and where it keeps the evidence about it.

`corpus/<app>/` is a byte-identical copy of upstream at its pinned commit and is
never written to. Everything this project authored about an app lives apart from
it, in `corpus/evidence/`, named `<app>.<kind>.json`.

Only the evidence is committed. The app's source is third-party code,
downloaded with the command in the README, so this repository holds no other
project's code.

Keeping them apart is what lets "pinned at commit X" mean exactly that, and it
means a downloaded repository can never be graded as a fixture no matter what
files it happens to ship.
"""

from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus"
EVIDENCE_DIR = CORPUS_DIR / "evidence"

GROUND_TRUTH_SUFFIX = ".ground_truth.json"
MANIFEST_SUFFIX = ".manifest.json"
BASELINE_SUFFIX = ".baseline.json"

# `evidence` is a directory under corpus/, so no audited app may take the name.
RESERVED_APP_NAMES = frozenset({"evidence"})


def evidence_path(app: str, suffix: str, evidence_dir: Path = EVIDENCE_DIR) -> Path:
    """Return the path of one evidence file for an app."""
    return evidence_dir / f"{app}{suffix}"


def app_path(app: str, corpus_dir: Path = CORPUS_DIR) -> Path:
    """Return the directory holding an app's audited source."""
    return corpus_dir / app


# Shown whenever a fixture is missing, so nobody has to go looking for it.
DOWNLOAD_HINT = "the app is not downloaded yet - see 'Downloading the app' in README.md"


def _check_app(app: str, evidence_dir: Path) -> None:
    """Reject a half-added fixture, loudly, rather than grading against nothing."""
    if app in RESERVED_APP_NAMES:
        raise RuntimeError(f"{app!r} is reserved: corpus/{app} holds evidence, not an audited app")
    if not evidence_path(app, MANIFEST_SUFFIX, evidence_dir).is_file():
        raise RuntimeError(f"{app} has a grading key but no {MANIFEST_SUFFIX}, so it is unpinned")


def app_is_present(app: str, corpus_dir: Path = CORPUS_DIR) -> bool:
    """Say whether the audited app's source has been downloaded yet.

    Its absence is normal: the source is third-party and is not committed.
    """
    return app_path(app, corpus_dir).is_dir()


def discover_corpus_apps(corpus_dir: Path = CORPUS_DIR, evidence_dir: Path | None = None) -> tuple[str, ...]:
    """Find every signed-off fixture, so adding one needs no edit here.

    A grading key in the evidence directory is what makes an app a fixture.
    Nothing inside `corpus/<app>/` is consulted, so a checked-out repository
    cannot enrol itself by shipping a file of the right name.
    """
    evidence_dir = evidence_dir if evidence_dir is not None else corpus_dir / EVIDENCE_DIR.name
    apps = sorted(
        path.name.removesuffix(GROUND_TRUTH_SUFFIX)
        for path in evidence_dir.glob(f"*{GROUND_TRUTH_SUFFIX}")
    )
    if not apps:
        raise RuntimeError(
            f"no grading key matching *{GROUND_TRUTH_SUFFIX} under {evidence_dir}. "
            "The fixtures are missing, so the suite would test nothing."
        )
    for app in apps:
        _check_app(app, evidence_dir)
    return tuple(apps)

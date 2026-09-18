"""Command line entry point: audit one repository and write what was found.

What can be produced depends on what is available. The surfaces and the AI
inventory need nothing but the source; the bill of materials needs an external
generator and a dependency manifest this project knows how to read. Producing
less is a normal outcome and is reported, not treated as a failure.
"""

import argparse
import subprocess
import sys
from pathlib import Path

import audit_run
import pipeline
from reporting import progress


# The auditor is one of four scored systems, so its artifacts live under its
# own name: a baseline's findings.json must not overwrite the auditor's. The
# literal is deliberately not imported from `evaluation.document` -- that keeps
# the evaluation package out of the auditor's imports, since the tool being
# scored should not reach into the thing scoring it. A test asserts the two
# agree, so the copy cannot drift.
DEFAULT_ARTIFACTS_DIR = Path("artifacts") / "agentic_auditor"


# Conditions the user can fix, reported as a message rather than a traceback.
EXPECTED_FAILURES = (FileNotFoundError, FileExistsError, NotADirectoryError,
                     ValueError, RuntimeError)


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line arguments."""
    parser = argparse.ArgumentParser(description="Audit an LLM application's source.")
    parser.add_argument("repo_path", help="path to the repository to analyse, or an "
                        "https:// link to fetch, audit, and publish in one run")
    parser.add_argument(
        "--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR,
        help=f"where to write the artifacts (default: {DEFAULT_ARTIFACTS_DIR})",
    )
    parser.add_argument(
        "--drafts-dir", type=Path, default=None,
        help="where `--draft-key` writes the drafted key (default: "
             "grading_keys/drafts/). Given a directory of its own, a run keeps "
             "its own key instead of sharing one with every other run of the "
             "same app",
    )
    parser.add_argument(
        "--semantic-probe", action="store_true",
        help="ask the local model to judge each prompt template for injection. "
             "Off by default: it puts model-authored findings in findings.json, "
             "which is otherwise byte-identical whether a model ran or not. It "
             "is also the switch that lets the model choose the check order, "
             "recorded in planner.json",
    )
    parser.add_argument(
        "--draft-key", action="store_true",
        help="after the audit, ask the LOCAL model to draft a grading key for this "
             "app when none exists, into grading_keys/drafts/. Off by default: it "
             "costs a model call and a default audit is meant to stay fast and "
             "static. The draft is a starting point for a human to correct, not an "
             "answer -- see promote_key.py",
    )
    parser.add_argument(
        "--compare-models", action="store_true",
        help="audit the tree twice, once with the local model and once with a "
             "hosted one, draft a grading key if none exists, and score both. "
             "IMPLIES --semantic-probe, without which the two arms make no model "
             "calls and produce identical findings. SENDS THE AUDITED REPOSITORY'S "
             "SOURCE to a third party: prompt templates, file paths, line numbers "
             "and code snippets. Three of four model-driven stages follow the "
             "hosted model; the knowledge-base embeddings stay local.",
    )
    parser.add_argument(
        "--model", default=None,
        help="the local model to audit with, from those Ollama has already "
             "pulled (default: AUDITOR_MODEL from the environment or .env). "
             "findings.json records whichever answered, so a named model is as "
             "reproducible as the default one.",
    )
    parser.add_argument(
        "--cloud-model", default=None,
        help="the hosted model for --compare-models (default: OPENROUTER_MODEL "
             "from the environment or .env)",
    )
    return parser


def _draft_key(app_dir: Path, model: str | None = None,
               drafts_dir: Path | None = None) -> None:
    """Draft a grading key, never letting the attempt cost the run its report.

    Last stage of a run whose artifacts are already written, so every failure
    here is a printed reason and an exit code of zero. Without this a second run
    over the same app would raise `FileExistsError`, which `EXPECTED_FAILURES`
    turns into exit 1 -- an audit that succeeded, reported as a failure. That
    collision is what `--drafts-dir` removes rather than survives: given a
    directory of its own, a run drafts its own key instead of finding one
    already there.

    Works on any tree that is pinned, not just a fetched one: a key's line
    numbers mean nothing without the commit they were read at, and
    `key_store.write` says exactly that when it cannot find one.
    """
    try:
        drafted = pipeline.draft_key(app_dir, audit_run.local_model(True, model)["ask"],
                                     drafts_dir)
    except pipeline.DRAFTING_FAILURES as error:
        print(f"  no key drafted: {error}", file=sys.stderr)
        return
    if drafted is not None:
        print(f"wrote {drafted}")
        print("  a draft, not an answer: read it before scoring anything against it")


def run(args: argparse.Namespace,
        on_stage: progress.StageListener | None = None) -> dict:
    """Audit the repository and write its artifacts. Returns what it produced.

    The result dict -- app name, artifacts directory, whether advisories were
    read, wall clock -- not an exit code. `main` turns it into one. A caller
    that is not a command line needs to know *where the artifacts went*, and
    re-deriving that means duplicating `audit_run`'s own naming or resolving
    the repository a second time.

    `--compare-models` takes a different path entirely: two audits, a drafted
    key and two scores. It is not a variation on one audit, so it does not try
    to be one -- but it keeps this promise, returning the local arm's result
    with the hosted arm under `comparison`, because a caller that cannot tell
    which path ran cannot handle two shapes. An ordinary audit sets that key to
    None: one arm ran, which is not the same as a second arm finding nothing.

    Times itself: "audit execution time" is one of the measures the proposal
    committed to, and a wall-clock second is the only honest unit here -- the
    run shells out to Syft and Trivy and may call a local model, so CPU time
    would understate what a reader actually waits for.
    """
    # Handed down, never chosen here: the command line passes none and prints,
    # the web wrapper passes one and shows an audit advancing. Neither knows
    # about the other.
    if args.compare_models:
        # Imported here, not at module scope: `cloud_client` is the second
        # module in `src/` that can open a socket, and an ordinary audit must
        # not so much as construct it. The import is the flag's boundary.
        import compare_run
        return compare_run.run(args.repo_path, args.artifacts_dir,
                               args.cloud_model, args.model, on_stage,
                               args.drafts_dir)
    app_dir = pipeline.resolve_repo(args.repo_path, on_stage)
    audit_run.report_pin_gap(app_dir)
    result = audit_run.audit(app_dir, args.artifacts_dir,
                             audit_run.local_model(args.semantic_probe, args.model),
                             on_stage)
    # A link runs the whole pipeline; a local path stays the offline audit.
    if pipeline.is_url(args.repo_path):
        pipeline.publish(result["artifacts"], result["advisories_read"], on_stage)
    # Asked for, never assumed. Drafting costs a model call, and a default audit
    # is meant to be fast and to make the same artifacts whether a model was
    # running or not. It is also the one place the model authors ground truth,
    # which is worth a flag a reader can see in the command they typed.
    if args.draft_key:
        _draft_key(app_dir, args.model, args.drafts_dir)
    # Printed, never written into an artifact: a duration is the one number here
    # that changes on every run, and putting it in a file would break the
    # byte-identical guarantee every artifact makes for a fact about the
    # machine rather than about the audited app.
    print(f"audit completed in {result['seconds']:.2f} seconds")
    return {**result, "comparison": None}


def main() -> int:
    """Audit a repository. Returns the process exit code."""
    args = build_parser().parse_args()
    try:
        run(args)
        return 0
    except (*EXPECTED_FAILURES, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Audits one repository twice -- local model, then hosted -- and scores both.

What `--compare-models` does. The two arms differ by model and by nothing else:
the same tree, the same checks, the same order of operations, so a difference in
the artifacts is a difference the model made.

**Three of the auditor's four model-touching stages follow the flag.** The
planner's check order, the semantic probe and the remediation advice take the
model they are given. One does not: the knowledge-base embeddings
(`retrieval/retrieve.py`) run on a local embedding model. So the cloud arm is a
cloud audit in the parts a model can change a finding, and local in the part
that only retrieves. Saying "cloud audit" without that sentence would overclaim.

**What leaves the machine on the cloud arm**: the audited repository's own
content. Prompt template source text, surface ids -- which spell file paths,
line numbers, kinds and names -- finding titles and evidence, and code
snippets in the advice prompts. That is the audited app's source going to a
third party, and it is why this is a flag and not a default.
"""

import json
import sys
from pathlib import Path

from artifacts.finding import OWASP_IDS
from evaluation.document import AGENTIC_AUDITOR, CLOUD_AUDITOR
from evaluation.harness import score_apps, write_evaluation
from parsing.extractor import extract_repo
from keys.grading_keys import GROUND_TRUTH_SUFFIX, key_path
import audit_run
import cloud_client
import fetch_repo
from keys import key_drafting
from keys import key_store
import pipeline
from reporting import progress

def cloud_artifacts_dir(local_dir: Path) -> Path:
    """Where the hosted arm writes: beside the local arm, under its own system name.

    Derived rather than fixed. It was `Path("artifacts") / CLOUD_AUDITOR`, a
    constant, which meant every compare run of one app wrote the hosted arm to
    the same directory however `--artifacts-dir` moved the local one -- so a
    caller that isolated its runs isolated one arm of two. Deriving it keeps the
    two arms apart, keeps each scored under the name of the model that produced
    it, and is **byte-identical for the command line**: the default local
    directory is `artifacts/agentic_auditor`, whose parent is `artifacts`, so
    this still returns `artifacts/cloud_auditor`.
    """
    return local_dir.parent / CLOUD_AUDITOR


def cloud_arm(model: str | None = None) -> dict:
    """The hosted model, and what an artifact should record about it.

    No digest: OpenRouter names a model but not the weights behind it, and a
    field left null is honest where a made-up one would not be.
    """
    named = model or cloud_client.default_model()
    # Resolved now, not at the first request: without it the run drafts a key,
    # audits twice and publishes a cloud arm whose model_run names a model that
    # was never reached. `api_key` refuses by variable name, never by value.
    cloud_client.api_key()
    return {"ask": lambda prompt: cloud_client.ask(prompt, named),
            "identifier": named, "settings": cloud_client.DECODE_SETTINGS,
            "digest": None}


def ensure_key(app: str, app_dir: Path, model: dict,
               drafts_dir: Path | None = None) -> Path | None:
    """Draft a grading key with the local model when none exists, and return its path.

    Circular by construction -- see `key_drafting`. Returns None when the model
    named nothing, because an empty key scores perfect recall over no entries,
    which is worse than not scoring at all.
    """
    shipped = key_path(app, GROUND_TRUTH_SUFFIX)
    if shipped.is_file():
        # `check_not_a_graded_app` guards the URL path only, so a local clone
        # of a graded app reaches here. Drafting anyway would score the app
        # against a key the tool wrote for itself AND overwrite
        # `artifacts/<system>/evaluation.json` -- the file `evaluate.py`
        # produces from the real key -- replacing a published figure with one
        # measured against something else. Measured: it did exactly that.
        raise ValueError(
            f"{app} already has a grading key at {shipped}, so drafting one would "
            "score it against a key written by the system being scored and would "
            f"overwrite the evaluation produced from the real one. Audit it normally "
            "and score it with `python src/evaluate.py`.")
    drafts_dir = drafts_dir or key_drafting.DRAFTED_KEYS_DIR
    already = key_store.existing(app, drafts_dir)
    if already is not None:
        print(f"  using the drafted key already at {already}")
        return already
    surfaces = extract_repo(str(app_dir)).surfaces
    entries = key_drafting.draft(surfaces, model["ask"], OWASP_IDS)
    if not entries:
        print("  no grading key drafted: the model named no defects, and an empty "
              "key would score perfect recall over nothing", file=sys.stderr)
        return None
    pin = fetch_repo.pin_document(app_dir)
    document = key_drafting.key_document(
        app, key_drafting.anchored(entries, app_dir), pin.get("upstream_commit", ""),
        surfaces)
    # The directory resolved above, not the shared constant: this is the write,
    # and pointing it at `grading_keys/drafts/` is what made every run of an app
    # share one key.
    path = key_store.write(app, document, pin, drafts_dir)
    print(f"  drafted a grading key at {path} with {len(entries)} entries -- "
          "tool_drafted and unverified, so every figure it produces carries "
          "key_drafted_by_scored_system")
    return path


def score_both(app: str, local_dir: Path, drafts_dir: Path | None = None) -> None:
    """Score both arms against the drafted key, each under its own system name.

    `local_dir` is whatever `--artifacts-dir` named, not the default: scoring a
    fixed path would read an directory the local arm never wrote to.
    """
    for system, directory in ((AGENTIC_AUDITOR, local_dir),
                              (CLOUD_AUDITOR, cloud_artifacts_dir(local_dir))):
        document = score_apps([app], directory, system,
                              drafts_dir or key_drafting.DRAFTED_KEYS_DIR)
        path = write_evaluation(document, directory)
        print(f"  scored {system}: {path}")


def run(repo_path: str, artifacts_dir: Path, cloud_model: str | None = None,
        local_model_name: str | None = None,
        on_stage: progress.StageListener | None = None,
        drafts_dir: Path | None = None) -> dict:
    """Fetch, draft a key, audit twice, publish both, and score both.

    Returns the local arm's four keys with the hosted arm under `comparison`,
    which is the shape `main.run` promises on every path. The local arm is the
    one that answers to `--artifacts-dir`; the hosted arm writes beside it,
    under `cloud_artifacts_dir`, and is the comparison.

    **`on_stage` reaches the local arm only, and that is the whole design.**
    Until 2026-09-18 it reached neither: this function did not take a listener,
    so a `--compare-models` run announced nothing and the web page rendered all
    eight stages as never reached -- work that had happened twice, shown as
    work that never started. Threading it into *both* arms would be worse than
    the bug: the listener appends, so the page would receive sixteen
    announcements for eight stages, and `StageProgress` reads "which stage is
    working" as `index === announced.length`, which walks off the end of the
    list on the ninth. One arm announcing matches the record it is stored in --
    the row carries the local arm's result, with the hosted arm under
    `comparison`.
    """
    cloud_client.reset_exposure()
    app_dir = pipeline.resolve_repo(repo_path, on_stage)
    audit_run.report_pin_gap(app_dir)
    app = app_dir.resolve().name
    # The local arm honours `--model` like every other path: without this it
    # audited with the configured model while the command line said otherwise.
    local, cloud = audit_run.local_model(True, local_model_name), cloud_arm(cloud_model)

    print(f"drafting a grading key for {app} with {local['identifier']}")
    key = ensure_key(app, app_dir, local, drafts_dir)

    print(f"\nauditing with {local['identifier']} (local)")
    local_result = audit_run.audit(app_dir, artifacts_dir, local, on_stage)
    pipeline.publish(local_result["artifacts"], local_result["advisories_read"],
                     on_stage)

    print(f"\nauditing with {cloud['identifier']} (hosted)")
    cloud_result = audit_run.audit(app_dir, cloud_artifacts_dir(artifacts_dir), cloud)
    pipeline.publish(cloud_result["artifacts"], cloud_result["advisories_read"])

    if key is not None:
        print("\nscoring both arms against the drafted key")
        score_both(app, artifacts_dir, drafts_dir)
    _summarise(local_result, cloud_result, key)
    # Both arms, not just the one `--artifacts-dir` named. The hosted arm was
    # audited, published and scored and then thrown away here, so nothing but
    # this function's own printed summary ever saw it -- which is why the web
    # UI has never been able to show a comparison it ran.
    return {**local_result, "comparison": cloud_result}


def _summarise(local_result: dict, cloud_result: dict, key: Path | None) -> None:
    """Say where everything went, and what the comparison does and does not cover."""
    print(f"\nlocal  {local_result['artifacts']}  ({local_result['seconds']:.2f}s)")
    print(f"cloud  {cloud_result['artifacts']}  ({cloud_result['seconds']:.2f}s)")
    if key is None:
        print("no scores: no grading key was drafted")
    else:
        # Read off the key rather than spelled: `source` and `verified` are two
        # independent fields, and a draft a human has since checked says so.
        print(f"key    {key}  ({_standing(key)})")
    print("\nThe two arms differ in the planner's order, the semantic probe and the "
          "advice. The knowledge-base embeddings are local in both.")
    _report_exposure()


def _standing(key: Path) -> str:
    """What a key says about itself: who chose the entries, and whether one was read.

    Guarded, though the key was drafted moments ago: `draft_key` returns a key
    that already existed just as readily as one it wrote, so this can be a file
    a person has edited since. Both faults are `ValueError`, which `main` prints
    as a reason -- a bare read meant the *summary line*, printed after both
    audits had already succeeded, could end the run in a traceback.

    Spelled locally rather than importing `harness._read`, which is private to
    the scorer. That is the fifth copy of this guard in `src/`; `docs/TODO.md`
    records that it belongs in one module.
    """
    try:
        document = json.loads(key.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{key} cannot be read as json: {error}") from error
    if not isinstance(document, dict):
        raise ValueError(f"{key} holds {type(document).__name__}, not a json object, "
                         "so it is not a grading key")
    checked = "verified" if document.get("verified") else "unverified"
    return f"{document.get('source')}, {checked}"


def _report_exposure() -> None:
    """Say how much of the audited app went to a third party on this run.

    The request bodies only, and every request that left -- including one that
    timed out, because the bytes went whether or not an answer came back. The
    API key travels in a header and is deliberately not in this figure.

    What it cannot tell you is on the second line, and it is the part that
    matters: retention, training use, and which upstream provider OpenRouter
    routed to are not knowable from this side at all.
    """
    sent, requests = cloud_client.exposure()
    print(f"\nTotal bytes exposed to cloud: {sent} in {requests} request(s)")
    print("  the audited app's own source -- prompt text, file paths, line numbers, "
          "finding titles and code snippets")
    print("  not measurable from here: retention, training use, and which upstream "
          "provider served the request")

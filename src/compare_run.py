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

# Both arms' artifacts, kept apart so neither overwrites the other and each is
# scored under the name of the model that produced it.
CLOUD_ARTIFACTS_DIR = Path("artifacts") / CLOUD_AUDITOR


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


def ensure_key(app: str, app_dir: Path, model: dict) -> Path | None:
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
    already = key_store.existing(app, key_drafting.DRAFTED_KEYS_DIR)
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
    path = key_store.write(app, document, pin, key_drafting.DRAFTED_KEYS_DIR)
    print(f"  drafted a grading key at {path} with {len(entries)} entries -- "
          "tool_drafted and unverified, so every figure it produces carries "
          "key_drafted_by_scored_system")
    return path


def score_both(app: str, local_dir: Path) -> None:
    """Score both arms against the drafted key, each under its own system name.

    `local_dir` is whatever `--artifacts-dir` named, not the default: scoring a
    fixed path would read an directory the local arm never wrote to.
    """
    for system, directory in ((AGENTIC_AUDITOR, local_dir),
                              (CLOUD_AUDITOR, CLOUD_ARTIFACTS_DIR)):
        document = score_apps([app], directory, system, key_drafting.DRAFTED_KEYS_DIR)
        path = write_evaluation(document, directory)
        print(f"  scored {system}: {path}")


def run(repo_path: str, artifacts_dir: Path, cloud_model: str | None = None) -> dict:
    """Fetch, draft a key, audit twice, publish both, and score both.

    Returns the **local** arm's result, so this path keeps the same promise
    `main.run` makes on every other path: a caller that is not a command line
    gets the app name and where its artifacts went. The local arm is the one
    that answers to `--artifacts-dir`; the hosted arm is the comparison, and
    what it found is printed rather than returned.
    """
    cloud_client.reset_exposure()
    app_dir = pipeline.resolve_repo(repo_path)
    audit_run.report_pin_gap(app_dir)
    app = app_dir.resolve().name
    local, cloud = audit_run.local_model(), cloud_arm(cloud_model)

    print(f"drafting a grading key for {app} with {local['identifier']}")
    key = ensure_key(app, app_dir, local)

    print(f"\nauditing with {local['identifier']} (local)")
    local_result = audit_run.audit(app_dir, artifacts_dir, local)
    pipeline.publish(local_result["artifacts"], local_result["advisories_read"])

    print(f"\nauditing with {cloud['identifier']} (hosted)")
    cloud_result = audit_run.audit(app_dir, CLOUD_ARTIFACTS_DIR, cloud)
    pipeline.publish(cloud_result["artifacts"], cloud_result["advisories_read"])

    if key is not None:
        print("\nscoring both arms against the drafted key")
        score_both(app, artifacts_dir)
    _summarise(local_result, cloud_result, key)
    return local_result


def _summarise(local_result: dict, cloud_result: dict, key: Path | None) -> None:
    """Say where everything went, and what the comparison does and does not cover."""
    print(f"\nlocal  {local_result['artifacts']}  ({local_result['seconds']:.2f}s)")
    print(f"cloud  {cloud_result['artifacts']}  ({cloud_result['seconds']:.2f}s)")
    if key is None:
        print("no scores: no grading key was drafted")
    else:
        print(f"key    {key}  (tool_drafted, verified: false)")
    print("\nThe two arms differ in the planner's order, the semantic probe and the "
          "advice. The knowledge-base embeddings are local in both.")
    _report_exposure()


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

"""Runs the semantic probe with a local and a hosted model, and compares them.

Objective 5 of the proposal: whether an open-weight model run locally competes
with a hosted frontier one. This is the study, not the tool -- it drives the
auditor through the `model_ask_fn` seam `run_checks.build_findings` already
exposes, so no module under `src/` changes and the audit path stays offline.

**What it compares, and what it cannot.** The static checks use no model, so the
only model-dependent detection is the semantic probe. The honest measurement is
therefore *per prompt template*: which templates each model calls injectable,
and with what reasoning. The grading-key score is reported too, but its ceiling
is one entry -- the probe's whole contribution -- so it is the weaker number of
the two. Latency is confounded by network and provider queue, and the hosted
side has no `seed`, so one cloud run is one sample.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cloud_client                                             # noqa: E402
import model_client                                             # noqa: E402
from agreement import partition                                  # noqa: E402
from artifacts.surface import Surface                           # noqa: E402
from checks.run_checks import build_findings                    # noqa: E402
from artifacts.finding import CONFIRMED                          # noqa: E402
from checks.semantic_probe import CHECK_NAME as PROBE           # noqa: E402
from comparison_report import to_page                            # noqa: E402
from exposure import UNMEASURABLE, Ledger                        # noqa: E402
from parsing.extractor import extract_repo                      # noqa: E402
from prompt_kinds import classify                                # noqa: E402

# A document without this is not readable: the shape changed once already, and
# two incompatible files sit in `experiments/results/` with no way to tell them
# apart. Study output, deliberately not one of the audit artifacts -- the hosted
# arm has no seed and `seconds` is wall clock, so it is not byte-identical.
SCHEMA_VERSION = 1

# Every subject lands in exactly one of these, and they must sum to what was
# seen. Named once so the check and the report cannot drift apart.
BUCKETS = ("agreements", "disagreements", "not_put_to_a_model",
           "not_examined_by_every_arm")


def _arm(name: str, ask: Callable[[str], str], settings: dict,
         repo: str, surfaces: list[Surface]) -> dict:
    """Run one model over the app and record what its probe concluded."""
    ledger = Ledger()

    def watched(prompt: str) -> str:
        # Classified, not assumed: `build_findings` drives the planner through
        # this same seam, and calling every prompt a probe prompt is what made
        # a run claim it had sent template text when it had sent none.
        ledger.record(prompt, classify(prompt))
        return ask(prompt)

    started = time.monotonic()
    document, _planner = build_findings(
        repo, surfaces, None, model_ask_fn=watched,
        probe_model={"identifier": name, "settings": settings, "digest": None})
    elapsed = time.monotonic() - started
    probes = [p for p in document["probes"] if p["probe_name"] == PROBE]
    return {
        "model": name,
        "seconds": round(elapsed, 2),
        "verdicts": {p["subject_id"]: p["outcome"] for p in probes},
        "details": {p["subject_id"]: p["detail"] for p in probes},
        # Carried so a reader can tell "the model said safe" from "no model was
        # asked": a concluded probe may hold no reason, so both are needed.
        "reasons": {p["subject_id"]: p["reason"] for p in probes},
        "findings": sorted(f["finding_id"] for f in document["findings"]
                           if f["rule_id"] == PROBE),
        "exposure": ledger.summary(),
    }


def compare(repo: str, cloud_models: list[str]) -> dict:
    """Run the local model and each hosted model over one repository."""
    surfaces = extract_repo(repo).surfaces
    arms = [_arm(model_client.MODEL, model_client.ask,
                 model_client.DECODE_SETTINGS, repo, surfaces)]
    for name in cloud_models:
        arms.append(_arm(name, lambda prompt, m=name: cloud_client.ask(prompt, m),
                         cloud_client.DECODE_SETTINGS, repo, surfaces))
    result = {"schema_version": SCHEMA_VERSION, "repository": repo, "arms": arms,
              **partition(arms), "unmeasurable_exposure": list(UNMEASURABLE)}
    _check_partition(result)
    return result


def _check_partition(result: dict) -> None:
    """Refuse a document whose buckets do not add up to the subjects seen.

    The rule `evaluation.json` follows: a count cannot be published without the
    others that give it its denominator, so a bucket silently losing a subject
    is an error here rather than a smaller number in a report.
    """
    counted = sum(len(result[bucket]) for bucket in BUCKETS)
    if counted != result["subjects_seen"]:
        raise ValueError(f"the comparison sorted {counted} subjects but saw "
                         f"{result['subjects_seen']}; every subject must land in "
                         f"exactly one of {BUCKETS}")


def _note(result: dict) -> str:
    """One line saying what the comparison established, or that it established nothing."""
    if not result["agreements"] and not result["disagreements"]:
        return ("**No template was put to a model, so nothing here compares them.** "
                "Each subject was either settled before a model was asked or not seen "
                "by every model -- see which below. This run says nothing about either model.")
    if not result["disagreements"]:
        return ("**The models agreed on every template both were asked about.** "
                "Agreement is not proof of correctness: both could be wrong the same way.")
    return ("**They disagree, so at most one is right.** A verdict here is a claim about "
            "the *template's structure* -- whether it drops a value into instruction text "
            "with nothing separating the two -- not about whether the application is "
            "vulnerable. Read each model's reasoning below against the template itself.")


def _print(result: dict) -> None:
    """Report the comparison, and what it could not compare, on the same screen."""
    compared = len(result["agreements"]) + len(result["disagreements"])
    print(f"{result['repository']}: {result['subjects_seen']} prompt template(s), "
          f"{compared} put to a model\n")
    for arm in result["arms"]:
        flagged = sum(1 for v in arm["verdicts"].values() if v == CONFIRMED)
        # The request count travels with the byte count: "2970 bytes sent" alone
        # is what let a planner prompt be read as one probe request per template.
        print(f"  {arm['model']:34} {flagged} flagged of {len(arm['verdicts'])}, "
              f"{arm['seconds']:>6.2f}s, {arm['exposure']['bytes_sent']} bytes over "
              f"{arm['exposure']['requests']} request(s)")
    # All four counts together: quoting the agreement alone would hide that
    # nothing was compared, which is the defect this shape exists to prevent.
    print(f"\n  agree {len(result['agreements'])}, "
          f"disagree {len(result['disagreements'])}, "
          f"no model asked {len(result['not_put_to_a_model'])}, "
          f"not seen by every model {len(result['not_examined_by_every_arm'])}"
          f"  (of {result['subjects_seen']})")
    for row in result["disagreements"]:
        said = "  ".join(f"{m.split('/')[-1]}={v}" for m, v in row["verdicts"].items())
        print(f"    {row['subject']}\n      {said}")


def main() -> int:
    """Compare a local and a hosted model over one repository."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo_path")
    parser.add_argument("--cloud-model", action="append", dest="cloud_models",
                        help="repeatable; defaults to OPENROUTER_MODEL from the environment "
                             "or .env, else " + cloud_client.FALLBACK_MODEL)
    parser.add_argument("--out", type=Path, help="write the full comparison as JSON")
    parser.add_argument(
        "--html", type=Path,
        help="write a readable comparison page. Deliberately NOT report.html: that "
             "artifact is the audit, is byte-identical run to run, and stays local-only "
             "whether or not a key is set")
    args = parser.parse_args()
    try:
        result = compare(args.repo_path,
                         args.cloud_models or [cloud_client.default_model()])
    except (RuntimeError, ValueError) as error:
        # ValueError too: `classify` and `_check_partition` raise it deliberately,
        # and a refusal to account for a prompt is a message, not a traceback.
        print(f"error: {error}", file=sys.stderr)
        return 1
    _print(result)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {args.out}")
    if args.html:
        args.html.write_text(to_page(result, _note(result)))
        print(f"wrote {args.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

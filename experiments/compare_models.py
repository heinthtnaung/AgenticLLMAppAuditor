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
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cloud_client                                             # noqa: E402
import model_client                                             # noqa: E402
from artifacts.surface import Surface                           # noqa: E402
from checks.run_checks import build_findings                    # noqa: E402
from exposure import UNMEASURABLE, Ledger                        # noqa: E402
from parsing.extractor import extract_repo                      # noqa: E402

PROBE = "semantic_probe"


def _arm(name: str, ask, settings: dict, repo: str, surfaces: list[Surface]) -> dict:
    """Run one model over the app and record what its probe concluded."""
    ledger = Ledger()

    def watched(prompt: str) -> str:
        ledger.record(prompt, "probe prompt")
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
        "findings": sorted(f["finding_id"] for f in document["findings"]
                           if f["rule_id"] == PROBE),
        "exposure": ledger.summary(),
    }


def compare(repo: str, cloud_model: str) -> dict:
    """Run both arms over one repository and return the comparison."""
    surfaces = extract_repo(repo).surfaces
    local = _arm(model_client.MODEL, model_client.ask,
                 model_client.DECODE_SETTINGS, repo, surfaces)
    cloud = _arm(cloud_model, lambda prompt: cloud_client.ask(prompt, cloud_model),
                 cloud_client.DECODE_SETTINGS, repo, surfaces)
    subjects = sorted(set(local["verdicts"]) | set(cloud["verdicts"]))
    return {
        "repository": repo,
        "templates_examined": len(subjects),
        "arms": [local, cloud],
        "agreements": [s for s in subjects
                       if local["verdicts"].get(s) == cloud["verdicts"].get(s)],
        "disagreements": [{"surface": s, "local": local["verdicts"].get(s),
                           "cloud": cloud["verdicts"].get(s)} for s in subjects
                          if local["verdicts"].get(s) != cloud["verdicts"].get(s)],
        "unmeasurable_exposure": list(UNMEASURABLE),
    }


def _print(result: dict) -> None:
    """Report the comparison, leading with the per-template agreement."""
    print(f"{result['repository']}: {result['templates_examined']} prompt templates\n")
    for arm in result["arms"]:
        flagged = sum(1 for v in arm["verdicts"].values() if v == "confirmed")
        print(f"  {arm['model']:34} {flagged} flagged, {arm['seconds']:>6.2f}s, "
              f"{arm['exposure']['bytes_sent']} bytes sent")
    print(f"\n  agree on {len(result['agreements'])} of {result['templates_examined']}, "
          f"disagree on {len(result['disagreements'])}")
    for row in result["disagreements"]:
        print(f"    {row['surface']}: local={row['local']} cloud={row['cloud']}")


def main() -> int:
    """Compare a local and a hosted model over one repository."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo_path")
    parser.add_argument("--cloud-model", default=cloud_client.DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, help="write the full comparison as JSON")
    args = parser.parse_args()
    try:
        result = compare(args.repo_path, args.cloud_model)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    _print(result)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

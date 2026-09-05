#!/usr/bin/env bash
#
# Reproduce every figure in docs/REPORT.md from a clean checkout.
#
#   ./reproduce.sh
#
# Needs: .venv, Ollama with qwen2.5-coder:7b-instruct, Syft, Trivy.
# Optional: OPENROUTER_API_KEY in .env or the environment, for Objective 5.
# Without it the script still completes and says which step it skipped.

set -euo pipefail

APP="damn-vulnerable-llm-agent"
PIN="c0cf9a14adad76e9d6a53c41741f625334bd9971"
URL="https://github.com/ReversecLabs/${APP}.git"
TREE="fetched/${APP}"
ART="artifacts/agentic_auditor/${APP}"

green() { printf '\033[0;32m%s\033[0m\n' "$1"; }
step()  { set +x; printf '\n\033[1m== %s\033[0m\n' "$1"; set -x; }

cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .venv/bin/activate

set -x

# 1. The app, at the commit the grading key was written against. Cloned rather
#    than fetched by URL: main.py refuses to fetch under a graded app's name,
#    because that would overwrite the artifacts scored against its key.
step "Fetching ${APP} at ${PIN:0:12}"
if [ ! -d "$TREE" ]; then
  git clone --quiet "$URL" "$TREE"
  git -C "$TREE" checkout --quiet "$PIN"
fi

# The audit refuses a tree that drifted from its pin, so check here for a
# clearer message than a mid-run failure.
if [ -d "$TREE/.git" ]; then
  test "$(git -C "$TREE" rev-parse HEAD)" = "$PIN"
  test -z "$(git -C "$TREE" status --porcelain)"
fi

step "Auditing with the semantic probe"
python src/main.py "$TREE" --semantic-probe

step "Running both baselines"
python src/run_baseline.py baseline_static_rules "$TREE"
python src/run_baseline.py baseline_sbom_only "$TREE"

step "Scoring all three systems"
python src/evaluate.py
python src/evaluate.py --system baseline_static_rules
python src/evaluate.py --system baseline_sbom_only

# 5. Objective 5 needs a hosted model. A placeholder key is worse than none --
#    it fails authentication and, under `set -e`, would abort before the summary.
step "Objective 5: local versus hosted model"
if python -c "import sys; sys.path.insert(0,'experiments'); import cloud_client; cloud_client.api_key()" 2>/dev/null; then
  python experiments/compare_models.py "$TREE" \
    --out "${ART}/model-comparison.json" \
    --html "${ART}/comparison.html"
  COMPARISON="written to ${ART}/comparison.html"
else
  COMPARISON="SKIPPED: no OPENROUTER_API_KEY in .env or the environment"
fi

set +x
echo
green "All artifacts, metrics and comparisons generated."
echo
echo "  audit + probe   ${ART}/report.md"
echo "  scores          artifacts/agentic_auditor/evaluation.json"
echo "                  artifacts/baseline_static_rules/evaluation.json"
echo "                  artifacts/baseline_sbom_only/evaluation.json"
echo "  objective 5     ${COMPARISON}"
echo
echo "Every score carries key_ai_drafted and key_unverified: the grading key is"
echo "AI-drafted and verified:false. See docs/REPORT.md."

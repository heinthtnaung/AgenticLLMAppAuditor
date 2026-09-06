# Agentic LLM-App Auditor

Audits a single LLM application repository and reports findings mapped to the
OWASP Top 10 for LLM Applications, backed by SBOM/AIBOM evidence.

Runs **offline** with a local model. It reports; it never patches, commits, or
runs the code it audits.

## Risks it covers

From the **2025** OWASP list (the edition matters — supply chain is LLM03 now,
LLM05 before):

| Risk | Check | What it proves |
|---|---|---|
| LLM01 prompt injection | `taint.py` | An untrusted value reaches a model |
| LLM01 (opt-in) | `semantic_probe.py` | A prompt template interpolates a value with no delimiter |
| LLM02 output handling | `output_handling.py` | A query is built by string interpolation |
| LLM03 supply chain | `supply_chain.py`, `known_advisory.py` | A package is undeclared, or carries a known CVE and a surface reaches it |
| LLM06 excessive agency | `permissions.py` | A tool grants shell, interpreter or network reach |
| AUDITABILITY | `auditability.py` | An agent is built with no callback or handler |

LLM02 is the **2023** spelling of improper output handling; 2025 numbers it
LLM05. AUDITABILITY is this project's own category, not a stock OWASP entry.

Each check's title says what it establishes, not what its risk class implies.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Optional, each degrades with a printed reason if absent: **Syft** (SBOM),
**Trivy** (advisories), **vexctl** (OpenVEX), **Ollama** with
`qwen2.5-coder:7b-instruct` (advice and the probe).

## Use

```bash
python src/main.py https://github.com/owner/app.git   # fetch, audit, report
python src/main.py path/to/app                        # audit a local tree
python src/main.py path/to/app --semantic-probe       # + ask the model about prompt templates
```

Writes 11 artifacts to `artifacts/agentic_auditor/<app>/`. Start with
`report.md`.

Other commands:

```bash
python src/evaluate.py                    # score against grading_keys/
python src/run_baseline.py baseline_static_rules <app>
python src/emit_vex.py artifacts/agentic_auditor/<app>
python src/export_reports.py artifacts/agentic_auditor/<app>
python src/index_knowledge.py             # build the advice knowledge base
python src/ai_report.py artifacts/agentic_auditor/<app>   # optional AI-styled view
python src/fetch_repo.py <url>            # fetch and pin a repo without auditing
python src/model_client.py                # check the local model answers
```

`report.ai.html` is a presentation of `report.md`, not an authority: it is
model-written, non-deterministic, and refused whole if it invents an advisory.

## Reproduce everything

```bash
./reproduce.sh
```

Clones the app at its pinned commit, audits it with the probe, runs both
baselines, scores all three, and — if `OPENROUTER_API_KEY` is set — runs the
local-versus-hosted comparison.

Regenerates every detection and latency figure in `docs/REPORT.md`. **Not the
Objective 5 numbers**: those were measured over two other applications, one of
which is not pinned by any grading key, so the script cannot reproduce them.

Without a key it completes anyway and says which step it skipped. A placeholder
key would be worse than none: it fails authentication and, under `set -e`, would
abort before the summary.

## Worked example

`damn-vulnerable-llm-agent` is a deliberately vulnerable LangChain ReAct agent,
and the app this project is measured against.

```bash
# 1. get it at the commit the grading key pins
git clone https://github.com/ReversecLabs/damn-vulnerable-llm-agent.git \
  fetched/damn-vulnerable-llm-agent
cd fetched/damn-vulnerable-llm-agent
git checkout c0cf9a14adad76e9d6a53c41741f625334bd9971
cd ../.. && rm -rf fetched/damn-vulnerable-llm-agent/.git

# 2. audit it
python src/main.py fetched/damn-vulnerable-llm-agent

# 3. score it against the shipped grading key
python src/evaluate.py

# 4. compare against the baselines
python src/run_baseline.py baseline_static_rules fetched/damn-vulnerable-llm-agent
python src/evaluate.py --system baseline_static_rules
```

Expect 6 findings and **3 of 8** matched. `--semantic-probe` adds a model's
opinion on prompt templates; on this app it adds no finding.
Read `artifacts/agentic_auditor/damn-vulnerable-llm-agent/report.md`.

Two things that will silently spoil it: **editing the app's
`requirements.txt`** (the tree stops matching the pin and the supply-chain
finding disappears), and **leaving `.git` in place** (git commands inside then
resolve to the clone rather than this repo).

`main.py` also takes the URL directly, but not for this app — the name belongs
to a grading key, and the tool refuses to overwrite artifacts scored against
one.

## What it found

On `damn-vulnerable-llm-agent` at commit `c0cf9a14`, scored against
`grading_keys/`:

| System | Matched |
|---|---|
| This auditor | 3 of 8 |
| grep/AST baseline | 4 of 8 |
| SBOM-only baseline | 0 of 8 |

The key is **AI-drafted and unverified**, so every figure carries
`key_ai_drafted` and `key_unverified`.

**The sets matter more than the counts.** The auditor alone reaches the
supply-chain entry — that needs joining a surface to a component, which no grep
rule has. The baseline alone reaches the system-prompt and tool-authorisation
entries, both of which are *absences* a regex catches and this auditor's
dataflow does not. **Three of the eight are reached by neither**, which is the
honest state of the tool rather than a rounding error.

**Why this tool rather than a scanner.** On a repo with no LLM surfaces, Trivy
finds 311 vulnerabilities and this auditor reports 0 findings and 79
advisory-carrying components reached by nothing. Both are correct, and the pair
is the point: this tool answers "does the LLM reach it?", not "is it
vulnerable?".

## Optional: compare a local and a hosted model

Answers the proposal's Objective 5 — can an open-weight model run locally do
this job as well as a hosted one. **Entirely optional.** With no API key nothing
changes: `report.html` holds local-model output only, as it always does, and no
audit ever reads the key.

### Setup

Put both settings in `.env` (gitignored). A real environment variable wins over
either.

```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=z-ai/glm-5.2
```

### Run

```bash
python experiments/compare_models.py fetched/<app>
```

Compares the local model against `OPENROUTER_MODEL`. To compare several at once,
`--cloud-model` repeats and overrides the default:

```bash
python experiments/compare_models.py fetched/<app> \
  --cloud-model qwen/qwen-2.5-coder-32b-instruct \
  --cloud-model z-ai/glm-5.2 \
  --out comparison.json \
  --html artifacts/agentic_auditor/<app>/comparison.html
```

`--html` writes a readable page **beside** `report.html`, never inside it: the
audit report is byte-identical run to run, and a hosted model's answer is
neither reproducible nor available without a key.

### Reading the output

```
  fetched/<app>: 5 prompt template(s), 2 put to a model     # illustrative

  qwen2.5-coder:7b-instruct     2 flagged of 5,   2.6s, 2970 bytes over 3 request(s)
  z-ai/glm-5.2                  2 flagged of 5,  29.0s, 2970 bytes over 3 request(s)

  agree 2, disagree 0, no model asked 3, not seen by every model 0  (of 5)
```

That block shows the format, not a run you can reproduce: it is hand-written
from the saved five-template study's numbers, and its byte figure is one
`docs/REPORT.md` withdraws. **Three requests for five templates** is the point —
one of them is the planner's, and three templates were never sent at all.

**All four counts print together on purpose.** Only templates every model was
actually asked about can agree or disagree; the probe settles the rest on the
text alone — a template written somewhere other than that line, or one that
interpolates nothing. Counting those as agreement is how a run that consulted
nobody once reported "agree on 5 of 5".

The page shows each model's verdict **per prompt template with its reasoning**,
because a count alone hides which model is right. See `docs/REPORT.md`.

Three things worth knowing before quoting a result:

- **Only the semantic probe is model-dependent.** Every other check uses no
  model, so this compares the one place a model can change a finding.
- **Hosted models have no `seed`.** `glm-5.2` gave different verdicts on the
  same template across runs here. One run is one sample; repeat before
  concluding.
- **Latency is not a quality signal** — it is confounded by network, provider
  queue and routing.

`experiments/` lives outside `src/`, and nothing under `src/` may import it, so
the audit path stays offline. A test asserts both directions.

## Guarantees

- **Never executes the audited app.** `test_no_mutation.py` hashes the tree
  before and after; `test_no_write_commands.py` refuses write-capable
  subprocesses.
- **The audit path opens no socket** except to local Ollama. `model_client.py`
  is the only module under `src/` that connects, asserted as an exact set. The
  one exception is `experiments/`, the local-vs-cloud study, which is not part
  of the tool and which nothing under `src/` may import.
- **The model never decides what counts as a finding.** It writes advice, may
  order and narrow the plan, and judges prompt templates behind an opt-in flag.
- **Artifacts are byte-identical** run to run, except model-authored prose,
  `planner.json`'s order, and probe findings — all inert by default.

## Docs

| File | What |
|---|---|
| `docs/SCHEMAS.md` | The artifact contracts |
| `docs/REPORT.md` | Results and limitations |
| `docs/TODO.md` | Open work |
| `docs/HISTORY.md` | What was built, in order |
| `docs/PROPOSAL_COVERAGE.md` | Every proposal commitment, answered |
| `docs/CODING_RULES.md` | The 20 binding rules |

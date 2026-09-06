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

## Prerequisites

**Required.** Nothing else is needed to get surfaces, findings and a report.

| | | |
|---|---|---|
| Python | **3.10+** | modern type hints (`list[Path]`) |
| `git` | any | only for fetching a repository by URL |
| the packages in `requirements.txt` | pinned exactly | tree-sitter (JS/TS parsing), langgraph, fpdf2, chromadb |

Versions are pinned with `==`, not `>=`, on purpose: a tree-sitter grammar
update renames node types, which would silently change `surfaces.json` — the
artifact every published number is computed from.

**Optional.** Each one is absent-tolerant: the audit still completes, prints why
the stage was skipped, and produces fewer artifacts. None of them is needed to
try the tool.

| Tool | Install | Without it |
|---|---|---|
| **Syft** | `brew install syft` / [releases](https://github.com/anchore/syft/releases) | no `sbom.json`, no `mapping.json`, so no supply-chain findings |
| **Trivy** | `brew install trivy` / [releases](https://github.com/aquasecurity/trivy/releases) | no advisory findings; `coverage` says the data was not ingested |
| **Ollama** + `qwen2.5-coder:7b-instruct` | `ollama pull qwen2.5-coder:7b-instruct` | no remediation advice, no `--semantic-probe`, no `--draft-key` |
| **vexctl** | [releases](https://github.com/openvex/vexctl/releases) | no `findings.openvex.json` |
| **DejaVu font** | usually already present on Linux | HTML reports still written, PDFs skipped |
| An **OpenRouter key** | in `.env` | `--compare-models` refuses; nothing else notices |

## Install

```bash
git clone <this repo> && cd AgenticLLMAppAuditor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Check the local model answers, if you installed Ollama:

```bash
python src/model_client.py
```

## Step by step

**1 — audit something.** A URL is fetched at its current commit and pinned; a
local path is read where it is.

```bash
python src/main.py https://github.com/owner/app.git
```

Writes 11 artifacts to `artifacts/agentic_auditor/<app>/`. **Start with
`report.md`.** The run prints what it could not do — a missing Syft, an
unreachable model — rather than failing.

**2 — look at the evidence behind a finding.**

```
report.md            what was found, in prose, with the line and why it matters
findings.json        the same, as data; `coverage` says which checks could look
surfaces.json        every LLM surface found, and every file skipped
mapping.json         which surface reaches which dependency
remediation.md       per-finding advice, attributed to the passages that grounded it
```

**3 — turn on the optional model checks.** Off by default so an ordinary audit
is fast and produces the same artifacts whether a model was running or not.

```bash
python src/main.py <repo> --semantic-probe   # ask the model to judge prompt templates
python src/main.py <repo> --draft-key        # draft a grading key for a human to correct
```

**4 — export and publish.** Separate commands, because the audit itself opens no
socket and needs no renderer.

```bash
python src/export_reports.py artifacts/agentic_auditor/<app>   # HTML and PDF
python src/emit_vex.py artifacts/agentic_auditor/<app>         # OpenVEX, needs vexctl
```

**5 — score it, if you have a grading key.** A key is a human's answer for one
app; `grading_keys/README.md` says how to write one.

```bash
python src/evaluate.py                                    # the auditor
python src/run_baseline.py baseline_static_rules <repo>   # a comparison baseline
python src/evaluate.py --system baseline_static_rules
```

**6 — accept a drafted key**, once you have corrected it. This is the step that
makes a draft count: it refuses one that is not yet fit and says which of the
reasons.

```bash
python src/promote_key.py <app>
```

**Grounding the advice (optional, once).** Builds a local knowledge base from a
pinned OWASP Cheat Sheet clone, so remediation advice cites passages instead of
inventing them.

```bash
python src/index_knowledge.py
```

**Fetch without auditing**, if you want the pinned tree on disk first:

```bash
python src/fetch_repo.py <url>
```

## Settings

All optional, read from the environment first, then `.env` (gitignored). An
unknown `AUDITOR_*` name is refused rather than ignored, so a typo is loud.

| Setting | Default | |
|---|---|---|
| `AUDITOR_MODEL` | `qwen2.5-coder:7b-instruct` | the local model |
| `AUDITOR_SERVER_URL` | `http://localhost:11434/api/generate` | must stay a local address |
| `AUDITOR_TIMEOUT_SECONDS` | `120` | |
| `AUDITOR_EMBED_MODEL` | `nomic-embed-text:latest` | needs its `:tag`, or provenance comes out null |
| `AUDITOR_KNOWLEDGE_DIR` | `knowledge` | |
| `AUDITOR_MAX_TREE_MB` | `500` | raise it to audit a repo that ships datasets |
| `OPENROUTER_API_KEY` | — | `--compare-models` only; never read by an audit |
| `OPENROUTER_MODEL` | `z-ai/glm-5.2` | |

## Try it: catch a real prompt injection

`indirect-prompt-injection-poc` scrapes a web page and hands the text to a
model. Its own comments say it is vulnerable. One command:

```bash
python src/main.py https://github.com/kamranhasan/indirect-prompt-injection-poc --semantic-probe
```

The URL is fetched, pinned at its current commit, and audited — no cloning or
checking out by hand. About 26 seconds with a local model running.

```
wrote 11 artifacts to artifacts/agentic_auditor/indirect-prompt-injection-poc
audit completed in 25.95 seconds
```

Ten findings: one **LLM01** and nine **LLM03**. The LLM01 is the one worth
reading, in `report.md`:

```
LLM01  semantic_probe  app.py:77
  Prompt template interpolates a value into instruction text without delimiters
  CONFIRMED: the interpolation point `{content}` is placed inside instruction
  text with no delimiter, quoting, or system/data separation around it.
```

`app.py:77` is the line where the scraped page text reaches the model. That
prompt is written inline as a chat-message dict — `{"role": "user", "content":
f"...{content}"}` — with no name of its own, which is exactly the shape the
extractor was blind to until recently.

**What it does not find there, which is the honest half.** The *dataflow* to
that line — `requests.get` → `response.text` → `soup` → `page_text`, across two
methods, into a call whose value sits inside a list of dicts — defeats the taint
trace. The finding above comes from a model reading one line, not from following
the data. `docs/REPORT.md` says why.

Drop `--semantic-probe` and the LLM01 disappears: the probe is the only check
that asks a model anything, and it is off by default so an ordinary audit is
fast and produces the same artifacts whether a model was running or not.

### Scoring a run

Scoring needs a grading key, and this repository ships none — see *What it
found* below for the figures and the commit that holds the key they were
measured against. With a key in `grading_keys/`:

```bash
python src/evaluate.py                                        # the auditor
python src/run_baseline.py baseline_static_rules <repo>       # a baseline
python src/evaluate.py --system baseline_static_rules
```

Or let the local model draft one for you to correct, with `--draft-key`.

**One thing that will silently spoil a run:** pointing `main.py` at the
artifacts directory instead of the app. It audits that folder, finds no source,
and writes the empty result back over the real one.

## What it found

On `damn-vulnerable-llm-agent` at commit `c0cf9a14`, scored against a grading
key that **is no longer in this repository** — removed deliberately, recoverable
with `git show f9bd9ff:grading_keys/damn-vulnerable-llm-agent.ground_truth.json`.
The run happened; it is not reproducible from a clean checkout today.

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
python src/main.py <repo> --compare-models
```

Audits the tree twice — once with the local model, once with the hosted one —
publishes both, drafts a grading key if none exists, and scores both arms.

```
artifacts/agentic_auditor/<app>/   the local arm
artifacts/cloud_auditor/<app>/     the hosted arm
grading_keys/drafts/<app>.*        the key both were scored against
```

It implies `--semantic-probe`: without a model call the two arms produce
identical findings. `--cloud-model <name>` overrides `OPENROUTER_MODEL`.

**It sends the audited repository's source to a third party** — prompt text,
file paths, line numbers, surface names, finding titles and code snippets — and
prints how much at the end:

```
Total bytes exposed to cloud: 4820 in 3 request(s)
```

Request bodies only, counted before each send, so a request that timed out is
still counted. What it cannot measure is on the line beneath: retention,
training use, and which upstream provider OpenRouter routed to.

**Three of four model-driven stages follow the flag** — the planner's order, the
semantic probe and the remediation advice. The knowledge-base embeddings stay
local in both arms.

### The study behind it

`experiments/compare_models.py` is the Objective 5 write-up rather than the
tool: it runs the probe alone across several models at once and renders a page
comparing their reasoning.

```bash
python experiments/compare_models.py fetched/<app> \
  --cloud-model qwen/qwen-2.5-coder-32b-instruct \
  --cloud-model z-ai/glm-5.2 \
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

`experiments/` lives outside `src/` and nothing under `src/` may import it; a
test asserts both directions. The cloud client itself now lives in `src/`,
because `--compare-models` needs it — see Guarantees for what that costs.

## Guarantees

- **Never executes the audited app.** `test_no_mutation.py` hashes the tree
  before and after; `test_no_write_commands.py` refuses write-capable
  subprocesses.
- **An audit opens no socket** except to local Ollama. Two modules under `src/`
  can connect and the set is exact: `model_client.py` reaches Ollama on this
  machine, and `cloud_client.py` reaches OpenRouter — constructed only when
  `--compare-models` is passed, which is why `main.py` imports it inside that
  branch. A test runs a default audit and counts the sockets it attempts, so
  the narrower claim is proved rather than asserted. **This used to say one
  module. It says two now, and that is a real reduction** in what the tool
  guarantees, bought deliberately for the comparison.
- **The model never decides what counts as a finding.** It writes advice, may
  order and narrow the plan, and judges prompt templates behind an opt-in flag.
  Behind `--draft-key` it also drafts *ground truth* — the one place it decides
  what an audit is marked against, which is why that is a flag, why the draft
  lands where nothing discovers it, and why every figure such a key produces
  carries `key_drafted_by_scored_system`.
- **Artifacts are byte-identical** run to run, except model-authored prose,
  `planner.json`'s order, and probe findings — all inert by default. **Not the
  `cloud_auditor` arm**: a hosted model takes no seed, so nothing under
  `artifacts/cloud_auditor/` is reproducible byte for byte.

## Docs

| File | What |
|---|---|
| `docs/SCHEMAS.md` | The artifact contracts |
| `docs/REPORT.md` | Results and limitations |
| `docs/TODO.md` | Open work |
| `docs/HISTORY.md` | What was built, in order |
| `docs/PROPOSAL_COVERAGE.md` | Every proposal commitment, answered |
| `docs/CODING_RULES.md` | The 20 binding rules |

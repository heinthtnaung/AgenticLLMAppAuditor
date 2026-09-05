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
```

## What it found

On `damn-vulnerable-llm-agent` at commit `c0cf9a14`, scored against
`grading_keys/`:

| System | Matched |
|---|---|
| This auditor, static | 4 of 6 |
| This auditor, `--semantic-probe` | 5 of 6 |
| grep/AST baseline | 5 of 6 |
| SBOM-only baseline | 0 of 6 |

The key is **AI-drafted and unverified**, so every figure carries
`key_ai_drafted` and `key_unverified`.

**The sets matter more than the counts.** The auditor alone reaches the
supply-chain entry — that needs joining a surface to a component, which no grep
rule has. The baseline alone reaches the tool-authorisation entry. Union: all
six.

**Why this tool rather than a scanner.** On a repo with no LLM surfaces, Trivy
finds 311 vulnerabilities and this auditor reports 0 findings and 79
advisory-carrying components reached by nothing. Both are correct, and the pair
is the point: this tool answers "does the LLM reach it?", not "is it
vulnerable?".

## Guarantees

- **Never executes the audited app.** `test_no_mutation.py` hashes the tree
  before and after; `test_no_write_commands.py` refuses write-capable
  subprocesses.
- **Opens no socket** except to local Ollama. `model_client.py` is the only
  module that connects.
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

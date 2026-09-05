# What the proposal promised, and what this repository does

Written 2026-09-05. The proposal (`ci-proposal-template-(4).docx`, submitted
2026/08/26) is **not tracked in this repository**, so until now nothing let a
reader check the code against what was committed to. This file closes that gap:
every commitment below is quoted verbatim from the proposal and answered with a
file path or an admission.

**Headline: roughly 74% of the proposal's concrete commitments are delivered.**
The engineering is further along than the research design. The largest single
gap is not a missing module -- it is that the study's own central comparison was
never run.

## How the number is counted

**33 commitments, all of them rows in the tables below** -- Objectives,
Methodology, Evaluation and Dissemination. Fully delivered counts 1, partial
counts 0.5, missing counts 0. That gives **24.5 / 33 ~= 74%**, and the count is
reproducible by anyone who adds up the tables; an earlier version of this file
quoted 24.5/35 against 33 rows, which nobody could check.
Last recounted 2026-09-05 after the grading key, `ComponentRef` and the two new
AIBOM kinds landed.
Counted over the engineering commitments alone it is nearer 80%; over the
evaluation and research-design commitments alone, nearer 50%.

The split matters more than the total, so the total is given with its parts
rather than on its own.

---

## 1. The gap that matters most

> **Objective 5.** "To determine if Open weights models can compete with
> frontier AI offerings as an alternative."

> "The evaluation corpus will also compare local open-weight and **cloud-hosted
> frontier LLM configurations** under identical LLM-application security
> scenarios."

> "The study will measure ... the **data-exposure implications** of sending
> sensitive audit artefacts to an external inference provider."

**Nothing in this repository addresses any of it.** There is no cloud
configuration, no comparison harness, no second model path, and no measurement
of data exposure. `grep` for `cloud`, `frontier`, or any hosted-provider client
in `src/` returns nothing.

The tool is *architecturally* offline -- `src/model_client.py` is the only
module that opens a connection, and it talks to localhost. But that is the
**premise** of the study, not a **finding** of it. The aims section frames the
whole project as a trade-off investigation:

> "whether locally deployed models can retain adequate audit coverage, evidence
> traceability and practical security value while improving privacy, control,
> and suitability for sensitive environments"

An examiner who reads the aims and then the results will find the comparison
absent. This is one stated objective of five, and it is at 0%.

## 2. A risk class was substituted without saying so

The proposal names four risks:

> "Prompt Injection; Supply Chain Vulnerabilities; Excessive Agency and unsafe
> tool permissions; and **RAG/data-layer retrieval risks**."

The repository covers **LLM01, LLM03, LLM06, LLM02 and AUDITABILITY**
(`src/checks/run_checks.py`, `RISK_CLASS_BY_CHECK`). *Inadequate auditability of
agent actions* is this project's own invention -- `.claude/AGENTS.md` says so --
and it stands where **RAG/data-layer retrieval risk** was promised.

What exists: retrieval points *are* extracted as `DATA_SOURCE` surfaces
(`as_retriever`, `similarity_search`, `get_relevant_documents` in
`src/detectors/detector_names.py`), and `src/checks/taint.py` treats them as
untrusted sources, so indirect injection through a retrieved document is
partially reachable via LLM01.

What does not exist: any check that reports a retrieval-layer risk **as its own
class**. Retrieval poisoning, named in the corpus description, has no detector.

Counted as partial. It is worth deciding deliberately whether to build the
retrieval check or to state the substitution in the report -- the one thing that
should not happen is an examiner discovering it by diffing the two lists.

## 3. The corpus removal has a wider blast radius than it looks

> "The corpus will comprise two controlled Python-based agentic applications ...
> containing seeded prompt-injection, retrieval poisoning, excessive-agency,
> unsafe tool-use, and supply-chain-evidence scenarios."

> "The demo applications will contain ground-truth labels for vulnerable and
> non-vulnerable LLM surfaces."

> Dissemination: "A code repository containing the prototype, sample schemas,
> **reproducible demo applications**, and evaluation materials."

These were built and then removed on 2026-09-04 (`docs/TODO.md`, "Corpus
removal"). **`grading_keys/` no longer ships empty**: one key was added on
2026-09-05 for `damn-vulnerable-llm-agent`, pinned to upstream `c0cf9a14` and
cloned by URL, so measurement is possible again without this project carrying
someone else's code. It is AI-drafted and unverified, so every figure it
produces is qualified `key_ai_drafted` and `key_unverified`. The scoring machinery
(`src/evaluation/`, `src/baselines/`) is intact and tested against synthetic
data, and `docs/REPORT.md` Appendix A preserves the pins the published figures
were measured against -- so the numbers stay falsifiable by anyone willing to
re-clone.

But Month 3 of the schedule is entirely "Run the agentic auditor and baselines
over the evaluation corpus", and that cannot be redone as things stand. Every
check added since -- LLM02, AUDITABILITY, the semantic probe -- ships
**unmeasured**, and the published 2-of-6 was taken against a tool that had none
of them.

---

## 4. Commitment-by-commitment

### Data model (Methodology 1)

| Promised | Status | Where |
|---|---|---|
| `Surface` | Yes | `src/artifacts/surface.py` |
| `Finding` with severity, evidence, surface, location, remediation | Partial | `src/artifacts/finding.py`. Severity is only ever *quoted* from a named advisory source, never assigned -- a deliberate decision recorded in `docs/SCHEMAS.md`. Remediation lives in `remediation.json`, not on the finding. |
| `Component` and `ComponentRef` | Partial | **`ComponentRef` ships** (`src/artifacts/component_ref.py`) and `mapping._entry` builds one; `as_entry()` reproduces the `mapping.json` dict, so the artifact is untouched. **`Component` was written and deliberately deleted**: nothing in `src/` would have constructed one, and a class shipped only to make this row read "Yes" is dead code by this project's own rule. Counted Partial for that reason rather than quietly counted whole. |
| `GraphState` | Yes | `AuditState` in `src/checks/workflow.py` |

### Extraction and evidence (Methodology 2)

| Promised | Status | Where |
|---|---|---|
| Python `ast` extractor for LangChain/LangGraph | Yes | `src/parsing/extractor_python.py`, `src/detectors/` |
| Prompts, system messages, user-input paths, tools, graph nodes, agent definitions, model declarations, RAG/vector-store use | Partial | Four surface kinds in `src/artifacts/surface.py`. **No graph-node kind**: `add_node` is not extracted and `StateGraph` is recorded as an agent factory. User-input paths are *traced* by `src/checks/taint.py` rather than extracted as surfaces. |
| Syft, CycloneDX or SPDX | Yes | `src/deps/syft_runner.py`, `src/artifacts/sbom.py` (CycloneDX) |
| Trivy vulnerability scan | Yes | `src/deps/trivy_runner.py`, `src/checks/known_advisory.py` |
| Lightweight AIBOM (models, datasets, tools, MCP servers, agent roles) | Yes | `src/artifacts/aibom.py` records all five kinds; `DATASET` and `MCP_SERVER` were added 2026-09-05 with import-time guards tying each to a detector table. Python backend only — which is the scope the proposal set. Two known gaps are filed and xfail-pinned rather than hidden: `_kind_of` reads Python's tables whatever the language, and an MCP client given a `name=` keyword files as `TOOL`. |
| "CSAF/VEX-style JSON documents **will be parsed**" | **No** | The project *emits* OpenVEX (`src/emit_vex.py`). Reading an upstream document is explicitly out of scope -- `docs/TODO.md` Task 5.3, because no upstream document exists for any dependency. Objective 3 lists "exploitability information" as an input; it is currently only an output. |
| Surface-to-component linking heuristics | Yes | `src/artifacts/mapping.py` |

### The seven workflow nodes (Methodology 3)

| Promised node | Status | Where |
|---|---|---|
| `extract_llm_surfaces` | Yes | `src/parsing/extractor.py` (a phase, not a graph node) |
| `auditor_planner` -- "uses a local LLM and deterministic risk heuristics to choose the next surface and probe" | **Partial** | `src/checks/planner.py` is built, pure and tested, and the monotone merge is proven. Wired at the edge in `build_findings` (7.2); since 7.4 it also chooses **which surfaces each check examines**, recorded in `planner.json` and summarised in `findings.json`'s `checks_narrowed`. So "choose the next surface and probe" is delivered. Still partial on the other half of the sentence: there are **no deterministic risk heuristics**. The model ranks and selects alone; the deterministic code around it only *constrains* the choice (five containment rules) and never scores a surface for risk. |
| `trace_dataflow` | Partial | `src/checks/taint.py`. Python only -- the JS side would need the analysis rebuilt on tree-sitter -- so on a TypeScript app this node reaches nothing, in a tool that otherwise supports both. |
| `probe_injection` -- "controlled, benign direct and indirect prompt-injection tests **in a sandboxed environment**" | **Partial, by decision** | `src/checks/semantic_probe.py` asks the local model to judge a template's structure. **Nothing is executed and there is no sandbox** -- a deliberate methodological choice, argued in full in `docs/REPORT.md`'s Addendum: a dynamic test would either transmit the audited app's prompts to an external provider (the exposure this project exists to avoid) or measure `qwen2.5-coder` instead of the app, and it would cost the enforced never-executes guarantee that makes auditing an untrusted URL safe. Counted Partial because the proposal did specify a sandbox; the shortfall is stated, not silent. **Indirect injection through retrieved documents is not probed at all.** |
| `check_tool_perms` | Yes | `src/checks/permissions.py` |
| `link_supply_chain_evidence` | Yes | `src/artifacts/mapping.py` + `src/checks/known_advisory.py` |
| `assemble_report` -- JSON and Markdown/HTML | Yes | `src/report.py`, `src/markdown_html.py`, `src/export_reports.py` |

### Runtime guarantees

| Promised | Status |
|---|---|
| All inference local, via Ollama or LMStudio | Yes -- `src/model_client.py`, Ollama; enforced by `tests/parsing/test_offline*.py` |
| Human-in-the-loop; never patches, deploys or alters the target | Yes -- enforced by `tests/test_no_mutation.py` and `tests/test_no_write_commands.py` |

### Evaluation (Methodology 4)

| Promised measure | Status |
|---|---|
| Static grep/AST baseline | Yes -- `src/baselines/static_rules.py` |
| SBOM-only baseline | Yes -- `src/baselines/sbom_only.py` |
| True positives, false positives, false negatives | Yes -- `src/evaluation/scorer.py` |
| OWASP risk-category coverage | Yes -- `coverage.risk_classes_checked` |
| "percentage of findings containing valid code, SBOM/AIBOM, and CSAF/VEX evidence links" | Yes -- `src/evaluation/evidence.py`, as counts plus denominators (`evaluation.json` forbids float fields by design) |
| "precision and recall of LLM surface extraction" | **Partial** -- `expected_surfaces` explains *why a finding was missed*; extraction is not scored as its own precision/recall figure |
| "audit execution time" | Yes | `src/main.py` times each run; `docs/REPORT.md` "Audit Execution Latency" publishes the three-configuration table with a repeated measurement. |
| Local vs cloud-hosted frontier comparison | **No** -- section 1 |
| Data-exposure implications | **No** -- section 1 |
| "qualitative usefulness of reports for a human security reviewer" | **No** -- not attempted; this is a human study, not code |

### Dissemination

| Promised | Status |
|---|---|
| Academic research report | Partial -- `docs/REPORT.md` is a repository document with the measured results; the submitted academic report is separate work |
| Supervisor demonstration | Deliverable -- `python src/main.py <url>` runs the whole pipeline |
| Code repository with prototype, schemas, **reproducible demo applications**, evaluation materials | Partial -- the demo applications were removed (section 3). What ships instead is a **grading key** for a public app, pinned to upstream `c0cf9a14` and cloned by URL: `grading_keys/damn-vulnerable-llm-agent.*`. That restores measurement without shipping someone else's code, but it is AI-drafted and `verified: false`, so every figure it produces is qualified. |

---

## 5. Delivered beyond the proposal

Worth stating, because a coverage number read alone understates the work:

- **Five risk classes, where four were promised** -- LLM02 (improper output
  handling) was added on 2026-09-05.
- **JavaScript and TypeScript extraction** via tree-sitter. The proposal
  committed to Python only.
- **Knowledge-grounded remediation advice** (Phase 6): a pinned OWASP Cheat
  Sheet corpus indexed in ChromaDB, with every passage attributed in
  `remediation.json`. Not in the proposal at all.
- **Repository fetching by URL**, so the auditor runs on any repository rather
  than a fixed corpus.
- **SARIF output** beside JSON and Markdown.

## 6. What to do next, in order of what an examiner would notice

Four of the five actions this file first listed were taken on 2026-09-05, which
is why the sections above read as they do. What is left:

1. **Verify the shipped grading key.** It exists and it measures — see
   `docs/REPORT.md`, where the auditor scores 4 of 6 static and 5 of 6 with the
   probe, against 5 of 6 for the grep baseline and 0 of 6 for SBOM-only. But it
   is AI-drafted and `verified: false`, so every one of those figures carries
   `key_ai_drafted` and `key_unverified`. A human reading its six entries
   against `c0cf9a14` is what turns an indication into a result, and it is the
   cheapest remaining upgrade in the whole document.
2. **Publish an execution-time figure.** The run is timed and prints its
   duration; no number appears in `docs/REPORT.md`.
3. **Decide whether the planner should be consequential.** It chooses the order
   and records it, and the order changes no artifact unless `MAX_STEPS` binds.
   Either accept that and keep the record as provenance, or let it choose what
   to probe -- which reopens the rule that it must never subtract.

Done, and where: **Objective 5** and the **RAG/AUDITABILITY substitution** are
both now stated in `docs/REPORT.md`'s "Addendum: Methodology Deviations from
Proposal", so neither reads as an oversight. **Task 7.2** is wired, with the
caveat in item 3. **Audit execution time** is instrumented.

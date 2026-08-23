# TODO — Project Roadmap

Single source of truth for what is done and what is next.
**Update this file every time a task is finished** — tick the box in the same
change that completes the work (see rule 20 in `.claude/AGENTS.md`).

How the system currently works: [`FLOW.md`](./FLOW.md).

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Phase 0 — Decisions to lock first

- [ ] Confirm the exact 3–4 OWASP LLM Top 10 risks (proposal names: LLM01
      direct + indirect injection, LLM06 excessive agency / unsafe tool use,
      inadequate auditability) — sign this off so scope can't creep
- [x] Collect deliberately-vulnerable demo apps (2 apps, 9 planted findings,
      ground truth)
    - https://github.com/ReversecLabs/damn-vulnerable-llm-agent
    - https://github.com/13o-bbr-bbq/Broken_LLM_Integration_App
- [~] Select + verify 2–3 open-source LangGraph/LangChain apps (checklist and
      manifest template ready; live verification done by hand) — **two of the
      three are JavaScript/TypeScript**; the auditor now reads those too, and
      one has been adopted as a fixture (see below)
    - ~~https://github.com/langchain-ai/agent-chat-ui~~ — **dropped**: 56 source
      files yielding a single generic `fetch` surface. It is a frontend that
      talks to a server over `langgraph-sdk`, so it has no prompts, agents, or
      tools to audit. No parser could change that.
    - https://github.com/langchain-ai/langgraphjs-studio-starter — adopted as
      `corpus/oss-app-langgraphjs-starter` (TypeScript, 5 surfaces, no planted
      vulnerabilities, so it measures false positives on clean code)
    - https://github.com/langchain-ai/open_deep_research
- [~] Manually establish ground truth for the demo apps — drafted as
      `corpus/<app>/ground_truth.json`, 10 findings, `verified: false`.
      Needs the human second-person check. See B3.
- [ ] Manually establish ground truth for the open-source apps (read code,
      list surfaces/issues, second-person check)

---

## Phase 1 — Environment & LLM surface extractor

See `docs/PHASE_1_PLAN.md` for the task-level breakdown and done-criteria.

- [x] Set up offline model server (Ollama or vLLM) + download chosen model
      (Llama / Qwen & GLM 5.2 / Gemma 4 / Qwen-coder)
      — Ollama 0.32.15 running, `qwen2.5-coder:7b-instruct` pulled (4.4 GB),
      `python src/model_client.py` returns a reply from the local server.
- [ ] Stand up the LangGraph skeleton (shared state, planner node, bounded
      loop with step cap)
      — **not started, and believed misfiled**: this is Phase 3 work. See B4.
- [x] Build the LLM surface extractor (prompt templates, agent definitions,
      tool-call sites, prompt/tool data sources) with location recording

Phase 1 detail, per `docs/PHASE_1_PLAN.md`:

- [x] 1.1 Scaffolding — `src/ corpus/ tests/ artifacts/`, `requirements.txt`,
      `README.md`, `.venv` installs cleanly
- [x] 1.2 Offline model client — `ask()` verified against the local server
- [x] 1.3 Repo loader — `src/repo_loader.py`
- [x] 1.4 Surface data model — `src/surface.py`
- [x] 1.5 Surface extractor — `src/detectors.py` + `src/extractor.py`
- [x] 1.6 CLI entry point — `src/main.py`
- [x] Settings read from the environment (`src/config.py` + `.env.example`);
      the test corpus is discovered on disk instead of listed in code
- [x] System flow documented step by step in `docs/FLOW.md`
- [x] 1.8 Language registry (`src/languages.py`) — extension to language and
      to tree-sitter grammar, kept as two separate ideas
- [x] 1.9 JavaScript/TypeScript backend (`src/detectors_js.py`,
      `src/extractor_js.py`, `src/ts_utils.py`) via tree-sitter
- [x] 1.10 `oss-app-langgraphjs-starter` added as the clean-code fixture
- [~] 1.7 Validation — the suite is green, all 9 code-linked ground-truth
      surfaces found; the by-hand cross-check of every `ground_truth.json`
      is a human task. See B3a/B3b/B3c.

---

## Phase 2 — SBOM/AIBOM + advisory ingestion & mapping

- [ ] Generate SBOMs for each test app via Syft/Trivy (CycloneDX/SPDX JSON)
- [ ] Define the lightweight AIBOM JSON schema (models, datasets, tools,
      agents)
- [ ] Ingest CSAF/VEX-style advisories for selected components
- [ ] Build surface-to-component mapping (link each LLM surface to its
      SBOM/AIBOM components) — join on each surface's `module` field
- [ ] Decide on `artifacts/<app>/target.json` (app name + upstream commit +
      file count). Proposed during Phase 1 and **declined there** as out of
      scope: every field is already recoverable from the artifact directory
      name and `corpus/<app>/MANIFEST.json`. Revisit if Phase 2 needs the
      commit pinned next to the output.
- [ ] Detector precision follow-ups deferred from Phase 1: distinguish read
      from write in `open()`, drop message classes (`SystemMessage`,
      `HumanMessage`, `MessagesPlaceholder`) from `PROMPT_CLASSES` if they
      prove noisy on the open-source apps; the JavaScript side has the same
      `load`/`query`/`execute` breadth problem, no HTTP-route data source
      (Express/Next handlers are the main untrusted input in JS apps), and 29
      framework names no fixture exercises; one malformed `.ts` aborts a whole
      repo scan, which JS repos will hit more often than Python ones; and
      decide whether `src/` becomes
      a real package (it is currently flat, with `tests/conftest.py` adding it
      to `sys.path`). Also: a non-UTF-8 source file with no PEP 263 cookie now
      aborts the whole repo scan rather than being scanned approximately.

---

## Phase 3 — LangGraph auditor, probes & reporting

- [ ] Implement the agentic audit workflow (planner picks next probe over
      shared state)
- [ ] Implement probe: taint-style dataflow tracing (untrusted source →
      prompt/tool)
- [ ] Implement probe: benign injection tests in sandbox (direct + indirect
      via documents)
- [ ] Implement probe: static permission checks (over-privileged file/network
      tools)
- [ ] Enforce sandbox boundary (isolated instance, benign payloads only, no
      live systems)
- [ ] Build evidence-backed reporting (JSON + Markdown/HTML; each finding =
      OWASP ID + code location + LLM-surface link + SBOM/AIBOM/advisory refs)
- [ ] Confirm human-in-the-loop only (no auto-patch, no PR merge)

---

## Phase 4 — Evaluation & write-up

- [ ] Build the evaluation harness/scorer (reads `ground_truth.json`, computes
      TP/FP/FN → precision/recall/F1 per app + aggregated)
- [ ] Implement baselines: simple static rules and SBOM-only scan
- [ ] Run experiments: agentic auditor vs baselines on the full corpus
- [ ] (Optional, if RQ3 is kept) Compare model families (Gemma / Llama / Qwen)
- [ ] Analyse results (does agentic probing improve detection + explanation?)
- [ ] Write the thesis report
- [ ] Release the open-source prototype

---

## Blocked / needs a decision

Anything that stops work or needs a human call. Clear these as they are
resolved; do not tick the task above until its blocker is gone.

| # | Blocker | Who / what unblocks it |
|---|---|---|
| B3a | The two Python demo apps' `ground_truth.json` are **AI-drafted and unverified** (`verified: false`). Phase 4's precision/recall is graded against them, so no number is thesis-grade until a human confirms. | A human reads both apps and flips `verified`, `verified_by`, `verified_date`. Note the drafted count is **10** findings, not the 9 recorded in Phase 0 — confirm which is right. **Blocks Phase 4.** |
| B3b | `oss-app-langgraphjs-starter`'s ground truth is also AI-drafted. Its 5 surfaces were identified by reading `src/agent.ts` before running the extractor, so the exhaustiveness claim is independent — but still unverified. | Same human check. **Must not block Phase 2.** |
| B3c | Neither Python fixture has an **exhaustive** `expected_surfaces` list, so surface *precision* cannot be measured on them (only recall). Deriving the list from the extractor's own output would make precision trivially 100% and the metric worthless. | A human enumerates every surface in both apps by reading the code, then sets `expected_surfaces_complete: true`. |
| B4 | The Phase 1 line **"Stand up the LangGraph skeleton"** duplicates Phase 3's "agentic audit workflow (planner picks next probe over shared state)". Building it now would break rule 15. | Decide whether to move the line to Phase 3. Not implemented either way. |
| B6 | The **exact OWASP risk subset is still unsigned** (Phase 0, line 1). Scope can creep until it is. | Sign off the 3–4 risks. |
| B7 | **Phase owners are unassigned** across Hein / Bing Hong / JW. | Agree the split. |

---

## Cross-cutting / documentation

- [ ] Related-work / competitive-landscape section (verify Garak, PyRIT, Syft,
      Trivy current state — the proposal notes a search for prior DOI/arXiv
      work; document that search)
- [ ] Ethics section (offline, sandbox-only, no exploits, self-contained test
      apps)
- [ ] Team split — the proposal lists three people (Hein, Bing Hong, JW);
      assign owners per phase

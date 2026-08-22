# TODO — Project Roadmap

Single source of truth for what is done and what is next.
**Update this file every time a task is finished** — tick the box in the same
change that completes the work (see rule 20 in `.claude/AGENTS.md`).

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
- [x] Select + verify 2–3 open-source LangGraph/LangChain apps (checklist and
      manifest template ready; live verification done by hand)
    - https://github.com/langchain-ai/agent-chat-ui
    - https://github.com/langchain-ai/langgraphjs-studio-starter
    - https://github.com/langchain-ai/open_deep_research
- [ ] Manually establish ground truth for the open-source apps (read code,
      list surfaces/issues, second-person check)

---

## Phase 1 — Environment & LLM surface extractor

See `docs/PHASE_1_PLAN.md` for the task-level breakdown and done-criteria.

- [ ] Set up offline model server (Ollama or vLLM) + download chosen model
      (Llama / Qwen & GLM 5.2 / Gemma 4 / Qwen-coder)
- [ ] Stand up the LangGraph skeleton (shared state, planner node, bounded
      loop with step cap)
- [ ] Build the LLM surface extractor (prompt templates, agent definitions,
      tool-call sites, prompt/tool data sources) with location recording

---

## Phase 2 — SBOM/AIBOM + advisory ingestion & mapping

- [ ] Generate SBOMs for each test app via Syft/Trivy (CycloneDX/SPDX JSON)
- [ ] Define the lightweight AIBOM JSON schema (models, datasets, tools,
      agents)
- [ ] Ingest CSAF/VEX-style advisories for selected components
- [ ] Build surface-to-component mapping (link each LLM surface to its
      SBOM/AIBOM components)

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

## Cross-cutting / documentation

- [ ] Related-work / competitive-landscape section (verify Garak, PyRIT, Syft,
      Trivy current state — the proposal notes a search for prior DOI/arXiv
      work; document that search)
- [ ] Ethics section (offline, sandbox-only, no exploits, self-contained test
      apps)
- [ ] Team split — the proposal lists three people (Hein, Bing Hong, JW);
      assign owners per phase

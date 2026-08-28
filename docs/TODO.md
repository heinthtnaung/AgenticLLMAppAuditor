# TODO — Project Roadmap

Single source of truth for what is done and what is next.
**Update this file every time a task is finished** — tick the box in the same
change that completes the work (see rule 20 in
[`CODING_RULES.md`](./CODING_RULES.md)).

How the system works: [`FLOW.md`](./FLOW.md) · the standard it is held to:
[`CODING_RULES.md`](./CODING_RULES.md) · the JSON contracts:
[`SCHEMAS.md`](./SCHEMAS.md).

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Phase 0 — Decisions to lock first

- [x] Confirm the exact 3–4 OWASP LLM Top 10 risks (proposal names: LLM01
      direct + indirect injection, LLM06 excessive agency / unsafe tool use,
      inadequate auditability) — sign this off so scope can't creep
    - LLM01 – Prompt Injection
    - LLM03 – Supply Chain Vulnerabilities (2025 numbering; was LLM05)
    - LLM06 – Excessive Agency and Tool Permissions
    - Inadequate auditability of agent actions (not a stock OWASP entry)

      LLM08 (vector database / RAG retrieval) was considered and **dropped**:
      no corpus app performs retrieval, so its recall would be 0/0.

- [x] Collect deliberately-vulnerable demo apps (2 apps; **10** findings
      drafted, not the 9 first estimated — see B3a)
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
- [~] Manually establish ground truth for the demo app — drafted as
      `corpus/evidence/vuln-app-1-support-agent.ground_truth.json`, 5 findings,
      `verified: false`. Needs the human second-person check. See B3.
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

- [x] The audited app's source is downloaded, not committed: this repository
      holds no third-party project code, only the evidence about it. The
      README carries the pinned clone command, and tests that need the app
      skip with a pointer to it
- [x] 1.1 Scaffolding — `src/ corpus/ tests/ artifacts/`, `requirements.txt`,
      `README.md`, `.venv` installs cleanly
- [x] 1.2 Offline model client — `ask()` verified against the local server
- [x] 1.3 Repo loader — `src/repo_loader.py`
- [x] 1.4 Surface data model — `src/surface.py`
- [x] 1.5 Surface extractor — `src/detectors.py` + `src/extractor.py`
- [x] 1.6 CLI entry point — `src/main.py`
- [~] 1.7 Validation — the suite is green and every code-linked ground-truth
      surface is found *in the files the scan could read*; a scorer has to read
      `skipped_files` before treating that as recall (see `docs/SCHEMAS.md`).
      The by-hand cross-check of each grading key is a human task. See B3.
- [x] Settings read from the environment (`src/config.py` + `.env.example`);
      the test corpus is discovered on disk instead of listed in code
- [x] System flow documented step by step in `docs/FLOW.md`
- [x] 1.8 Language registry (`src/languages.py`) — extension to language and
      to tree-sitter grammar, kept as two separate ideas
- [x] 1.9 JavaScript/TypeScript backend (`src/detectors_js.py`,
      `src/extractor_js.py`, `src/ts_utils.py`) via tree-sitter
- [x] 1.10 `oss-app-langgraphjs-starter` added as the clean-code fixture
- [x] Evidence split out of the audited code: `corpus/<app>/` is now a
      byte-identical upstream copy, and everything authored about it lives in
      `corpus/evidence/`, owned by `src/corpus_paths.py`
---

## Phase 2 — SBOM/AIBOM + advisory ingestion & mapping

See [`PHASE_2_PLAN.md`](./PHASE_2_PLAN.md) for the task breakdown and
done-criteria.

- [~] Generate an SBOM via Syft. **Not** CycloneDX or SPDX as produced: that
      output carries a random id, a timestamp and absolute paths, so it cannot
      be byte-identical across runs. `sbom.json` is a normalised shape keeping
      CycloneDX field names and PURL identity. One Python app so far
- [x] Define the AIBOM schema and build it (`src/aibom.py`), derived from
      `surfaces.json` so every entry traces to a surface. `datasets` is absent:
      no surface kind produces one
- [x] Write the advisory data policy (`SCHEMAS.md`): fetched out-of-band as a
      documented manual step, read from disk, never at runtime
- [ ] Read npm manifests, so a JavaScript app can be given an SBOM. Until
      then `src/main.py` refuses one rather than reporting every real
      import as an undeclared dependency
- [ ] Build the advisory matcher — **deferred, not forgotten**: of five
      components two have no version and three are inferred from a range, so
      there is nothing an honest matcher could key on yet
- [x] Build surface-to-component mapping (`src/mapping.py`), joining on each
      surface's `module`. Five outcomes, all exercised on the corpus:
      third_party 6, stdlib 3, first_party 1, used_but_undeclared 1,
      unresolved 8. It found PyYAML used but never declared
- [x] ~~`artifacts/<app>/target.json`~~ — **declined for good.** Every field it
      would carry is already recoverable: the app name is the artifact
      directory's name, and the upstream commit and file count come from
      `corpus/evidence/<app>.manifest.json`. A second place to state the same
      facts is a second place for them to disagree. Recorded in `SCHEMAS.md`
- [x] `open()` now reports read against write, from its mode argument. An
      absent mode reads as `r`, which is Python's documented default rather
      than a guess; a mode built at runtime says so instead of guessing.
      `+` counts as a write flag: `r+` and `rb+` open a read-write handle and
      were reported as reads until that was fixed and tested
- [ ] Detector precision, deferred from Phase 1: drop `SystemMessage` /
      `HumanMessage` / `MessagesPlaceholder` from `PROMPT_CLASSES` if they
      prove noisy; the JS side has the same `load` / `query` / `execute`
      breadth problem
- [ ] Detector coverage gaps: no HTTP-route data source on the JS side, though
      Express and Next handlers are the main untrusted input in JS apps; and
      29 JS framework names no fixture exercises
- [x] Robustness: a malformed `.ts` or a non-UTF-8 Python file no longer
      aborts the scan, and an oversized file — already skipped, but only ever
      warned about — is now recorded too. The walk records the file in
      `surfaces.json`'s new `skipped_files` and carries on (`schema_version` 3).
      It goes in the artifact rather than only stderr because Phase 4 grades
      recall from that file, and a skip in a console log makes a missed surface
      indistinguishable from a detector miss. Only `UnreadableSource` is
      caught, so a detector bug stays loud — `UnicodeDecodeError` is a
      `ValueError` subclass, and a broad `except` would file a bug as a
      deliberate skip. The parser's message is deliberately not stored: its
      wording is CPython-version dependent and can contain an absolute path.
      The skip list is sorted at the walk, not only in the serialiser, so the
      warnings printed and the records written cannot disagree on order. The
      two known limits in `SCHEMAS.md` — a non-UTF-8 `.ts` file is mangled
      rather than skipped, and an unopenable file still aborts the scan — are
      pinned by `tests/parsing/test_extractor_skip_limits.py`, so changing
      either is a conscious decision with a failing test attached
- [x] ~~Make `src/` a real package~~ — **declined.** It is 24 modules in four
      folders with one entry point, and the folders are plain directories that
      Python imports without an `__init__.py`. `python src/main.py` works,
      `tests/conftest.py` handles the path, and converting would touch every
      import for no reader benefit. Recorded in `FLOW.md`

---

## Phase 3 — LangGraph auditor, probes & reporting

- [ ] Audit a repository straight from a URL, and restore corpus fixtures from
      their pinned manifests. Both were built during Phase 1 and removed again
      to keep it offline and simple. Bringing them back means bringing back the
      safety work an untrusted input needs: an https/git@ allow-list, a
      validated directory name (`.../org/..` would otherwise escape the
      download directory), skipped symlinks, no submodule recursion, and
      non-interactive git. Worth doing when the evaluation needs more than one
      app, not before.

      The reviewed implementation and its 78 offline tests are kept on the
      `phase3/url-fetcher` tag, so this is a restore rather than a rewrite:

      ```sh
      git checkout phase3/url-fetcher -- src/repo_fetcher.py \
          tests/repo_fetcher_fakes.py tests/test_repo_fetcher_*.py
      ```

      A companion `src/fetch_corpus.py`, which restored fixtures from their
      pinned manifests, was written and removed within a single change and is
      not in history. It was ~85 lines: read each `*.manifest.json`, `git init`
      + `fetch --depth 1 <commit>` + `checkout FETCH_HEAD`, verify `rev-parse
      HEAD` equals the pinned commit, then delete `.git`. That verification is
      the load-bearing part — without it a moved upstream silently invalidates
      every line number in the grading key.
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
| B3 | The demo app's grading key is **AI-drafted and unverified** (`verified: false`). Phase 4's precision/recall is graded against them, so no number is thesis-grade until a human confirms. | A human reads the app and flips `verified`, `verified_by`, `verified_date`. **Blocks Phase 4.** |
| B4 | The Phase 1 line **"Stand up the LangGraph skeleton"** duplicates Phase 3's "agentic audit workflow (planner picks next probe over shared state)". Building it now would break rule 15. | Decide whether to move the line to Phase 3. Not implemented either way. |
| B6 | **The subset is now decided but the corpus does not exercise all of it.** The project cites the 2025 OWASP list: LLM01, LLM03 (supply chain), LLM06, and auditability. The one corpus app has findings for LLM01, LLM02, LLM06 and AUDITABILITY -- **nothing for LLM03**, so the risk Phase 2 exists to report has no ground-truth finding to be graded against. | Add an LLM03 finding to the grading key once Phase 2 can produce evidence for one. The app has two used-but-undeclared dependencies (PyYAML, python-dotenv), which is a real candidate. |
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
- [~] Project documentation written and kept in step with the code:
      `CODING_RULES.md` (the binding standard, tracked so the whole team and
      an examiner get it), `FLOW.md` (how the system works), `SCHEMAS.md`
      (the JSON contracts between phases)

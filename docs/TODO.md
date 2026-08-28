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

- [x] Collect deliberately-vulnerable demo apps (2 apps). The one on disk
      carries 6 drafted findings; the second app is not downloaded, so the
      corpus-wide count cannot be stated here — see B3
    - https://github.com/ReversecLabs/damn-vulnerable-llm-agent
    - https://github.com/13o-bbr-bbq/Broken_LLM_Integration_App
- [~] Select + verify 2–3 open-source LangGraph/LangChain apps (checklist and
      manifest template ready; live verification done by hand) — **two of the
      three are JavaScript/TypeScript**; the auditor now reads those too, and
      one of them is a fixture on disk (see 1.10)
    - ~~https://github.com/langchain-ai/agent-chat-ui~~ — **dropped**: 56 source
      files yielding a single generic `fetch` surface. It is a frontend that
      talks to a server over `langgraph-sdk`, so it has no prompts, agents, or
      tools to audit. No parser could change that.
    - https://github.com/langchain-ai/langgraphjs-studio-starter — adopted as
      `corpus/oss-app-langgraphjs-starter`, pinned to `cd9a02c6` (TypeScript,
      5 surfaces, no planted vulnerabilities, so it measures false positives on
      clean code). Removed when the corpus narrowed to one app, restored since
    - https://github.com/langchain-ai/open_deep_research
- [~] Manually establish ground truth for the demo app — drafted as
      `corpus/evidence/vuln-app-1-support-agent.ground_truth.json`, 6 findings,
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
- [x] 1.3 Repo loader — `src/parsing/repo_loader.py`
- [x] 1.4 Surface data model — `src/artifacts/surface.py`
- [x] 1.5 Surface extractor — `src/detectors/detectors.py` + `src/parsing/extractor.py`
- [x] 1.6 CLI entry point — `src/main.py`
- [~] 1.7 Validation — the suite is green and every code-linked ground-truth
      surface is found *in the files the scan could read*; a scorer has to read
      `skipped_files` before treating that as recall (see `docs/SCHEMAS.md`).
      The by-hand cross-check of each grading key is a human task. See B3.
- [x] Settings read from the environment (`src/config.py` + `.env.example`);
      the test corpus is discovered on disk instead of listed in code
- [x] System flow documented step by step in `docs/FLOW.md`
- [x] 1.8 Language registry (`src/parsing/languages.py`) — extension to language and
      to tree-sitter grammar, kept as two separate ideas
- [x] 1.9 JavaScript/TypeScript backend (`src/detectors/detectors_js.py`,
      `src/parsing/extractor_js.py`, `src/parsing/ts_utils.py`) via tree-sitter
- [x] 1.10 A clean-code fixture — `oss-app-langgraphjs-starter`, restored and
      pinned to `cd9a02c6`. It is the only fixture that can measure a
      false-positive rate; every other one measures recall alone. Current
      reading: **5 of 5 expected surfaces found, 0 false positives**, against a
      grading key that claims `expected_surfaces_complete: true`, so an extra
      surface would fail the test rather than go unnoticed
- [x] Evidence split out of the audited code: `corpus/<app>/` is now a
      byte-identical upstream copy, and everything authored about it lives in
      `corpus/evidence/`, owned by `src/corpus_paths.py`
---

## Phase 2 — SBOM/AIBOM + advisory ingestion & mapping

See [`PHASE_2_PLAN.md`](./PHASE_2_PLAN.md) for the task breakdown and
done-criteria.

- [x] Generate an SBOM via Syft. Two files: `sbom.cyclonedx.json` is valid
      CycloneDX, so the result can be fed to other supply-chain tooling and
      checked independently; `sbom.json` is a normalised shape and is what the
      later phases read. The standard format alone is not enough, because it
      has no field for how much a version can be trusted -- one guessed from
      `~=0.3.25` looks identical to an exact pin -- and it omits dependencies
      the generator did not find (two on the Python app, two on the JS one).
      Both corpus apps now produce both bills
- [x] Define the AIBOM schema and build it (`src/artifacts/aibom.py`), derived from
      `surfaces.json` so every entry traces to a surface. `datasets` is absent:
      no surface kind produces one
- [x] Write the advisory data policy (`SCHEMAS.md`): fetched out-of-band as a
      documented manual step, read from disk, never at runtime
- [x] Read npm manifests, so a JavaScript app can be given an SBOM
      (`src/deps/npm_manifest.py`). The JS fixture now produces all five
      artifacts: **82 components, 80 of them `locked`** with an exact version
      from `yarn.lock`, against the Python app's 1 pinned of 5. Mapping
      coverage is 4 of 5 surfaces (80%) versus 6 of 19 (32%). The four problems
      recorded here before are settled:
      (a) duplicate names — a component's identity is now
      `(ecosystem, name, version)`, so all three `langsmith` versions survive
      where a name-keyed dict kept one;
      (b) a scoped name is percent-encoded (`%40langchain`), verified equal to
      the generator's own purl on all 80 components;
      (c) the exact-pin rule is per ecosystem — `==1.2.3` for PyPI, a bare
      `1.2.3` for npm — so `==4.19.2` is no longer read as an npm pin;
      (d) name normalisation is PEP 503 for PyPI and lowercase-only for npm,
      keeping `lodash.merge` and `lodash-merge` distinct.
      The mapping join now also compares ecosystem to the surface's language
- [x] A lockfile-resolved version is its own provenance, `locked`
      (`sbom.json` `schema_version` 2). It earns a versioned purl because it is
      what will actually be installed, while `inferred` stays structurally
      barred. It is assigned from "a lockfile was read", never from the
      ecosystem. Only npm reaches it through the CLI today, though:
      `manifests_present` reports no Python lockfile, and it must not until
      `from_lockfile` is per component — the flag is document-wide, and the
      generator's Python range-guessing is on, so one `poetry.lock` would
      relabel every guessed version as a fact at once
- [x] An ambiguous join drops the version instead of picking one
      (`mapping.json` `schema_version` 2). Where a name
      holds several installed versions, `mapping.json` reports
      `component_version_count` and a version-less purl. Caught on the fixture:
      `@langchain/openai` is installed at 0.3.0 and 0.3.2, and the join key was
      asserting 0.3.2 by sort order alone
- [x] A package declared bare now keeps the version the generator resolved
      (`sbom.json` `schema_version` 3). `unconstrained` keeps its meaning --
      the manifest named no version -- and the resolved version travels in
      `version` as evidence, never in the PURL: what a resolver found is not
      what the app asked for. Neither corpus bill changed a byte beyond the
      version number, because both of their unconstrained records are
      `tool_reported: false` with nothing to keep; the synthetic case in
      `tests/artifacts/test_sbom_vocabulary.py` is the only one that exercises
      it. The retention rule became one-directional in the process: a version
      implies one of the four sources, not the reverse
- [ ] Read Python lockfiles (`poetry.lock`, `Pipfile.lock`). Needs
      `from_lockfile` derived per component from the generator's own evidence
      first, for the reason on the `locked` line above
- [ ] Attribute a constraint to the record it actually selected. Today
      `declared_in` and `version_constraint` are facts about the name, so the
      fixture's `langsmith` 0.1.48 record carries `^0.1.55` — a constraint its
      own version fails. Fixing it needs a `yarn.lock` resolution-tree parser
      and semver satisfaction, which is a bigger job than reading the manifest
- [ ] Scan a repository declaring both a Python and an npm manifest. It is
      refused with a message today rather than half-read, because one SBOM
      holds one ecosystem and reporting only the Python half would understate
      the tree while looking complete. No corpus fixture is mixed
- [ ] Ingest the local advisory snapshot (planned: `src/deps/advisories.py`)
      and build
      the matcher. **No longer blocked on evidence.** It was deferred because
      an advisory keys on a versioned PURL and the Python app yields exactly
      one: of five components only `langchain-litellm` is pinned, and a version
      inferred from a range is barred from the PURL by design, so a matcher
      would have reported on 20% of the tree while looking complete. Reading
      npm manifests changed that — the JS fixture yields **80 versioned
      PURLs** from its lockfile, so there is now a tree worth matching against.
      What remains is the matcher itself and the out-of-band snapshot
- [x] Build surface-to-component mapping (`src/artifacts/mapping.py`), joining on each
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
- [x] ~~Drop `SystemMessage` / `HumanMessage` / `MessagesPlaceholder` from
      `PROMPT_CLASSES`~~ — **considered and refused.** The first two *are*
      prompt text, so reporting them is correct rather than noisy. A
      `MessagesPlaceholder` is a history slot, which is exactly where indirect
      injection lands, so dropping it would cost LLM01 recall. With one fixture
      there is no evidence of noise either way, and a name in a table costs
      nothing while a missed prompt is a recall failure
- [x] HTTP-route data source on the JS side (`src/detectors/data_sources_js.py`).
      Express and Next handlers are the main untrusted input in JS apps, and
      the detector reports the registration site: `app.get('/x', h)`,
      `router.post`, `app.use('/api', r)` and the chained `app.route('/x')`.
      The guard is **two arguments and a literal path starting `/`**, not "a
      callback as the last argument" as first planned -- that would have missed
      `router.post('/x', handler)`, where the handler is a bare identifier.
      `app.get('port')`, Express's config getter, stays quiet on the leading
      slash. Route surfaces carry no `module`: `app` is a local bound to
      `express()`, so naming its package needs Phase 3's dataflow.
      **Synthetic-tested, not corpus-measured** -- neither fixture runs a
      server, so no false-positive rate is claimed
      (`tests/detectors/test_data_sources_js.py`)
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
- [x] ~~Make `src/` a real package~~ — **declined.** It is 37 modules in five
      folders with one entry point, and the folders are plain directories that
      Python imports without an `__init__.py`. `python src/main.py` works,
      `tests/conftest.py` handles the path, and converting would touch every
      import for no reader benefit. Recorded in `FLOW.md`

---

## Phase 3 — LangGraph auditor, probes & reporting

- [ ] Restore corpus fixtures from their pinned manifests (Task 3.8a), and
      separately audit a repository straight from a URL (Task 3.8b). Split
      because 3.8a protects the grading keys' line numbers and 3.8b only
      enlarges the corpus, which is a Phase 4 need. Both were built during
      Phase 1 and removed again; the code is on the `phase3/url-fetcher`
      tag. Original note follows.
      Audit a repository straight from a URL, and restore corpus fixtures from
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
- [ ] Make `call_bindings` scope-aware. It is module-wide "last binding wins"
      today, so in the corpus app `cursor` reads as bound at line 75 while it is
      used at lines 14 through 79 -- it is bound separately inside several
      functions. Harmless for the taint trace, which over-approximates within a
      file, but it is why `DATA_SOURCE_METHODS` could not be narrowed by the
      receiver's type: that would drop real detections on evidence from an
      unrelated scope
- [ ] Implement the agentic audit workflow: the LangGraph skeleton (shared
      state, planner node, bounded loop with a step cap) and the planner that
      picks the next probe over that state. Moved here from Phase 1, which had
      it as its own line — the two described the same work, and nothing was
      built under either, so only the line moved
- [x] Taint-style dataflow tracing (`src/checks/taint.py`, built on the new
      `src/parsing/bindings.py`). Traces an untrusted value to a model or a
      model-driven tool **within one file**, which is a hard limit rather than a
      starting point. It reaches `VULN1-03`: `prompt := st.chat_input()` at
      `main.py:60` is handed to `executor(prompt)` at line 82, where `executor`
      was bound from an `AgentExecutor` surface at line 71. The missing half was
      the binding -- a surface says a call happened at a line, never what the
      result was called afterwards. Nine sources it could **not** follow are
      recorded as `inconclusive` / `trace_left_static_analysis` rather than
      dropped, so nine unfollowable traces sit beside two findings instead of
      reading as a clean bill. Python only: the JS side would need the same
      analysis rebuilt on tree-sitter, and `coverage.checks_run` omits the check
      entirely on a JS app rather than claiming it looked
- [x] Narrowed the bare method names on both language sides, by **measuring
      first rather than guessing**. The safe cut turned out to be whether the
      receiver can be named at all: `resp.json().load()` and
      `registry[key].load()` produce a surface named bare `load`, matching any
      object whatsoever, so they are dropped; `cursor.execute(...)` and
      `self.cache.load()` point at something and are kept. Both corpus apps
      produce byte-identical surfaces, so the noise class went and no real
      detection did.
      Not done, and worth knowing why: narrowing by the receiver's **type** is
      what the line originally imagined, and the binding analysis cannot support
      it yet -- see the scope limit below
- [x] Static permission checks (`src/checks/permissions.py`): a tool surface is
      over-privileged when its class grants a shell, an interpreter or outbound
      HTTP. **It finds nothing on this corpus**, which is the honest result --
      neither fixture uses `ShellTool`, `PythonREPLTool` or the Requests tools,
      so the rule is stated and exercised but not demonstrated. The graded LLM06
      finding is not of this kind: `VULN1-02` is a tool accepting any userId,
      which is a missing authorisation check and needs the dataflow of 3.4
- [x] `findings.json` and its two first producers (`src/artifacts/finding.py`,
      `findings_document.py`, `src/checks/`). A finding cites its evidence or
      cannot be constructed, and `src/checks/supply_chain.py` produces the
      graded LLM03 finding from `mapping.json`'s `used_but_undeclared`. Verified
      against the key with the documented `LINE_TOLERANCE` join: 1 produced
      finding, matching `VULN1-06`, and **0 findings on the clean fixture**
- [x] ~~Enforce sandbox boundary (isolated instance, benign payloads only, no
      live systems)~~ — **superseded.** Phase 3 does not execute the audited
      app at all, so there is no sandbox to enforce. Refusing to run someone
      else's program is a stronger guarantee than running it carefully, and
      `tests/test_no_mutation.py` asserts it
- [ ] Build evidence-backed reporting (JSON + Markdown/HTML; each finding =
      OWASP ID + code location + LLM-surface link + SBOM/AIBOM/advisory refs)
- [x] Confirm human-in-the-loop only (no auto-patch, no PR merge), and that
      the auditor never executes the audited app. Asserted, not promised:
      `tests/test_no_mutation.py` hashes a corpus app before and after a full
      audit, and `tests/test_no_write_commands.py` reads `src/` for any
      mutating process or dynamic execution. The one module allowed to start a
      process is `syft_runner`, and a tripwire module proves the difference
      between reading a file and importing it

---

## Phase 4 — Evaluation & write-up

- [ ] Build the evaluation harness/scorer (reads `ground_truth.json`, computes
      TP/FP/FN → precision/recall/F1 per app + aggregated)
- [ ] Implement baselines: simple static rules and SBOM-only scan
- [ ] Report which framework names the corpus actually exercises. **Moved out
      of Phase 2:** the fix is fixtures, not detector code, and the number is
      an evaluation result. Measured today: the JS tables hold **57** names
      across 12 tables -- 47 plus the 10 the route detector added -- and the
      one JS fixture exercises **5**, so 52 are carried untested. Counting
      excludes `HTTP_METHODS` and `ROUTE_DECORATOR_ROOTS`, which are the Python
      tables the route tables are built from rather than tables of their own.
      (An earlier note said 29; that was never sourced.)
- [ ] Run experiments: agentic auditor vs baselines on the full corpus
- [ ] (Optional, if RQ3 is kept) Compare model families (Gemma / Llama / Qwen)
- [ ] Implement probe: benign injection tests in a sandbox (direct + indirect
      via documents). **Moved out of Phase 3**, where it could not earn its
      place: every finding in both grading keys carries `detection` of `static`
      or `either` and not one is `probe`, so it would add no recall the static
      path cannot reach; the vulnerable fixture defaults to
      `gpt-4-1106-preview` through LiteLLM, so running it breaks the offline
      guarantee; and aimed at Ollama instead, an observed injection becomes a
      fact about `qwen2.5-coder:7b-instruct` rather than about the audited app.
      Revisit only with a fixture carrying `detection: "probe"` findings and a
      locally servable model
- [ ] Analyse results (does agentic probing improve detection + explanation?)
- [ ] Write the thesis report
- [ ] Release the open-source prototype

---

## Blocked / needs a decision

Anything that stops work or needs a human call. Clear these as they are
resolved; do not tick the task above until its blocker is gone.

| # | Blocker | Who / what unblocks it |
|---|---|---|
| B3 | Both grading keys are **AI-drafted**. The JS key is `verified: true` but with `verified_by`/`verified_date` still null, which `SCHEMAS.md` treats as incoherent; the Python key is back to `verified: false` because VULN1-06 was drafted into it after the human read. Phase 4's precision/recall is graded against both, so no number is thesis-grade yet. | A human reads VULN1-06, flips the Python key, and fills `verified_by`/`verified_date` on **both**. Only a human may set these fields. **Blocks Phase 4.** |
| B6 | ~~The corpus exercised no LLM03 finding~~ -- **drafted, awaiting the human read.** `VULN1-06` now records PyYAML used but never declared, with `SURF-06` as its expected surface, so the risk Phase 2 exists to report has something to be graded against. It is AI-drafted like the rest, so it folds into B3 rather than standing alone. `python-dotenv` is also absent from `requirements.txt` but no LLM surface resolves to it, so the artifact carries nothing to cite for it. | Clears with B3. |
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
- [x] Project documentation written, and kept in step as the code changes:
      `README.md` (what it is, how to run it, and what it produces today),
      `CODING_RULES.md` (the binding standard, tracked so the whole team and
      an examiner get it), `FLOW.md` (how the system works), `SCHEMAS.md`
      (the JSON contracts between phases)

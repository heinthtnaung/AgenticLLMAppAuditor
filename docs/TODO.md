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
      corpus-wide count cannot be stated here — the keys are per-app.
      **All of this describes the corpus as it was; it was removed 2026-09-04**
      (see "Corpus removal" below), so every "on disk" in this phase is past
      tense and the pins live in `docs/REPORT.md` Appendix A
    - https://github.com/ReversecLabs/damn-vulnerable-llm-agent
    - https://github.com/13o-bbr-bbq/Broken_LLM_Integration_App
- [x] Select + verify 2–3 open-source LangGraph/LangChain apps (checklist and
      manifest template ready; live verification done by hand). **Two are
      fixtures on disk**: `oss-app-langgraphjs-starter` (TypeScript, see 1.10)
      and `oss-app-react-agent` (Python), one per language the auditor reads,
      so a false-positive number is not taken solely from the language its
      taint trace cannot parse
    - ~~https://github.com/langchain-ai/agent-chat-ui~~ — **dropped**: 56 source
      files yielding a single generic `fetch` surface. It is a frontend that
      talks to a server over `langgraph-sdk`, so it has no prompts, agents, or
      tools to audit. No parser could change that.
    - https://github.com/langchain-ai/langgraphjs-studio-starter — adopted as
      `corpus/oss-app-langgraphjs-starter`, pinned to `cd9a02c6` (TypeScript,
      5 surfaces, no planted vulnerabilities, so it measures false positives on
      clean code). Removed when the corpus narrowed to one app, restored since
    - https://github.com/langchain-ai/react-agent — adopted as
      `corpus/oss-app-react-agent`, pinned to `9bbd82d8` (Python, 4 surfaces,
      no planted vulnerabilities). Added so false positives could be measured
      on **Python**, where the taint trace runs at all -- the clean TypeScript
      fixture cannot exercise it. **The result is thinner than the intent:**
      the trace runs here but concludes nothing (one source, unfollowed), and
      the extractor finds no tool surface, so the permission check had no
      subject either. Its zero false positives is 0 of 0 opportunities --
      stated and exercised, but not demonstrated. It declares dependencies in `pyproject.toml`, which
      the tool does not read, so it is also the only fixture reaching the
      no-manifest path end to end -- no SBOM, no mapping, and
      `unresolved_component_count: null` on real data for the first time
    - https://github.com/langchain-ai/open_deep_research
- [x] Manually establish ground truth for the demo app —
      `corpus/evidence/vuln-app-1-support-agent.ground_truth.json`, 6 findings,
      now `verified: true` with a named human and date. It stays
      `source: ai_drafted`: who wrote it and who checked it are different
      facts, and collapsing them would overstate the key's provenance
- [x] Manually establish ground truth for the open-source apps —
      `corpus/evidence/oss-app-langgraphjs-starter.ground_truth.json`, 5
      expected surfaces and no findings, also read and verified. B3 cleared on
      both

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
      README carries the pinned clone commands (now under "Restoring the
      graded corpus"), and tests that need the app skip with a pointer to it
- [x] 1.1 Scaffolding — `src/ corpus/ tests/ artifacts/`, `requirements.txt`,
      `README.md`, `.venv` installs cleanly
- [x] 1.2 Offline model client — `ask()` verified against the local server
- [x] 1.3 Repo loader — `src/parsing/repo_loader.py`
- [x] 1.4 Surface data model — `src/artifacts/surface.py`
- [x] 1.5 Surface extractor — `src/detectors/detectors.py` + `src/parsing/extractor.py`
- [x] 1.6 CLI entry point — `src/main.py`
- [x] 1.7 Validation — **resolved 2026-09-04.** It sat at `[~]` because the
      by-hand cross-check of each grading key is a human task; all three keys
      did carry one (`verified: true`, named checker, date) before the corpus
      was removed, which is what closes it. The finding it recorded still
      stands and is not a corpus fact: every code-linked ground-truth surface
      was found *in the files the scan could read*, so a scorer must read
      `skipped_files` before treating that as recall (see `docs/SCHEMAS.md`).
- [x] Settings read from the environment (`src/config.py` + `.env.example`);
      the test corpus is discovered on disk instead of listed in code
- [x] System flow documented step by step in `docs/FLOW.md`
- [x] 1.8 Language registry (`src/parsing/languages.py`) — extension to language and
      to tree-sitter grammar, kept as two separate ideas
- [x] 1.9 JavaScript/TypeScript backend (`src/detectors/detectors_js.py`,
      `src/parsing/extractor_js.py`, `src/parsing/ts_utils.py`) via tree-sitter
- [x] 1.10 A clean-code fixture — `oss-app-langgraphjs-starter`, restored and
      pinned to `cd9a02c6`. Current reading: **5 of 5 expected surfaces found,
      0 false positives**, against a grading key that claims
      `expected_surfaces_complete: true`, so an extra surface would fail the
      test rather than go unnoticed. It is still the fixture carrying real
      false-positive evidence: its supply-chain check ran against an
      82-component SBOM and its one tool surface was judged.
      `oss-app-react-agent` joined it later as a second clean fixture, in
      Python, but no check there had a subject to be wrong about -- 0 of 0
      opportunities. The vulnerable fixture still measures recall alone
- [x] Evidence split out of the audited code: `corpus/<app>/` was a
      byte-identical upstream copy, and everything authored about it lived in
      `corpus/evidence/`, owned by `src/corpus_paths.py` (**all three removed
      2026-09-04**; the split itself survives as `grading_keys/` beside a tree
      the tool never owns, which is the same idea taken further)

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
- [ ] Read Python lockfiles (`poetry.lock`, `Pipfile.lock`, and `uv.lock`,
      which `oss-app-react-agent` ships and which is why that fixture produces
      no bill of materials at all). Needs
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
- [x] **Measured what advisory data is worth, with an off-the-shelf scanner.**
      Trivy 0.74.0 on `security-agent-testbed` at commit `89eaa8ab`: **311
      vulnerabilities** (22 critical, 128 high, 284 unique CVEs, 68 packages)
      where this auditor reports **0**. Both correct -- no advisory data here,
      and that repo has no LLM surfaces (`surface_count: 0`) -- but it sizes the
      gap below and is now the README's scanner comparison. Trivy is **not** a
      dependency: nothing under `src/` calls it and it is absent from the
      prerequisites
- [x] **Severity and VEX for every vulnerability, reached or not.** Two user asks,
      one change (`SCHEMA_VERSION` 5 → 6). Severity: `Finding.advisory_severity`
      and per-CVE severity in the unreached list, the word quoted from Trivy's
      named source and carried only beside `advisory_cvss_source` (an
      attribution invariant refuses an unattributed word) — the reversal of the
      earlier "severity refused" stance, honest because it is a quotation, never
      the tool's own rating, and never a SARIF `level` or a scored number. VEX:
      `to_vex_statements` now emits `affected` for a reached component and
      `under_investigation` for an unreached one (present, exploitability not
      assessed) — `not_affected` stays unrepresentable (allow-set in
      `_statement_arguments`), so `emit_vex` produces a document even for a repo
      with zero reached components (security-agent-testbed: 311
      under_investigation, 0 not_affected, ~4s). The report shows severity per
      CVE and a VEX summary counted from the same `to_vex_statements` the
      emitter writes from, so the counts match by construction.
- [x] **Report the vulnerable-but-unreached components, not just count them.**
      `security-agent-testbed` (79 vulnerable dependencies, no LLM surfaces) read
      as "No findings" because the report showed only
      `coverage.advisory_unreached_component_count`. Fixed: `known_advisory`
      now also produces `unreached_components` (each purl with its sorted
      advisory ids), stored as `coverage.advisory_unreached_components`
      (`SCHEMA_VERSION` 4 → 5, paired with the count in the builder), and
      `report.py` renders a prominent `## Known vulnerabilities in dependencies`
      section listing them, with the headline reframed to "No finding reaches an
      LLM surface" so a report is never misread as clean. They stay **out** of
      the scored `findings` list, so `evaluation.json` is byte-unchanged and the
      tool does not become a dependency scanner — the reachability claim is still
      what a *finding* means.
- [x] ~~Ingest the local advisory snapshot~~ **Done — as Trivy, not OSV.**
      The planned matcher (`advisories.py`, `version_ranges.py`) was never
      written: version-range semantics are a spec this project does not own,
      the argument that chose Syft and vexctl, so `src/deps/trivy_runner.py`
      runs Trivy offline (six network switches off by flag, asserted by value
      in `tests/test_advisory_launch.py`) and `src/checks/known_advisory.py`
      joins its purl-keyed records to the mapping. One finding per (surface,
      component, advisory), anchored on the reaching surface so `matches_key`
      scores it unchanged; everything unreached is
      `coverage.advisory_unreached_component_count`. `SCHEMA_VERSION` 3 → 4:
      four `advisory_*` finding fields (CVSS as an attributed **vector**
      quotation -- ~~the severity word is refused as a judgement~~ (reversed at v6)) and four
      `advisory_*` coverage fields pinning generator, version and the DB's own
      `UpdatedAt`. SARIF `ruleId` is now the CVE/GHSA id on advisory findings,
      which fells VEX blocker one. Measured: `oss-app-langgraphjs-starter`
      yields 2 findings at `src/agent.ts:9` with 11 unreached;
      `security-agent-testbed` stays at 0 findings with **79 unreached**, which
      is the honest sentence its report now prints. See `ADVISORY_PLAN.md`'s
      completed checklist. Still open there: grading-key entries for the new
      check (human work), and the A4 re-measure write-up
- [~] VEX documents (`vex/`). The folder, its manifest and the provenance
      discipline are in place; **no document and no reader in `vex/`** -- the
      document this project *emits* lives under `artifacts/` and is ticked
      below -- and both are
      recorded rather than left implicit. Two blockers, each a property of the
      data: no upstream VEX document exists for any dependency of any fixture
      (`langchain`, `langchain-community`, `langchain-litellm`, `openai`,
      `streamlit`, `pyyaml` all checked at conventional locations and in PyPI
      metadata -- none publishes one or declares a security URL), and a VEX
      statement needs a versioned PURL while only 1 of the Python app's 5
      components carries an exact version. The npm fixture is not blocked by
      the second: 80 of 82 are `locked`. `tests/test_vex_unread.py` asserts
      nothing under `src/` reads the folder, so a half-wired reader cannot make
      a claim the data does not support
- [x] Install `vexctl` (v0.4.4, static binary to `~/.local/bin`). It does not
      scan and was never going to: `create` authors a document, `merge` joins
      documents, `filter` applies them to **someone else's** results. As a
      filter before the report is written it is the right tool and the right
      position -- a finding a maintainer has already declared `not_affected`
      should not reach a reader as though nobody had looked
- [x] Emit `findings.sarif.json` beside `findings.json` (`src/artifacts/sarif.py`).
      The precedent is exact: `sbom.cyclonedx.json` already sits beside
      `sbom.json` for feeding other tooling, and SARIF is that for
      static-analysis results. No `tool.driver.version`, because this project
      has no version number and every candidate is a fact-shaped guess; the
      contract it came from travels as `runs[].properties.findings_schema_version`
      instead. `level` is the constant `warning`, which is what SARIF resolves
      an absent level to, so the copy asserts no severity this project refuses
      to claim. `narrative` is dropped, so the file has no exempt field and is
      byte-identical every run
- [ ] ~~Wire the vexctl filter before the report~~ — **superseded by Task 5.3**,
      which is where the filter's disposition now lives; this entry is kept for
      the measurement below. Note the first condition it names has since been
      met: advisory findings carry CVE ids, so the rule-id blocker is gone and
      only the product-blindness and the absent upstream documents remain.
      Emitting SARIF was once recorded here as the thing blocking it. That was
      wrong. `vexctl filter` joins on
      `result.ruleId` being an *advisory identifier* and nothing else: a SARIF
      result with `ruleId: "CVE-2020-14343"` and a matching statement is
      dropped, while the same document with `ruleId: "undeclared_dependency"`
      -- this project's actual rule id -- is untouched. Only `CVE-`, `GHSA-`,
      `GO-` and `RUSTSEC-` schemes match, so even a PyPI-native `PYSEC-` id
      would not. Findings would have to carry CVE ids first, which needs
      advisory ingestion.
      And it should not be wired even then without care: a statement about
      `pkg:npm/totally-unrelated@1.0.0` suppressed a result about PyYAML,
      because the product is ignored entirely. A filter that drops findings
      without checking which component they concern would quietly undo "every
      finding cites the evidence that produced it"
- [x] ~~Decide whether `vexctl` is worth a second external binary.~~ **Decided:
      yes, installed.** The earlier reasoning against it is kept because it is
      still half true -- OpenVEX is plain JSON that `json.dumps` covers, and
      `merge`/`attest` are of no use here. What changed the answer is `filter`:
      re-implementing statement matching would put this project's own code
      between a maintainer's claim and the reader, which is exactly the place a
      standard tool belongs. Note this does **not** touch the stdlib-first
      rule, which governs pip packages and whose one standing exception is the
      JS parser: `vexctl` is an external binary, the third alongside Syft and
      Ollama, and belongs in the README's prerequisites table rather than in
      `requirements.txt`
- [x] **Measured bound on emitting VEX, and now enforced in code:** this tool
      may emit `affected` and must never emit `not_affected`. `mapping.json`
      has one entry per LLM *surface*, so an unreached component is not an
      unused one -- on the TypeScript fixture `@langchain/core/messages` is
      imported by the app's own source with no surface reaching it.
      `vulnerable_code_not_in_execute_path` from surface reachability alone
      would suppress a real vulnerability in running code.
      `tests/test_vexctl_launch.py` asserts no module under `src/` passes that
      status, `--justification` or `--impact-statement` as a value, with a
      planted violation proving the search bites and a second test proving a
      docstring explaining the ban does not read as breaking it
- [x] **Emit VEX rather than consume it. Done.** `src/artifacts/vex.py` decides
      the claims and `src/emit_vex.py` runs `vexctl` to author them into
      `artifacts/<system>/<app>/findings.openvex.json` -- a derived interchange
      copy, the same relationship `findings.sarif.json` has to `findings.json`,
      and a command of its own so an audit gains no external binary and no
      changed artifact count.

      **The audited app is the product; the component is a subcomponent.**
      That is the difference between a document worth publishing and one that
      restates the advisory: "this app is affected by this CVE via this
      component, reached by `TavilySearchResults` at `src/agent.ts:9`" is the
      claim, and `mapping.json` is what establishes it. One statement per
      (advisory, component) -- deduplicated, since OpenVEX resolves competing
      statements by timestamp and identical timestamps leave no precedence --
      with every reaching surface named in `status_notes`.

      **Two earlier claims here were wrong and are corrected.** `vexctl`'s
      `@id` is *not* a content hash of the document: it is a canonicalization
      hash of the document as created, and `add` leaves it unchanged, so an
      N-statement document would have carried an id identifying only the first.
      The emitter sets its own. And byte-identity needs `TZ=UTC` as well as
      `SOURCE_DATE_EPOCH`, because `action_statement_timestamp` otherwise
      renders in the local offset. The instant is the advisory database's own
      date, so the document says when its data was taken.

      Measured: `oss-app-langgraphjs-starter` emits 2 statements, byte-identical
      across runs, and `vexctl filter` accepts the document against our own
      SARIF and suppresses nothing -- which is correct, `affected` is not a
      suppression. `security-agent-testbed` emits nothing: 79 advisories, none
      reached

      Tested in five files: `tests/artifacts/test_vex.py` (the claim and the
      deduplication, pure), `tests/cli/test_emit_vex.py` (the pin, the id and
      the product), `tests/cli/test_emit_vex_command.py` (which vexctl commands
      run, with the tool replaced by a recorder),
      `tests/cli/test_emit_vex_vexctl.py` (the real tool, byte-identity and the
      filter, skipped when vexctl is absent) and
      `tests/corpus/test_vex_corpus.py` (the fixtures: 2 statements for the JS
      app, 0 for the Python one, from a transcribed advisory index so no test
      needed Trivy) -- **that last file was deleted with the corpus on
      2026-09-04**; the other four still run
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

- [x] ~~Task 3.8a — restore corpus fixtures from their pinned manifests.~~
      **Closed out of scope, deliberately** (2026-09-04, user decision), the way
      Task 5.3 was, rather than left as a task that can never be ticked. The
      restore had no subject left: the whole pinned corpus was removed, because
      the auditor takes any repository by URL and a fixed set of fixtures no
      longer reflects how it is used. What was owed here is now owed nowhere --
      and that is stated rather than implied. The three pins it would have
      restored are transcribed in `docs/REPORT.md` Appendix A, so the published
      Phase 4 figures name their inputs and stay falsifiable.
      **Task 3.8b, auditing from a URL, moved to Phase 5 and shipped.** The two
      were one line; rule 20 says split a line that turns out to be bigger than
      one, and these protected different things: 3.8a kept a grading key's line
      numbers honest, while fetching by URL enlarged what could be audited. In
      the end the second made the first unnecessary.
      Both were built during Phase 1 and removed again
      to keep it offline and simple. Bringing them back means bringing back the
      safety work an untrusted input needs: an https/git@ allow-list, a
      validated directory name (`.../org/..` would otherwise escape the
      download directory), skipped symlinks, no submodule recursion, and
      non-interactive git. Worth doing when the evaluation needs more than one
      app, not before.

      **The `phase3/url-fetcher` tag does not exist, so this is a rewrite.**
      This entry claimed the reviewed implementation and its 78 offline tests
      were kept there and could be checked out file by file. Searched for and
      not found: not in local tags, not on `origin`, and no reachable commit
      contains the code. Whatever was tagged was never pushed and is gone.
      Recorded rather than quietly deleted, because the difference between a
      restore and a rewrite is most of the estimate -- and because a claim that
      code is recoverable is the kind that goes unchecked until someone needs
      it.

      The safety checklist above survives the loss and is still what the work
      is: it is a list of properties, not of code.

      A companion `src/fetch_corpus.py`, which restored fixtures from their
      pinned manifests, was written and removed within a single change and is
      not in history. It was ~85 lines: read each `*.manifest.json`, `git init`
      + `fetch --depth 1 <commit>` + `checkout FETCH_HEAD`, verify `rev-parse
      HEAD` equals the pinned commit, then delete `.git`. That verification is
      the load-bearing part — without it a moved upstream silently invalidates
      every line number in the grading key.
- [x] Binding lookup is scope-aware. `call_bindings` was module-wide "last
      binding wins", so in the corpus app `cursor` read as bound at line 75
      while it is bound separately at 12, 35, 61 and 75 in four different
      methods. It is replaced by `scoped_call_bindings`, which returns a
      `Scope` carrying both a body and the names it binds -- the two travel
      together so neither can be read against the other's code. The taint
      trace walks scope by scope, so a source in one function can never be
      matched to a sink in another that reuses the name; the first attempt
      kept a module-wide walk and *introduced* that false positive, which is
      why `tests/checks/test_taint.py` now pins both the negative and its
      positive twin. Corpus output is unchanged -- 2 findings, 9 probes --
      which is the safest kind of correctness fix: it removes a way to be
      wrong without moving a number. A nested function is walked with its
      parent, which over-approximates in the direction that costs nothing,
      since a closure really can see the enclosing name
- [x] The agentic audit workflow (`src/checks/workflow.py`), on **LangGraph**.
      Shared `AuditState`, a planner node, an actor node, and a bounded loop
      with `MAX_STEPS = 20` -- the cap is the mechanism that stops a planner bug
      looping over someone else's repository, not a promise. The planner decides
      *which check runs next*; it does not decide what counts as a finding, which
      stays with the checks that read evidence and cite it. It is the real path
      now, not a parallel one: `coverage.checks_run` is what the workflow did
      rather than a list written beside it. Same output as before -- 2 findings,
      9 probes, byte-identical across runs.
      The dependency is a deliberate exception to the stdlib-first rule, taken
      because the thesis argues an agentic LLM app should be audited by one. It
      brings 33 packages including `langsmith`, whose tracing would send data off
      the machine, so the module disables it before importing langgraph rather
      than trusting a default
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
- [x] Evidence-backed reporting: `findings.json` plus `report.md`
      (`src/report.py`), written beside the other artifacts. Each finding shows
      its OWASP id, code location, the surface it came from and its component
      or mapping evidence. **What was not examined gets equal billing**, which
      is the part that matters: the vulnerable app's report lists two findings
      and then nine traces that could not be followed, eight surfaces with no
      component to check, two risk classes no check covers, and the absence of
      advisory data. The clean app's report
      opens "No findings. See what was not examined, below, before reading that
      as clean."
      It is a rendering with no contract of its own -- its only inputs are the
      two artifacts, and it recomputes nothing from source, because a second
      producer of the same facts is a second place for them to disagree. No
      count is turned into a rate: scoring is Phase 4's job.
      The renderer refuses what it cannot back: a stale `findings.json` from
      an older schema, and a finding claiming a probe reached it while naming
      a probe the document does not contain -- that would print "probe
      analysis" with no evidence under it, which is the one thing this report
      must not do.
      `findings.json` goes to schema_version 2 for it: `coverage` gains
      `risk_classes_checked` and `unresolved_component_count`, the two facts a
      reader needs to tell "no check covers this" from "a check found nothing"
      -- the second counts only mapping's `unresolved` reason, since `stdlib`
      and `first_party` are answers and `used_but_undeclared` is already a
      finding
- [x] Name `TavilySearch`, `ToolNode` and `init_chat_model` in the Python
      detector vocabulary. Reading `oss-app-react-agent` identifies all three
      as real LLM surfaces -- a tool call, a tool node and a model loader --
      and the Python tables name none of them, so the extractor finds 4 of the
      ~7 surfaces a reader sees. The JS tables already carry
      `TavilySearchResults`, so the two languages disagree about the same
      library. They are deliberately **absent** from that fixture's
      `expected_surfaces`, which is why its `expected_surfaces_complete` is
      `false`: listing them would fail the suite, and quietly omitting them
      without saying so would fit the key to the tool
- [x] **VULN1-04** (LLM02, `transaction_db.py:62`) -- closed by
      `src/checks/output_handling.py`, which reports a query built by
      interpolation rather than parameterised. Measured on
      `damn-vulnerable-llm-agent`: two findings, `transaction_db.py:62` and
      `:76`; the four constant-query calls at lines 14, 22, 44 and 56 report
      nothing (44 and 56 are `executemany`, not `execute`). `LLM02` now appears in `risk_classes_checked`, so this
      entry's miss reason can no longer be `no_check_for_risk_class`
- [ ] Close the three remaining known misses on the vulnerable app. Phase 4's
      scoring found them, but the work is Phase 3's: it changes what the
      auditor detects, and a detector must never be changed during a
      measurement. Two are checks that ran and stayed silent -- **VULN1-01**
      (LLM01, the system prompt at `main.py:21`) and **VULN1-02** (LLM06, the
      `GetUserTransactions` tool at `tools.py:40`). One is a risk class no
      check covers at all -- **VULN1-05** (AUDITABILITY, the `AgentExecutor` at
      `main.py:71`), so `risk_classes_checked` still does not name
      AUDITABILITY and that miss is attributed `no_check_for_risk_class`
      rather than to silence. Do it knowingly, in its own change, and re-score
      afterwards -- the before-and-after is itself a result worth reporting
- [x] Per-finding remediation advice (`remediation.json` + `remediation.md`),
      written by the local model. **This reversed a recorded decision**:
      `SCHEMAS.md` had listed "any suggested fix" among what the model may not
      write, because a model-written patch is one copy-paste from crossing the
      no-auto-fixing boundary. The concern was not dismissed, it was given a
      mechanism -- and the old text is struck through rather than deleted, so
      the reversal is legible.
      The guard runs on the answer, not the prompt, because prompt wording was
      **measured to leak**: told in general terms not to name the app's
      identifiers, `qwen2.5-coder:7b-instruct` returned a snippet containing
      `st.chat_input`; told the exact tokens, it did not. Advice is refused
      whole -- never edited -- if it names an identifier from the finding's own
      evidence or the app's modules, arrives as a diff, exceeds the volume
      caps, smuggles a code fence through prose, or names a foreign OWASP id.
      Refusals are recorded, so a reader can tell "the model wrote nothing"
      from "the model wrote something and it was refused".
      The advice lives in its own file the scorer cannot open, so
      `findings.json` stays byte-identical whether the model ran or not and no
      model word reaches a Phase 4 number
- [x] Confirm human-in-the-loop only (no auto-patch, no PR merge), and that
      the auditor never executes the audited app. Asserted, not promised:
      `tests/test_no_mutation.py` hashes a corpus app before and after a full
      audit, and `tests/test_no_write_commands.py` reads `src/` for any
      mutating process or dynamic execution. The one module allowed to start a
      process is `syft_runner`, and a tripwire module proves the difference
      between reading a file and importing it

---

## Phase 4 — Evaluation & write-up

See [`PHASE_4_PLAN.md`](./PHASE_4_PLAN.md) for the task breakdown.

- [x] Write `docs/PHASE_4_PLAN.md`. Every earlier phase got its plan before its
      code and this one did not: the scorer was built first, and the plan says
      so in its own section rather than papering over it. It gates what has not
      been built -- the entry point, the two baselines and the comparison --
      and writes each baseline's brief down *before* its code, so a baseline
      cannot be quietly weakened once the numbers come out close
- [x] Build the evaluation harness/scorer (`src/evaluation/`). Reads each
      app's `ground_truth.json`, `findings.json` and `surfaces.json`, joins
      them on the one rule in `src/evaluation/grading.py`, and builds
      `artifacts/<system>/evaluation.json`: TP/FN per app and pooled, with every miss
      attributed to a reason rather than left as a bare count. The join rule
      lives in source because three test files had grown three different line
      windows for it, and a scorer built on a fourth would measure something
      the suite does not certify
- [x] **No rate is a field, and F1 is refused outright.** `precision`,
      `recall` and `f1` appear nowhere in `evaluation.json`; a reader cannot
      copy a percentage out of it without dividing, and to divide they must
      hold the denominator. `false_positives` is `null` -- never `0` -- when
      the key's `findings_complete` is false, because the count is undefined
      there. No corpus app supports both precision and recall today, so
      no single app yields an unqualified pair
- [x] Give the harness a command to run from -- `src/evaluate.py`, its own
      entry point rather than a hook in the per-app CLI, because a whole-run
      artifact written by a per-app command is how a partial run silently
      produces a complete-looking score. `--system` is a closed vocabulary
      (`SCORED_SYSTEMS`), since the value becomes a directory name, and the
      artifacts moved to `artifacts/<system>/<app>/` so three systems can
      coexist -- which is also what lets the harness score every one of them
      unmodified. It prints counts and their qualifications, never a rate
- [x] Implement baselines: simple static rules (`src/baselines/static_rules.py`,
      rules in `rules.py`) and SBOM-only scan (`src/baselines/sbom_only.py`),
      run by `src/run_baseline.py` and scored through the **unmodified**
      harness. Ceilings were computed before the code and both held exactly:
      Baseline A reached 5 of 6, Baseline B 0 of 6. Neither reads a grading
      key -- `test_scorer_boundary.py` now guards `src/baselines/` too
- [x] Report which framework names the corpus actually exercises. **Moved out
      of Phase 2:** the fix is fixtures, not detector code, and the number is
      an evaluation result. The counting rule now lives in
      `src/evaluation/vocabulary.py` rather than in prose, because the figure
      that stood here -- "57 names across 12 tables" -- reproduced under no
      reading of the source, exactly like the unsourced "29" before it. A
      framework name is an identifier the detectors look for that a framework
      or library published; HTTP verbs, object-name roots like `app`, chat
      message dict keys and author-chosen name substrings are excluded, and the
      count is deduplicated because `HIGH_PRIVILEGE_TOOLS` and `TOOL_CLASSES`
      deliberately overlap, and a name counts as reached when a surface names
      it or names it as a dot segment -- a detector matches a root and records
      the whole chain, so `cursor.execute` reaches `execute`. **Measured:
      Python exercises 12 of 86 registered names, JavaScript 4 of 42** -- so
      112 of 128 are carried untested. The 12 and the 4 are a dated measurement
      and cannot be repeated: the corpus that exercised them was removed
      2026-09-04. The denominators are live and now pinned by a test, because they
      went stale the moment Task 2 added four Python names and nothing caught
      it -- this line claimed a test carried them when none did
- [x] Run experiments: agentic auditor vs baselines on the full corpus.
      **The grep baseline beats the auditor on recall, 5 of 6 against 2 of 6**,
      with 1 false positive against 0 *(pre-advisory run — the verified
      headline; post-advisory the auditor's OSS-app count was 0 → 2, both true
      CVEs the key predated; after the key gained `STARTER-01` it is 3 of 7 vs
      5 of 7 at 0 false positives, `key_unverified` until the human re-check —
      see the README's headline section for all three labels)*. SBOM-only reaches 0 of 6 and produces
      187 false positives. Reported headline-first because a comparison that
      only shows wins is not evidence. Full table and caveats in
      `PHASE_4_PLAN.md` Task 4.4
- [ ] (Optional, if RQ3 is kept) Compare model families. **A second model is
      now available** -- `gemma4:latest` beside `qwen2.5-coder:7b-instruct` --
      **and the model now has a bounded job**: it advises on every finding into
      `remediation.json`. Both preconditions are met, so the comparison is
      finally runnable. What it can compare: `status_counts.written` against
      `status_counts.rejected`, and the distribution of refusal `reason`s --
      how often each family's answer named the audited app's own identifiers,
      arrived as a diff, or re-classified the finding. Those are counts read
      off the artifacts, needing no human adjudication. **Three caveats before
      any number is quoted:** it measures advice quality under a fixed
      contract, not detection quality, which stays deterministic in every
      scored path; nothing here enters `evaluation.json`, so the comparison is
      descriptive; and `model_digest` is what makes it honest, since one of the
      tags is literally `:latest`
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
- [x] Analyse results. **The counts do not tell the useful story; the sets do.**
      The auditor matches `{VULN1-03, VULN1-06}`, the grep baseline
      `{VULN1-01..05}` -- near-complementary, union all six, and only
      `VULN1-03` shared. **`VULN1-06` is reached by the auditor alone**: it is
      the supply-chain finding, and reaching it means joining a surface to a
      component, which is what `mapping.json` is for. A regex fires on
      `import yaml` at `utils.py:3` while the key anchors at the use site
      `utils.py:75`; the SBOM baseline knows the package and not the line.
      Where the auditor loses it loses ground it never entered -- LLM02 and
      AUDITABILITY are absent from its `risk_classes_checked`. The probing
      question stays **unanswerable**: every scored run carries
      `model_disabled`, so no scored output depends on the model. Full analysis
      in `PHASE_4_PLAN.md` Task 4.7
- [ ] Write the thesis report
- [~] Release the open-source prototype. **Hygiene checked against a clean
      clone**: MIT licence present, no audited app source tracked (`corpus/`
      holds only `evidence/`), no artifact tracked, no `.env` or credential.
      **Blocked on the write-up**: `docs/report.docx` is tracked and stale
      while its source is gitignored, so a release today would ship a document
      contradicting the code beside it

---

## Phase 5 — Audit any repository, and export what it found

See [`PHASE_5_PLAN.md`](./PHASE_5_PLAN.md) for the task breakdown. This phase
changes what goes **in** and what comes **out**, and touches no detector: a
measurement re-taken because the measurer changed is not a measurement.

- [x] Task 5.1 — audit a repository straight from a URL. **Done.**
      `src/repo_url.py` decides what may be fetched (pure functions, so every
      planted attack is a plain unit test) and `src/fetch_repo.py` does the
      fetching: `https://` only, `-c protocol.allow=never` so a redirect cannot
      downgrade the transport, a scrubbed environment, a 300s timeout, a
      500 MB cap that removes the tree rather than scanning it, and a download
      root of `fetched/` that is **not** `corpus/`. It refuses an existing tree
      *and* an existing pin, since the pin is half the artifact. `rev-parse`
      runs before the history is removed, and the commit lands in
      `fetched/<name>.manifest.json`. It uses a clone rather than a checkout,
      which does the same job without the spelling `MUTATING_COMMANDS` bans.
      **And it refuses a name a committed grading key owns**: the download root
      is not `corpus/`, but `main.py` keys artifacts on the directory name
      alone, so a tree fetched as `vuln-app-1-support-agent` would have written
      over the artifacts `evaluate.py` scores. A test asserts the composed argv
      -- both `-c protocol...` flags, `--depth 1`, `--no-tags`, no submodule
      recursion -- and another asserts `_environment()`'s contents, since the
      structural check alone passes if it is rewritten to return `os.environ`. **Moved here from
      Phase 3 Task 3.8b**, which is now split: 3.8a protects the grading keys'
      line numbers and stays in Phase 3, while fetching by URL only enlarges
      the corpus. **A rewrite, not a restore** -- the `phase3/url-fetcher` tag
      the old entry pointed at does not exist. It is the tool's first untrusted
      input, so the safety properties are the task rather than a checklist:
      `https://` only, a scrubbed git environment (`GIT_CONFIG_GLOBAL` and
      `GIT_CONFIG_SYSTEM` to devnull, `GIT_TERMINAL_PROMPT=0`, because
      `url.<base>.insteadOf` rewrites a URL that already passed the check), a
      timeout, a size cap, and a named download root that refuses an existing
      destination -- otherwise a fetch could land on a pinned fixture and rot
      its grading key
- [x] Task 5.2 — export both reports as HTML and PDF. **Done.**
      `src/markdown_html.py` is a deliberate subset converter over the
      Markdown the audit already wrote -- one chain, Markdown to HTML to PDF,
      so nothing re-reads the artifacts and becomes a second producer of the
      same prose. It **escapes** HTML rather than passing it through, which is
      a safety property and not a limitation: `guidance` and `narrative` are
      model-authored. It raises on a table rather than flattening one into a
      paragraph. `src/export_reports.py` is a command of its own, so an audit
      needs no renderer installed and `write_all`'s artifact count keeps
      meaning what it meant. **`/CreationDate` is pinned** to the Unix epoch --
      no exemption needed, and two exports of one report are byte-identical.
      Not downstream of 4.9 after all: nothing generated here is committed,
      `fetched/` and `/artifacts/` are both gitignored, so the `report.docx`
      trap is structurally out of reach. 4.9 still stands on its own below.
      **The two documents are exported independently**, because `guidance` is
      model-authored and `remediation.md` sorts first: before that was isolated,
      one model-written table left *neither* document exported. A refusal is now
      reported alongside whatever did convert, and only an empty result raises
- [x] **Optional AI-formatted HTML report** (`report.ai.html`), user-requested.
      `src/ai_report.py` hands the deterministic `report.md` to a local model
      (`gemma4:latest`, config `AUDITOR_AI_REPORT_MODEL`) and asks it to style
      the same facts. The authoritative `report.html` is untouched and stays
      byte-identical; this page is a bonus. **Safety: a page that invents an
      advisory the audit never found is refused whole** (fabrication is the
      worst failure a security report has); a page that *omits* ids is allowed
      but its banner says it is INCOMPLETE and points at `report.html`. Records
      gemma's model id and digest. A command of its own and a degrading step in
      `pipeline.publish`, so the audit path, the artifact count, and the offline
      guard are untouched; `report.ai.html` is a documented byte-identity
      exception. `model_client.ask`/`model_digest` gained an optional `model`
      arg so gemma is used here while remediation keeps qwen.
      **Its `pipeline.publish` stage shipped without a test, and broke six**
      (2026-09-04): the six `tests/cli/test_pipeline_publish.py` tests reached
      the real `format_report` and raised `NotADirectoryError`. Fixed by a
      `stub_ai_report` seam in `tests/pipeline_helpers.py` beside the VEX and
      export ones, plus the three tests the stage never had -- the page's path
      is printed, an unreachable model is a stderr note, and a page refused for
      inventing an advisory is a note too. Recorded here rather than folded into
      Phase 6: the debt is this line's, not that phase's.
- [x] **One-command pipeline**: `python src/main.py <https-link>` fetches (or
      reuses a prior fetch of the *same URL* — a same-named different repo is
      refused by pin comparison), audits, authors VEX and exports HTML/PDF, each
      stage degrading with a printed reason. A **local path stays the pure
      offline audit, artifact-for-artifact unchanged**, so the no-network tests
      and the artifact-count contract hold. `src/pipeline.py` owns the
      composition (~85 lines; `main.py` stayed under rule 18 by delegating);
      `emit_vex.is_available()` added so a missing vexctl is a note, while a
      failing installed one still propagates
- [x] ~~Task 5.3 — the VEX **filter** (consuming)~~ — **declared out of scope,
      deliberately**, rather than left as a task that can never be ticked. The
      emitting half shipped as the Phase 2 item above; consuming rests on two
      facts unlikely to change: **no upstream VEX document exists** for any
      dependency of any fixture, and **`vexctl filter` ignores the product** —
      measured, a statement about an unrelated package suppressed a finding
      about PyYAML — so wiring it would suppress findings about the wrong
      component, undoing "every finding cites the evidence that produced it".
      Advisory ingestion did fell the third, historical blocker (`ruleId` is
      now a CVE/GHSA id). **Revived only by both together**: an upstream
      document appearing for a real dependency, and a product-aware filter.
      The position it would take is settled and stays recorded: before both
      the report and the remediation advice

---

- [x] **Grade the reachability claim, not the CVE identity.** `matches_key`
      honours the key's existing `component` field (byte-for-byte purl match,
      optional-when-named like `llm_surface`), and
      `oss-app-langgraphjs-starter`'s key gains `STARTER-01` -- one entry per
      (surface, component), naming no CVE, so it survives advisory-database
      updates. Both CVE findings answer it: 1 entry, 2 answered findings, 0
      false positives, and `answered_finding_count` was added beside
      `true_positives` (evaluation schema v2) so the pools never print entry
      counts beside finding counts. F1 flipped to reportable -- still never a
      stored rate. The key's `verified` flag is reset; see B9

- [x] **`corpus/` and `artifacts/` deleted** (2026-09-03, user instruction),
      so the repository ships the tool and its evidence-*about*-apps, not any
      audited tree. `artifacts/` was gitignored output and regenerates from a
      run. `corpus/evidence/`'s nine files were tracked; **the deletion is now
      committed**, so the restore is one step longer than this line first said
      -- `git checkout -- corpus/evidence` answers "pathspec did not match",
      because git no longer knows the path. It comes back from the deleting
      commit's parent:
      `git checkout "$(git rev-list -1 HEAD -- corpus/evidence)^" -- corpus/evidence`,
      then the three pinned clones (README, "Restoring the graded corpus",
      corrected 2026-09-04). **Everything from here to the end of this entry
      describes the world between 2026-09-03 and 2026-09-04 and is kept as the
      record of it** -- the corpus was removed outright later that day (see
      "Corpus removal" below), so no restore is owed and none is possible.
      At the time: **the suite refused at collection until evidence was
      restored** — `conftest.py` called `discover_corpus_apps()` at import,
      which raised when the folder was gone.
      The 1937-passing state was recorded immediately before deletion (corpus
      restored + `STARTER-01` re-applied). **One trap preserved rather than
      lost:** the `STARTER-01` grading-key edit was never committed, so a bare
      `git checkout` restores the pre-entry key; `docs/evidence-overrides/`
      holds the edited key and the README restore steps copy it back. Committing
      that entry into `corpus/evidence/` would retire the override.
      **Its cost, measured 2026-09-04, and now paid**: with `corpus/evidence/`
      restored but the three app clones still absent, **ten tests failed rather
      than skipped** -- `tests/artifacts/test_mapping.py` (8),
      `test_mapping_reasons.py` (1) and `test_determinism.py` (1) -- because
      each built a mapping from `corpus/vuln-app-1-support-agent` directly and
      `repo_loader` raises `FileNotFoundError` on a missing path. Alone in the
      suite, they were not guarded by `require_corpus`, so a fresh checkout
      could not go green at all. **Fixed**: one `require_corpus(SUPPORT_AGENT)`
      in each file's shared helper, and the suite is now
      **1817 passed, 326 skipped, 0 failed** with no app downloaded (that was
      the count when this guard landed; Phase 6's own tests took it to 1836
      later the same day).
      Cloning the fixtures would have turned those ten skips back into passes;
      **that is moot since the corpus was removed hours later** and those tests
      were deleted with it. The episode is kept because the lesson outlived
      them: a test that errors where its neighbours skip cannot be told from a
      real failure, which is now rule 13's business.
      Also fixed the same day:
      **`pytest.ini` now sets `testpaths = tests`**, because a bare `pytest` at
      the repo root walked `fetched/` -- the third-party trees `fetch_repo.py`
      downloads, each with its own suite and its own uninstalled dependencies --
      and died with 365 collection errors before running one of ours. Any test
      count recorded here is from `python -m pytest -q`.

Phase 5's charter -- "changes what goes in and what comes out" -- would also
cover grounding the advice in a knowledge base, but every Phase 5 task is ticked
or closed and that work adds a dependency, a folder, a data directory and a
schema bump, so it has its own phase: Phase 6 below.

## Phase 6 — Knowledge-grounded remediation advice (RAG)

See [`RAG_PLAN.md`](./RAG_PLAN.md). **Not a reversal of Phase 0.** Phase 0
dropped LLM08 (vector database / RAG retrieval) as a *risk class the auditor
detects*, because no corpus app retrieves. This phase adds retrieval as a
*mechanism the auditor uses for its own advice*: passages from a pinned local
knowledge base (the OWASP Cheat Sheet Series, indexed in ChromaDB with a local
Ollama embedding model) are injected into the remediation prompt and attributed
in `remediation.json`. Two different things. **Confined to advice**: nothing
here touches `findings.json`, `owasp_id`, `model_run` or the scorer, and every
degrade path is recorded rather than hidden.

- [x] Task 6.0 — split `artifacts/remediation.py` before extending it. **Done.**
      224 lines, two jobs. The judging half (`judge`, `app_identifiers`, the
      size caps and patch regexes, plus `evidence_line` moved from
      `checks/advise.py` and a new shared `foreign_owasp_ids`) now lives in
      `artifacts/advice_rules.py` (161 lines at the split, 166 now);
      `remediation.py` keeps the shape and vocabulary (107 lines **at the
      split; ~207 after Task 6.3 added the knowledge vocabulary** -- the figure
      is history, not a current claim, and rule 18 is on it) and never imports
      the rules. Seven importers rewired. Verified as a pure move: 14 recorded judging cases
      identical before and after, and full audits of two fetched apps
      (`ai-bom`, `llm-security`) byte-identical across all 17 artifacts.
- [x] Task 6.1 — the knowledge base and its index command. **Done.**
      `retrieval/chunks.py` (pure: heading-split markdown, code and tables
      dropped), `retrieval/manifest.py` (pure: `SOURCES` registry, the commit
      read from the clone's `.git` files, the content digest),
      `retrieval/store.py` (the one chromadb importer: telemetry off, a
      refusing embedding function so Chroma can never embed, vectors-only API),
      `src/index_knowledge.py` (one command: chunk, embed via Ollama, rebuild
      the index, write `knowledge/manifest.json`; raises rather than degrades).
      **Built for real on 2026-09-04**, not only against the synthetic index the
      tests use: the pinned CheatSheetSeries clone at `b8586414`, 121 files,
      3,484 passages, 57 seconds, and **31 MB for one index** -- measured after
      deleting `knowledge/index/` and building once, which is the only way to
      get that number: `Store.rebuild` drops the Chroma collection but leaves
      its HNSW files behind, so the folder gains ~10 MB per rebuild (50 MB
      after three here). Gitignored data rather than a leak in the artifacts,
      and left unfixed on purpose -- removing directories from `src/` cuts
      against this tool's no-write posture -- but `rm -rf knowledge/index`
      before a rebuild is the workaround, and 31 MB is the figure to quote.
      The manifest pins commit,
      content digest, embed model, embed model digest and chromadb version
      (1.5.9), and the store tests pass under the blocked-socket fixture.
      One defect the real build found and the synthetic one could not:
      `AUDITOR_EMBED_MODEL` defaulted to the untagged `nomic-embed-text`, which
      indexes fine but pins nothing -- Ollama lists a pulled model as
      `name:latest` and `model_digest` looks it up by that exact string, so
      `embed_model_digest` came out `null`. The default is now
      `nomic-embed-text:latest`, matching how the other two model settings are
      written, and the index was rebuilt.
- [x] Task 6.2 — embeddings, retrieval, and the OWASP reference. **Done.**
      `model_client.embed` over `/api/embed` with `ModelNotPulled` on 404 (the
      network stays in one module); `retrieval/retrieve.py` with the pure
      helpers and one `probe()` per run that owns every degrade reason;
      `retrieval/owasp_reference.py`, the 2025 entry per `owasp_id` by lookup,
      AUDITABILITY sourced to this project with no owasp.org URL. A finding
      retrieves attributed passages from the built index, and all four
      `KNOWLEDGE_REASONS` values have a test that produces them. **Two caveats
      kept rather than glossed:** "retrieves from a built index" is asserted
      against a *synthetic* index in the tests, never the real one, so the suite
      stays machine-independent; and `probe` was split into `_is_stale` and
      `_embed_reason` before this was ticked, because at 35 lines doing four
      jobs it broke rule 3.
- [x] Task 6.3 — `remediation.json` v2 and the wiring. **Done.**
      `knowledge_base` as a top-level sibling of `model_run`; `sources` on every
      entry, validated in `advice_entry`, stripped with tier (b); the reference
      and passages in the prompt before the forbidden list; `stub_knowledge` in
      the CLI tests so no test depends on this machine's index. The
      schema-keeper's reader list is exhausted (its documentation half is 6.4a
      below, so this tick does not claim the schema is written up), and an
      index-present, model-unreachable run is byte-identical. Also here:
      `tests/remediation_fixtures.py` pinned `FINDINGS_SCHEMA_VERSION = 3` while
      findings was at 6 -- a drifted pass-through literal, corrected to 6.
      **Three defects the reader audit found, all fixed here:** `tests/test_outputs.py`
      never got `stub_knowledge`, so eight of its tests would have started
      reading the real index and calling the real embedding endpoint the moment
      anyone followed the README and built one -- it passed only because no index
      existed yet; `cli_helpers.stub_model` patched `ask`/`model_digest` with
      lambdas taking no `model` argument, which the retriever's digest lookup
      then called with one; and `_read_manifest` trusted the manifest's
      `source_count`, so a hand-edited `0` raised out of `knowledge_provenance`
      and killed the audit that merely looked at the file -- the opposite of what
      that function's docstring promises. Every field it reads is now validated
      there, and a future manifest schema degrades to `index_stale` by intent.
- [x] Task 6.4a — the docs. **Done.** `SCHEMAS.md` (`schema_version` corrected
      to 2, the `knowledge_base` and `sources` rows, the source vocabulary, the
      status table's fourth column, the three determinism tiers rewritten --
      `knowledge_base` into (a) because an index is an input, `sources` into (b)
      with the reason it is not (a) -- and a new `knowledge/manifest.json`
      section beside the `vex/manifest.json` one, including the digest join the
      two files share, which was written down nowhere); `FLOW.md` (section 5
      rewritten from "two places" to three, a retrieval leg in both diagrams,
      the module map, section 7's model-client paragraph); `README.md` (a
      prerequisites row, an "Optional: the knowledge base" setup section, the
      grounding and attribution paragraphs in the remediation section, the
      layout, the documentation index); `.claude/AGENTS.md`. And
      **`docs/RAG_PLAN.md`, which `TODO.md` and `AGENTS.md` had both been
      pointing at while it did not exist** -- written as the plan of record with
      a "what changed during implementation" section rather than backdated.
- [x] Task 6.4b — the measurement. **Done**, and see the measurement block
      below. The same findings advised with and without retrieval, refusal
      counts compared, on three fetched apps (25 findings). There is no graded
      alternative any more and there will not be one: Task 3.8a is closed and
      the six graded findings are gone, so refusal counts -- measurable without
      a key -- are the only comparison this phase can make.
**The measurement (2026-09-04).** The same 25 findings advised twice, once with
retrieval and once without, everything else held: `qwen2.5-coder:7b-instruct`
at temperature 0 seed 0, `nomic-embed-text:latest`, the index at manifest
`1e37fcd1be24`. Three fetched apps, because the graded corpus was removed the
same day and no key exists to score advice against.

| App | Findings | Refused, ungrounded | Refused, grounded |
|---|---|---|---|
| `RAG-Examples-with-Langchain` | 15 | 11 | 5 |
| `RepoAgent` | 8 | 0 | **2** |
| `ai-bom` | 2 | 2 | 0 |
| **Total** | **25** | **13** | **7** |

By reason: `snippet_too_long` 6 → 1, `names_app_identifier` 7 → 6. All 18
grounded written entries cited passages, three each -- the cap -- so 54
attributions in total.

**Read it with three caveats, none of them small.** (1) The aggregate improvement
is real but **not uniform**: on `RepoAgent`, which refused nothing ungrounded,
grounding *introduced* two refusals. A phase that only quoted 13 → 7 would be
hiding that. (2) This measures whether an answer **survived the output
contract**, not whether the advice is any good. There is no grading key for
advice quality and this phase does not invent one. (3) It is not a controlled
comparison of wording: the grounded prompt is longer by construction, so
`snippet_too_long` falling 6 → 1 is consistent with "shown example prose, the
model wrote shorter snippets" but is not evidence for that mechanism over any
other. One model, one embedding model, one index, one run each.

- [x] Task 6.4c — the tests for the retriever seam. **Done.** Both sides of the
      join were tested and the join itself was not: nothing under
      `tests/checks/` mentioned a retriever, passages or sources.
      `tests/checks/test_advise_grounded.py` now pins the four things
      `advise.py` promises about grounding -- the passages reach the prompt,
      they sit *before* the instructions (the ordering Ollama's front-truncation
      makes a safety property, asserted by index against the template's own
      words), the attributions reach the entry, and a refused or unanswered
      finding keeps none of them -- plus `advise_all` passing the retriever to
      every finding. `tests/test_outputs.py` gains the first end-to-end
      `sources` in the suite: every other test set `store=None`, so
      `passages_for` short-circuited and no `sources` had ever been produced by
      the real chain. `tests/parsing/test_offline_containment.py` -- split out
      of `test_offline.py`, which was 40% over rule 18's line cap with two
      jobs in it -- now asserts that
      `retrieval/store.py` is the one chromadb importer -- claimed in that
      module's docstring, `requirements.txt`, `RAG_PLAN.md` and
      `knowledge/README.md`, and backed by nothing, while the analogous
      network-module claim beside it had a test -- with a planted second
      importer to prove the search fires. And
      `tests/retrieval/test_retrieve_probe.py` covers `_opened_index`'s
      `ImportError` arm: chromadb uninstalled under a built index degrades to
      `index_stale` instead of killing the audit. Two test helpers were widened
      to make it possible: `stub_knowledge` takes a store, and `stub_model` /
      `stub_model_unavailable` now cover `embed` -- they claimed to stub every
      model call and covered two of three.
- [ ] Task 6.5 — MITRE ATLAS as a second source, **deferred**. Its data is
      YAML with custom tags, needing PyYAML: a fifth stdlib exception for one
      file, and the very package the fixture's `VULN1-06` flags. Revival path:
      the STIX JSON bundles in `mitre-atlas/atlas-navigator-data`, readable
      with the stdlib; `KNOWLEDGE_SOURCES` then gains `mitre-atlas` with a
      schema bump.
- [ ] The `LLM02` label cites the wrong edition. `finding.py:23-24`,
      `SCHEMAS.md:647,886` and the prompt in `advise.py` say "from the 2025
      list", but the project uses `LLM02` for insecure output handling
      (`report_gaps.py:15`, the grading key) -- the **2023** numbering. In the
      2025 list LLM02 is Sensitive Information Disclosure and output handling is
      **LLM05**. Renaming a graded id would move Phase 4's numbers, so it is
      deferred; until then `retrieval/owasp_reference.py` states both halves
      and cites the 2025 LLM05 page, and the prompt no longer asserts an edition
      the reference block would contradict.

## Corpus removal — the evaluation's fixtures come out (2026-09-04)

**User decision, asked and reaffirmed.** The auditor takes any repository by
URL (Phase 5), so the user asked why a pinned corpus was still needed. The cost
was put to them plainly: the fixtures are what make Phase 4 a *measurement*
rather than a description, and without a grading key a finding cannot be
scored — Phase 6's measurement had already hit this, reporting only refusal
counts because fetched apps have no keys. They reaffirmed, and chose the scope:
**fixtures and plumbing out, `src/evaluation/` and `src/baselines/` kept** as
machinery that can score any audited app against a key placed beside it.

- [x] **Provenance preserved before anything was deleted.** `docs/REPORT.md`
      gained Appendix A: the three apps with their upstream URLs and exact
      commits, and `STARTER-01` transcribed field by field — the grading-key
      entry that existed *only* in `docs/evidence-overrides/` and was never
      committed. Without this, every §6 figure would have become unfalsifiable
      rather than merely unrepeated. The numbers are kept with their inputs
      named; deleting a measurement because its input was withdrawn would have
      left §6 describing a system nobody had measured.
- [x] **`src/corpus_paths.py` → `src/grading_keys.py`.** `grading_keys/` at the
      repo root replaces `corpus/evidence/`; `key_path` and
      `discover_graded_apps` replace `evidence_path` and
      `discover_corpus_apps`. Named `grading_keys` rather than `evidence_paths`
      because "evidence" is already this project's word for what a *finding*
      cites, in 19 modules. Gone with the corpus: `CORPUS_DIR`, `app_path`,
      `app_is_present`, `RESERVED_APP_NAMES`, `DOWNLOAD_HINT` — a graded app is
      now one the user audited from wherever they pointed the tool, so the
      project owns no path to its source and cannot say whether it is present.
      **`discover_graded_apps` returns `()` instead of raising on empty**: zero
      keys is the normal state now, not a broken checkout.
- [x] **The two evaluation CLIs changed shape.** `run_baseline.py` takes a
      repository path the way `main.py` does, instead of walking the corpus,
      and derives the artifact directory name through `repo_url.SAFE_NAME`
      rather than a second validator. `evaluate.py` gained `--keys-dir` and
      scores every app `discover_graded_apps` finds. **An app with a key and no
      artifacts is still a hard error, never a quiet skip** — `evaluation.json`
      has no field for who was skipped, so a skip would ship as a complete
      score over fewer apps than a reader assumes. That was the one thing the
      guard refused in the first draft of this plan.
- [x] **A grading key is now hand-placed input, so it is validated.**
      `harness._check_key` refuses a key missing a field, on the wrong
      `schema_version`, or with a non-list `findings`, naming the fault.
      Previously `scorer.py` read the key's fields raw and the only shape check
      lived in `tests/corpus/test_ground_truth.py` — which this change deletes.
- [~] **Rule 13 amended in `docs/CODING_RULES.md`**, the binding standard --
      **awaiting the user's sign-off, see B10.** Written, and the two
      sub-agent definitions now cite it as binding, but an edit to the graded
      standard is not the tooling's to make final. It
      said "validate each task against the demo apps in `corpus/`", which is no
      longer possible. It now says a test builds whatever tree it needs inside
      the test, so the suite passes on a clean checkout with nothing
      downloaded. An edit to the graded standard is recorded rather than made
      silently.
- [x] **Safety guards re-anchored, not dropped.** The corpus supplied the
      realism for the offline, no-mutation and baseline-determinism guards. Each
      moved to a tree the test writes, keeping a non-zero count assertion so it
      still has a falsifier — and each docstring now admits what a synthetic
      tree gives up: no oversized file, no non-UTF-8 source, no malformed
      `.ts`, no unforeseen code shape. The source-and-settings guards
      (`test_offline_containment.py`, `test_no_write_commands.py`,
      `test_scorer_boundary.py`) never needed a fixture and are now the primary
      evidence for the offline claim.
- [x] **`tests/test_scorer_boundary.py` was about to stop guarding.** It
      asserted `scored_modules_importing("corpus_paths") == set()` against a
      hardcoded module name; after the rename that is vacuously true. Updated,
      and given the planted-import mutation check it never had.
- [x] Docs: README (the restore section replaced by "Scoring an audit against a
      grading key"; layout; the headline result now names where its inputs
      went), `FLOW.md`, `SCHEMAS.md`, `.claude/AGENTS.md`, `RAG_PLAN.md`,
      `.gitignore` (including two comments that cited the pattern being
      removed), and `docs/PHASE_4_PLAN.md`. `PHASE_1..5_PLAN.md` and
      `ADVISORY_PLAN.md` are left as **history** — they are plans of record for
      shipped phases, and rewriting the past to match the present is how a
      project loses the ability to say what it once decided.
- [x] `docs/evidence-overrides/` deleted, after its contents were transcribed
      into `docs/REPORT.md` Appendix A. It existed only to preserve an
      uncommitted corpus grading-key edit.
- [x] **The docs tick above was premature and is corrected here rather than
      quietly re-ticked.** The guard's second pass found three things wrong in
      files this section had already claimed as done: `README.md`'s
      `run_baseline` examples still omitted the new required path argument, so
      a documented command exited 2; the Licence line was a garbled half-edit;
      and `.claude/AGENTS.md` still carried four corpus-dependent instructions,
      one of which ("fetching by URL was built and removed again") contradicted
      Phase 5 having shipped, and another of which told a reader to validate
      against demo apps two paragraphs after saying none exist. All fixed. The
      lesson is the tick's, not the guard's: a doc edit is done when the
      commands in it run. **A later pass found two more**, both in files this
      section had claimed as done: `docs/SCHEMAS.md` and `docs/REPORT.md` each
      stated as live fact that a test checks every `code_anchor` against the
      real source line -- that test lived in `tests/corpus/` and was deleted
      here, so the field is recorded and no longer enforced. Both now say so.
      A schema contract is not a place to leave an enforcement claim standing
      after its enforcement is gone.
- [x] **The pin refusal was claiming more than it checked.** `_check_app` said
      a key without a manifest "is unpinned: a key's line numbers mean nothing
      without the commit they were read at", while testing only that the file
      existed -- a manifest holding `{}`, or holding no JSON at all, enrolled
      the app. Since that pin is the whole reproducibility guarantee behind
      Appendix A, the manifest is now read and a non-empty `upstream_commit`
      required, with four tests for the ways it can pin nothing (`{}`, non-JSON,
      `null` and the empty string) -- and a JSON syntax error now raises its own
      refusal rather than being reported as a missing field, which would send a
      reader after a field their file may well contain.
- [x] **Two limits of the key validation, recorded because neither shows up as
      a failing test.** (1) `ENTRY_FIELDS` was first written with
      `surface_name` in it, which `SCHEMAS.md` marks optional and `grading.py`
      reads with `.get()` -- so it would have refused a valid key for an entry
      tied to no named surface. Corrected to the **four fields the scorer
      subscripts unguarded** -- `id`, `file`, `line`, `owasp_id` -- a *subset*
      of the eight `SCHEMAS.md` requires, deliberately: the job is to turn a
      crash into a message, not to restate the schema. `llm_surface`,
      `surface_name` and `component` are all read through `.get()`-truthiness
      guards in `grading.py` and cannot raise, so requiring any would refuse a
      valid key. (An earlier draft of this very line said "the five genuinely
      required fields", which was the same class of mis-statement again.)
      **A check stricter than the schema is as wrong as one that is looser, and
      harder to notice, because its own tests pass.** (2) There is **no
      converse guard** for `ENTRY_FIELDS` the way there is for `KEY_FIELDS`:
      the top-level one works because every scorer function names the parameter
      `key`, but entries are read as `entry[...]` and `e[...]` in `scorer.py`
      and as `key_entry[...]` in `grading.py`. **That claim was wrong, and I
      made it three times before a review pass killed it.** A scan of
      `scorer.py` over `entry` and `e` returns exactly the four fields, so the
      guard is possible and now exists.

      I also said `grading.py` was out of scope because its entry reads were
      all `.get()`-guarded. **That was wrong too.** It has six entry
      subscripts, and three of them -- `file`, `line`, `owasp_id` -- are plain
      reads that would crash; they were covered only because `scorer.py` reads
      the same three, which is coincidence. Extending the scan there does not
      work naively either: `subscript_keys` sees `key_entry["llm_surface"]`
      even though it sits after `key_entry.get("llm_surface") and` on the same
      line, so a bare scan demands fields no key need carry. Closed by naming
      a second tuple, `GUARDED_ENTRY_FIELDS` -- the fields subscripted *only*
      after a `.get()` test -- and asserting both modules' reads fall in the
      union, so a new read in either belongs to neither tuple and fails.

      **A fourth pass caught that this was still not "construction".** The
      union scan proves no read is *unnamed*; it does not stop someone
      silencing it by appending a crashable field to the guarded tuple. That
      needed a second scanner -- the string arguments of `.get()` calls -- and
      an assertion that every name in `GUARDED_ENTRY_FIELDS` really is
      `.get()`-tested, so padding the tuple fails until the guard is written.
      Its own residual limit, stated rather than glossed: it proves guard and
      subscript live in the same module under the same name, not that the guard
      dominates that subscript. Verified by mutation -- a genuinely unguarded
      read planted in `grading.py` *plus* the tuple padded to match it fails
      the new test, and passed the union cover test, which is the hole
      reproduced.
      **And the extraction itself left a duplicate that falsified a claim I
      wrote in the same change.** `tests/checks/test_workflow_scope.py` still
      had its own `string_literals` (byte-identical to `ast_scan`'s) and its own
      `called_names` -- a *different* function under the same name, bare
      `node.func.id` where `ast_scan`'s returns the dotted chain. Two docstrings
      then claimed "exactly one copy of each scanner". Fixed by importing, and
      **pinned by a test** that asserts each scanner name in `ast_scan.py` is
      defined once across `tests/`, derived from `ast_scan` rather than a
      hardcoded list. The prose claim of uniqueness is what let a byte-identical
      copy sit there; a claim about the tree belongs in a test, not a docstring.
      **That guard paid for itself on its first run**, finding a duplicate
      nobody was looking for: `parse` was defined three times -- the scanner,
      plus one in `detector_helpers.py` and one in `detector_helpers_js.py`
      that parse a fixture *snippet string* rather than a file. Not copies, but
      one name with three answers, which is the hazard. Renamed to
      `parse_snippet` in both helpers rather than allowlisting the name, since
      an allowlist would have exempted the most collision-prone scanner exactly
      where the guard matters most.
      **Five drafts of this work miscounted something**, and the last two were
      counts *in the comment about counting*: "nine other guards" became "ten"
      and was wrong again, because the same edit that fixed it added two
      importers. The durable fix is not counting more carefully -- it is not
      writing the number. `tests/test_scorer_boundary.py` says "shared with
      every other guard" and cannot rot; the numbers in
      `test_no_write_commands.py` and `test_ast_scan.py` were deleted rather
      than corrected. **A count in a comment is a fact with no test behind it**,
      which is the same defect as the uniqueness claim two paragraphs up.
      Swept the rest of the tree for the same shape afterwards, since five
      instances raises whether it is systemic. **The sweep found two rotten and
      then I wrote a sixth** -- a fresh count, into the docstring of the module
      whose whole thesis is that counts in prose rot, in the same round that
      recorded the lesson. Deleted. So the honest version of the sweep's result
      is: nothing pre-existing was rotten beyond those two, and the failure mode
      is not a stale tree but the reflex to quantify while writing.
      `knowledge_fixtures.py`'s "four test files build the same index" is
      correct, and the other numeric claims ("the scorer opens three files",
      "one of three scored systems", "one of four modules that start a
      process") are closed-vocabulary design facts with tests behind them,
      which is the difference between a count and a contract.
- [ ] **One-name-two-answers survives in the detector helpers**, flagged rather
      than fixed because renaming them is its own task (rule 15).
      `parse_snippet` returns `ast.AST` in `tests/detector_helpers.py` and
      `tuple[Node, bytes]` in `tests/detector_helpers_js.py`; `only` and
      `other_detectors` are duplicated across the same pair. The
      `tests/test_ast_scan.py` guard cannot see these -- it covers the names
      `ast_scan.py` defines, and tree-wide uniqueness is not the rule, since
      40-odd fixture helper names are legitimately defined in more than one
      test module (`refuse` in six files, `audit` in five). Worth a pass that
      gives the language-specific pair language-specific names.
      Two smaller things this left, recorded rather than rediscovered:
      `GUARDED_ENTRY_FIELDS` is a constant in `src/` with **no production
      reader** -- it exists so the tests can classify a read. It now lives in
      `grading.py`, beside the guarded subscripts it describes, rather than in
      `harness.py`: it was put at the I/O edge first because `ENTRY_FIELDS` is
      there, which is proximity to a *sibling* rather than to the code the
      constant is about. And `tests/test_no_write_commands.py` was 258 lines while
      **ten** test modules import its scanners (three of them the
      `subscript_keys`/`get_call_keys` pair, the rest `parse`) -- a test module
      doubling as a helper library, and `get_call_keys` was added to a module
      that never calls it. Moved to `tests/ast_scan.py`. An earlier draft of
      this line said "four import sites", which is the same undercount the
      rule-18 table above was already corrected for: **a number quoted to
      justify a deferral is the one number worth checking.**

      Two other things came out of it. `OPTIONAL_ENTRY_FIELDS` was a wrong
      name: `SCHEMAS.md` marks `llm_surface` required-but-nullable, so
      "optional" was false for one of the three, and `line_end` is genuinely
      optional yet absent because nothing subscripts it. And the limit about
      `e` still stands: it is a generic comprehension alias, so unlike `key`,
      `findings_document` and `surfaces_document` the name is not
      self-guarding.
      **The lesson is
      about the shape of the mistake:** "a guard is impossible here" is a claim
      that stops anyone looking, so it needs more evidence than "a guard would
      be awkward", and I asserted it from the latter.
      The two *artifacts* got the same treatment, and the absence of a
      converse guard there had hidden a real hole -- `FINDINGS_FIELDS` and `SURFACES_FIELDS` listed
      three of the seven fields `scorer.py` subscripts, so `findings.json`
      short of `coverage`, `model_run` or `schema_version`, and
      `surfaces.json` short of `skipped_files`, each still left the CLI as a
      bare `KeyError` traceback while every test passed.
- [ ] **`code_anchor` is required by the schema and validated by nothing.** Its
      drift test went with the corpus, and it is not in `ENTRY_FIELDS` because
      that list has one criterion (what would crash the scorer) and this would
      not. Checking it is *present* costs no file read and recovers the cheap
      half of what the deleted test gave; checking it still *matches* the
      source needs reading the audited tree at score time, which the scorer
      deliberately does not do. Same for `title` and `description`.
- [x] **Three re-anchored guards were exercising less than they claimed** --
      the risk named when this scope was chosen, and found by measurement
      rather than by reading. The blocked-socket workflow reached the taint
      check but got nothing out of it (the pinned app had produced a taint
      finding); the mixed-app fixture's comment claimed its two findings came
      from two different checks with nothing asserting it; and
      `test_no_mutation.py`'s docstring admitted "no malformed `.ts`" over a
      tree holding two Python files, so it covered neither the tree-sitter
      backend nor a dependency manifest. Each fixed at the fixture, not at the
      assertion.

**Five modules are at or over rule 18's ~200 lines and are deliberately left
alone**, named here so the next person does not have to find them. Measured
with `wc -l`, not estimated -- an earlier draft of this paragraph said "three"
and named a fourth file that is under the line:

| Module | Lines | The cut, when it comes |
|---|---|---|
| `src/fetch_repo.py` | 214 | its manifest authoring (`manifest`, `write_manifest`, `manifest_path`) |
| `src/artifacts/findings_document.py` | 211 | pre-dates this session |
| `src/artifacts/remediation.py` | 207 | its source-attribution validation |
| `src/detectors/detectors.py` | 204 | pre-dates this session |
| `src/export_reports.py` | 203 | pre-dates this session |

Whichever gains the next field goes first. `src/retrieval/retrieve.py` was
split at 232 during Phase 6 because it had two clear jobs; these five are one
job each, which is why they are flagged rather than cut. `src/main.py` at 197
is the next to watch, then `src/retrieval/manifest.py` at 195.

**Rule 18 covers test modules too, and thirteen are over the line** -- worst
`tests/test_outputs.py` 264, `tests/retrieval/test_retrieve_probe.py` 259,
`tests/evaluation/test_harness.py` and `tests/cli/test_export_reports.py` 241.
Each is one module's tests, so they are left alone; the exemption is stated
rather than assumed.

**Three files were split rather than exempted, because each held two jobs** --
which is the trigger rule 18 actually names, as against the line count:
`test_key_entry_check.py` at 256, split with `test_entry_field_cover.py`;
`test_artifact_check.py` at 198, split with `test_artifact_field_cover.py`; and
`test_no_write_commands.py` at 258, split with **`tests/ast_scan.py`**, which also
ended **the worst instance** of a test module doubling as a helper library --
ten importers. Cross-test-module imports remain elsewhere -- fixture helpers
rather than scanners (`load`/`stage`/`write_json` from `test_harness`,
`hash_tree` from `test_no_mutation`, `trace`/`surface` from `test_taint`,
`trace_agent_call` and its siblings from `test_taint_methods`, `stage_reports`
from `test_export_reports`). **No count here on purpose**: this one rotted
three times, twice inside the change that corrected it. `grep -rn '^from test_'
tests/` answers it, and cannot go stale; those are fixture helpers rather than scanners,
and are recorded here rather than claimed gone. The three
files that still import constants from it import the *rule* (which programs may
be launched), not the scanning, so that coupling is correct. The **resulting**
sizes are deliberately not quoted: they were, twice, and rotted twice inside one
session -- once when a test was deleted, once by an off-by-one. The line count
that *motivated* a split is history and stays put; the count after it is a fact
about the current tree, which is what `wc -l` is for.

**Suite state, since the removal's whole point was to stop the fixtures gating
it.** Before: **1841 passed, 326 skipped** -- every skip "the app is not
downloaded". After: **1950 passed, 0 skipped** on a machine with every optional
tool installed -- **1997 passed and 2 strict xfails** after the follow-up
work, 2028 after the LLM01 three-way method gate -- and roughly a dozen skips on
a machine with none of those tools. The
xfails are the recorded taint defect, strict, so they fail the suite the day
the detector is fixed. The
disappearance of those 326 is the measurable fact that the corpus gating is
gone; the remaining skips are about Syft, Trivy, vexctl, Ollama and fonts, and
that number is a fact about a machine rather than about the suite.

**What this costs, stated plainly.** No number in `docs/REPORT.md` §6 can be
re-taken without re-cloning the three repositories from Appendix A. Phase 4 is
machinery with no shipped subject: `tests/evaluation/` and `tests/baselines/`
still exercise the scorer, the one join rule and both baselines against
synthetic data, but nothing in this
repository measures the auditor's accuracy any more. That is the trade the
decision made, and it belongs here rather than in a footnote.

## LLM01: the attribute-callee half fixed, two shapes still blind (2026-09-05)

**Half of the open defect recorded 2026-09-04 is closed.** `agent.invoke(...)`
and `agent.run(...)` -- the standard modern LangChain spellings -- are now
traced. `bindings.called_name` is replaced by two pure helpers, `receiver_name`
(the callee for `f(x)`, `obj` for `obj.m(x)`, `""` for a deeper chain) and
`method_name`.

**The fix nearly shipped a false positive, and that is the part worth
remembering.** The first design resolved the receiver and stopped there. My
stated reasoning was that `reached` holds only names bound at an
`AGENT_DEF`/`TOOL_CALL` line, so no unrelated object could match -- true, and
beside the point. It made *every method* on a surface-bound object count as
consumption, and configuration APIs are as common as `.invoke` on exactly those
objects. `project-guard` refuted it with a reproduction I then confirmed by
hand:

```python
api_key = os.getenv("OPENAI_API_KEY")   # DATA_SOURCE
llm = ChatOpenAI()                      # AGENT_DEF
llm.bind(api_key=api_key)               # -> "Untrusted input reaches the model"
```

Nothing reaches the model there. **A security tool's wrong "yes" is worse than
the miss it replaces**, and this one wore a plausible title. Closed by gating on
the method as well as the receiver: `CONSUMING_METHODS` in `taint.py`, because
"which method consumes a value" is taint semantics rather than syntax. A bare
`agent(x)` names no method and always consumes.

Measured after the fix:

| Shape | Findings | |
|---|---|---|
| `agent(question)` | 1 | unchanged |
| `agent.invoke(question)` | **1** | newly found |
| `agent.run(question)` | **1** | newly found |
| `llm.bind(api_key=question)` | **0** | false positive prevented |
| `agent.add_node(question)` | **0** | false positive prevented |
| `agent.runnable.invoke(question)` | 0 | still blind |
| `agent.invoke({"input": question})` | 0 | still blind |

- [ ] **Two shapes remain blind, and still record no `INCONCLUSIVE` probe** --
      a receiver that is not a local name, and a value passed inside a
      container. A strict xfail holds each in
      `tests/checks/test_taint_defect.py`, so the suite goes red the day either
      is fixed and the entry cannot be forgotten. The dict-literal half was
      deliberately skipped here on measurement, not taste: across `fetched/`,
      **213** calls take the `obj.method(x)` shape against **2** that pass a
      dict literal carrying a bare name -- measured over 5 Python files in 2
      repositories, which is the denominator that ratio needs and did not
      originally carry.
- [x] **The closed list turned out to be a third silent stop, and the fix for
      the defect had introduced it.** `agent.generate(question)` -- a method
      simply absent from `CONSUMING_METHODS` -- produced no finding *and* no
      probe. `project-guard` also found the list internally inconsistent:
      `predict`/`apredict` and `stream`/`astream` were in it, `generate` was
      not. Closed by giving the gate **three** answers instead of two:
      `CONSUMES` (a finding), `CONFIGURES` from a named
      `CONFIGURING_METHODS` (silent, and rightly -- nothing is inconclusive
      about `llm.bind(key)`), and `UNKNOWN_METHOD` (an `INCONCLUSIVE` probe
      naming the method). An unknown method is not evidence of configuration,
      and filing it as such is how a closed list becomes silence. The probe
      reuses `trace_left_static_analysis`, so no schema change. **This is the
      lesson of the whole entry arriving twice**: the first fix traded a miss
      for a false positive, and the second traded it for a new silence. The
      list is now safe by construction rather than by remembering to extend
      it.
- [ ] **The honesty half is still owed for the two remaining shapes.** There
      are now two probe producers, not one: `_unfollowed` reports a source never
      bound to a name, and `_unknown_method_probe` a method neither list knows.
      Neither catches a deep chain or a container, so those two still read as
      *traced and clean*. Fixing them does not need the capability work.
- [ ] **`CONFIGURING_METHODS` is safe against absence, not against membership.**
      A name missing from it falls through to a probe; a name wrongly *present*
      is silent, and no test can tell it from a correct entry. `bind` is the one
      to watch -- it binds kwargs forwarded at invocation time, so
      `llm.bind(api_key=key)` is not a consumption while
      `llm.bind(extra_body=untrusted)` arguably is. Stated in the module comment
      rather than fixed, because the alternative is probing every configuring
      call.
      **The mirror cost, now that a missing name is loud:** a real consuming
      method outside `CONSUMING_METHODS` -- `astream_log`,
      `batch_as_completed`, `abatch_as_completed` are absent today -- downgrades
      a genuine flow from a finding to a probe. Precision lost, not silence,
      which is why they are recorded here rather than added in a rush.
- [ ] **`src/checks/taint.py` is 211 lines**, over rule 18's ~200, having grown
      from 139 with this work. The natural cut is the method gate -- the two
      vocabularies and `_verdict` -- which answers "does this call consume its
      argument", a different question from "where does this value go". Flagged
      rather than taken.
- [ ] **Pre-existing, found in passing:** `taint._surfaces_by_line` keys by
      line, so `settings = json.load(open("s.json"))` drops one of the two
      sources on that line -- the finding anchors on `open` rather than
      `json.load`. Not touched here (rule 15).

## Four requested features, re-planned after measurement (2026-09-05)

The user asked for four fixes. `project-guard` simulated all four against the
four repos in `fetched/` before a line was written, and **three of the four did
not survive**. Recorded because the plans were mine and the measurements are
the only reason they did not ship.

- [ ] **1. `self.x = call()` binding -- DO NOT DO AS PLANNED. It is inert.**
      I claimed it was "~5 lines, unblocks LLM01 on the RAG repo". Applied
      exactly as specified and re-run, the output is byte-identical: 0 findings
      before, 0 after. Verified twice, once by the guard and once by hand.
      The reason is that `retriever` at `main.py:277` is *already* a plain
      `ast.Name` binding in the same scope; binding `qa_chain` adds a key
      nothing looks up. **The real gap is a missing rule**: a tainted value
      passed into the *sink-construction call itself*
      (`RetrievalQA.from_chain_type(retriever=retriever)`), where
      `receiver_name` answers `"RetrievalQA"` and nothing is in `reached`.
      That rule fires -- measured, `main.py:332` -- but see the next line.
- [ ] **1a. The sink-construction rule needs an argument allow-list first.**
      Measured on the same file: it also reports
      `ChatOpenAI(api_key=os.getenv(...))`, an env-var credential, as untrusted
      input reaching the model. **One true positive and one false positive, on
      the only app it fires on.** Gate on the keyword with a `CONTENT_ARGUMENTS`
      allow-list (`retriever`, `input`, `query`, `question`, `context`,
      `documents`, `messages`), the same direction as `CONFIGURING_METHODS`: a
      missing name is a miss, not a false finding.
- [x] **2a. `from_lockfile` per component -- DONE, and it was a live bug, not a
      prerequisite.** `sbom.py` computed it document-wide, so the mere presence
      of `yarn.lock` relabelled every component that had a version as `locked`
      -- including versions the generator guessed -- which granted them a
      **versioned purl**, the key `known_advisory` joins CVEs on. Any npm app
      with a lockfile hit this. Fixed by reading the generator's own
      `syft:location:<n>:path` evidence per component, via `is_lockfile_path`
      beside `LOCKFILE_NAMES` and a pure `_lockfile_pinned` helper;
      `_reported_versions` is untouched, an earlier attempt that threaded a
      tuple through it corrupted `version` into a two-element array and the purl
      into `pkg:npm/x@('9.9.9', True)`. `docs/SCHEMAS.md` described this bug as
      *prevented* -- it reasoned the Python path was safe and never noticed the
      npm path did the same thing -- and now describes what actually happens.
- [ ] **2b. An unversioned purl is published as *unreached*, which is a
      positive claim of safety.** Reproduced 2026-09-05, not inferred:
      `deps/trivy_runner.py:68` indexes advisories by **versioned** purl, while
      a component whose version the SBOM could not establish reaches
      `mapping.json` with a bare `pkg:pypi/<name>`. The two never join. Run
      against a mapping entry `pkg:pypi/langchain` reached by an `AGENT_DEF`
      surface and an advisory keyed `pkg:pypi/langchain@0.1.0`,
      `find_known_advisories` returns **0 findings** and `unreached_components`
      returns that very component -- so the tool both misses the advisory and
      *asserts* nothing reaches it. That assertion is the evidence a VEX
      `vulnerable_code_not_in_execute_path` statement rests on, and it flows
      into `findings.openvex.json` and `docs/REPORT.md`.
      The real app has two such purls today: `pkg:pypi/langchain` and
      `pkg:pypi/streamlit`, both unversioned, both reached.
      **The fix is not to match on name alone** -- that would claim an advisory
      applies to a version never established, inventing the opposite error.
      A component whose reach cannot be decided is *undecided*, not unreached,
      and saying so needs a third bucket beside `unreached_components`. That is
      a coverage-key change: `schema-keeper` first, then `project-guard`.
- [ ] **2. Python lockfiles -- two tasks left.** `Pipfile.lock` is
      **JSON**, not TOML, so it ships on the stdlib today; only `poetry.lock`
      and `uv.lock` need `tomllib`, which is 3.11+ while this project declares
      3.10+. Raise the floor rather than add `tomli` -- a fifth stdlib
      exception for two files is not proportionate, and nothing tests the 3.10
      claim. **The prerequisite is a schema-behaviour fix**: `sbom.py`'s
      `from_lockfile` is computed *document-wide*, so the moment a lockfile
      appears every Python component with a version flips `inferred` ->
      `locked`, which reaches the purl, which `known_advisory` joins on. False
      precision straight into advisory findings. Per-component first.
- [x] **3. LLM02 -- ship the SQL rule, not the dataflow one.** The motivating
      grading-key entry is `cursor.execute(f"SELECT ... {userId} ...")`, and
      `argument_names` collects `ast.Name` only, so an f-string argument yields
      an empty set: no dataflow rule built on it can ever match. The syntactic
      rule -- an f-string/`%`/`+`/`.format()` argument to `*.execute(...)` --
      reaches the entry and needs no bindings work. The shell half
      (`os.system`, `subprocess`, `eval`) has **zero subjects** across all four
      fetched apps, so it is deferred rather than built. Keep the `LLM02`
      spelling and state the edition: the id is enforced in `finding.py` and
      spelled in the baselines, the report and the grading keys.
      **Shipped** as `src/checks/output_handling.py`. Two things the plan did
      not say and the gate made explicit. The title is
      `"Database query built by string interpolation, not parameterised"`, not
      "model output reaches a database": the check establishes the *sink* half
      of LLM02 and cannot establish that the interpolated value came from the
      model, because an f-string yields no `ast.Name` to bind. And it is
      scoped to LLM apps *by the planner*, not inside the check -- planned only
      when the repo has an `AGENT_DEF` or `TOOL_CALL` surface, so a plain
      Python service gets the check absent from `checks_run` rather than
      silent, and `security-agent-testbed`'s published 0 findings still holds.
- [x] Two verified silent misses in `output_handling.py`, pinned by tests so
      they cannot change unnoticed. Only the argument expression is judged, so
      `q = f"SELECT {x}"` followed by `cursor.execute(q)` reports nothing, and
      neither does `.format_map(d)`. The first needs the binding the taint
      trace already builds; the second is one name in `_formats_a_value`.
      Recorded because the check is named in `coverage.checks_run`, where
      silence means "looked and found nothing".
      **Pinned** by `test_a_query_built_into_a_variable_one_line_earlier_is_missed`
      and `test_a_format_map_query_is_missed` in
      `tests/checks/test_output_handling.py`, both named as gaps rather than as
      desired behaviour. Closing either makes its test fail, which is the
      point; the `.format_map` half was mutation-checked. The *misses
      themselves* stay open above
- [ ] `output_handling._is_literal_text` judges `%` by shape, not by value, so
      `execute("SELECT %s" % ("literal",))` **is reported** while
      `execute("SELECT %s" % "literal")` is silent -- the tuple is neither a
      `Constant` nor a nested `BinOp`, so it reads as dynamic. Found by
      `test-writer` running the case rather than assuming it; pinned by
      `test_a_percent_query_interpolating_a_literal_tuple_is_reported`, whose
      docstring says it asserts the behaviour rather than the ideal. Low harm
      (the advice is parameterisation either way) but the asymmetry is
      arbitrary, and a reader deserves better than "the shape decides"
- [ ] `owasp_reference.REFERENCES["LLM02"]` summarises the risk as "model
      output is passed to another component", which is exactly what
      `output_handling.py` disclaims. The finding title is honest and the
      advice prompt beside it is not. It is a class-level entry, so the fix is
      not to edit the reference -- decide whether the advice prompt should cite
      the check's own title instead
- [ ] Report `executescript` alongside `execute` and `executemany`. It cannot
      be reached today: the finding is anchored on a `DATA_SOURCE` surface and
      `detector_names.DATA_SOURCE_METHODS` has no `executescript` entry, so no
      surface exists to anchor on. Adding one is a **detector** change and
      belongs in its own change; `output_handling.EXECUTE_METHODS` raises at
      import if it ever names a method the detector table does not supply
- [x] **4. AUDITABILITY -- shipped as a Finding, not a probe.**
      `src/checks/auditability.py`, rule id
      `agent_defined_without_callback_handler`, title "Agent constructed with
      no callback or handler argument". **No schema change**: it emits a
      Finding, so the `PROBE_REASONS` value the old plan needed is void, and
      `AUDITABILITY` was already in `OWASP_IDS`.
      Three corrections the gate forced on the requested design. It is scoped
      to `AGENT_FACTORIES` -- the detector's own set, named rather than copied
      -- rather than all `AGENT_DEF`, because `AGENT_DEF` also covers bare
      model clients and "auditability of agent *actions*" is not a claim about
      `ChatLiteLLM(...)` -- that alone dropped this app from 3 findings to 2.
      The `LANGCHAIN_TRACING_V2` limb was dropped: **zero subjects** across all
      four fetched apps, and "near the definition" is an unnamed proximity
      window that re-imports the module-layout dependence the old design was
      parked for. And the title asserts the structural fact, not the
      conclusion.
      Language-narrowed after the gate found the planner blind to it: the JS
      and Python `AGENT_FACTORIES` share `StateGraph`, `MessageGraph` and
      `AgentExecutor`, so a TypeScript agent made `has_agent_surface` true, the
      check was planned, `run_over_repo` read Python only, and AUDITABILITY was
      published as examined with nothing found -- a blind spot dressed as a
      clean result. `_is_auditable_agent` now requires `language == PYTHON` and
      is the single place agent-hood is decided; the duplicate
      `AGENT_FACTORIES` test in the call walker was removed once the gate
      proved the two were equivalent mutants.
      Tests: `tests/checks/test_auditability.py` (what it reports),
      `test_auditability_subjects.py` (what counts as a subject),
      `test_check_scope.py` (what reaches `coverage`).
      Measured: `main.py:69` and `main.py:71` on `damn-vulnerable-llm-agent`,
      the second being **VULN1-05's anchor**. Planner-scoped, so
      `security-agent-testbed`'s published 0 findings still holds.
      **The known false positive, accepted deliberately**:
      `RAG-Examples-with-Langchain` imports `logging` and calls `logger.info`
      ~30 times but passes no `callbacks=`, so all three of its agents are
      reported. The alternative is a registry of blessed handler class names,
      which is the LangSmith name-matching this project already rejected.
      **The unfixable cost**: AUDITABILITY entering `risk_classes_checked`
      turns VULN1-05's miss reason from `no_check_for_risk_class` into a scored
      comparison, and the grading keys went with the corpus -- so the 2-of-6
      cannot be re-measured. No new number is published.
      **Narrowed again after the gate's second pass**: the planner gate was
      language-blind, so a TypeScript agent -- `detector_names_js` shares
      `StateGraph`, `MessageGraph` and `AgentExecutor` with the Python set --
      planned a check that reads `.py` only, and AUDITABILITY was published as
      examined with an empty finding list. `_is_auditable_agent` now requires
      `PYTHON` and is shared by the check and the gate, which used to spell the
      predicate twice. Tests: `tests/checks/test_check_scope.py` (the
      TypeScript case, through `coverage`) and
      `tests/checks/test_auditability_subjects.py` (the name sets are
      disjoint, so a model client can never be a subject)
- [ ] **4 (superseded, kept for the trail). AUDITABILITY -- probe only, and not yet.** My file-scoped
      absence check inverts on the one app with subjects: in
      `damn-vulnerable-llm-agent` it reports `tools.py` (tool surfaces, no
      logging) and stays silent on `main.py`, because `main.py:82` has
      `callbacks=[st_cb]` -- a Streamlit *display* handler. So it fires on
      module layout and is silenced by a UI widget. That is the same objection
      I raised against checking for LangSmith, reproduced by my own design. It
      also needs a new `PROBE_REASONS` value, which is a schema-vocabulary
      change with three readers -- `schema-keeper` first.

**Two consequences worth stating before either check ships.** Five documents,
`docs/REPORT.md` among them, assert that LLM02 and AUDITABILITY have no check.
And adding a class to `risk_classes_checked` converts "no check covers this"
into an ordinary miss in the scorer, so the published 2-of-6 can look *worse*
with unchanged behaviour -- and the corpus is gone, so it cannot be re-measured.

## Phase 7 — an LLM in the planner, and a probe that does not overclaim (2026-09-05)

Requested: an `auditor_planner` that uses the local model to route the audit,
and a `probe_injection` stage. Plan of record: `docs/PHASE_7_PLAN.md`, written
before any code because `docs/PHASE_4_PLAN.md` records being built before its
plan and calls that a defect.

**The finding that reframed the request.** `src/checks/workflow.py`'s `plan()`
is `{"steps": state["steps"] + 1}` and `act()` takes `remaining[0]` -- the order
is fixed before the graph starts. So `docs/FLOW.md:266`'s published sentence,
"The planner chooses which check runs, and nothing else", **is already false**.
This phase does not add agency to a working planner; it makes a published claim
true for the first time.

**The line, quoted from this project's own documents.** `docs/FLOW.md:266` and
`docs/PHASE_3_PLAN.md:192` both forbid a planner that decides what counts as a
finding. The request's step 5 -- static checks process "only the surfaces the
LLM planner explicitly marked" -- crosses it: a surface the model declines to
mark yields no finding, and the absence lands in `coverage.checks_run`, which
`docs/SCHEMAS.md` defines as "could not look at all" and
`src/evaluation/scorer.py:56` converts to `no_check_for_risk_class`. Rejected.
**The rule adopted instead: the planner may ADD and ORDER, never SUBTRACT.**

- [x] **7.0a -- move the pick into the planner node.** `plan()` makes the pick
      via `choose_next`; `act()` runs `state["chosen"]` and refuses `None`.
      **Not** "makes `docs/FLOW.md` true", which is how I first wrote it: the
      pick is still `remaining[0]` and every eligible check still runs, so this
      moved a constant rule into the node the docs say owns it. `project-guard`
      caught the overclaim -- the same class of error as the LLM02 title
- [x] **7.0b -- correct the two published sentences.** `docs/FLOW.md`'s "The
      planner chooses which check runs" implied a power to subtract the planner
      has never had and must never gain; it now says the planner chooses the
      **order**, never which ones run. `docs/PHASE_3_PLAN.md` is annotated
      rather than rewritten -- it is a plan for a shipped phase, and the repo's
      convention is to annotate those, not revise them retroactively
- [ ] **7.0 (superseded, kept for the trail) -- make `plan()` real, with no model.** The planner selects from
      `remaining` rather than the graph walking a fixed list; the decision is
      recorded; `docs/FLOW.md:266` and `docs/PHASE_3_PLAN.md:192` corrected to
      match the code. Standalone, zero risk, no model, no schema change
- [x] **7.1 -- `src/checks/planner.py`, pure functions only.** Prompt, parse,
      validate against `workflow.KNOWN_CHECKS`, merge monotonically. **No
      `model_client` import**; `tests/parsing/test_offline_containment.py`
      gains the module as structural proof. The model function is a parameter,
      the way `advise.py` takes its `Retriever`
- [x] **7.2 -- wiring, and `planner.json` as an artifact of its own.** The
      model is consulted at the **edge**, in `build_findings`, and the answer
      passed as the `plan_order` parameter `workflow.audit` already takes. Not
      inside a graph node: `tests/parsing/test_offline.py:126` asserts
      `no_network.attempts == []` and counts **attempts, not successes**, so a
      model call in a node fails it even when it degrades correctly.
      **`schema-keeper` ruled against putting `planner_run` in
      `findings.json`** and the reasoning is worth keeping: the order provably
      changes no other byte (the merge is a permutation, `checks_run` is
      sorted, findings and probes are sorted, `MAX_STEPS` cannot bind on six
      checks), so the block would carry the file's only order-dependent bytes
      -- costing `README.md`'s byte-identical claim, a `SCHEMA_VERSION` bump
      that makes every artifact on disk unreadable to `report.py` and `vex.py`,
      and a fabricated record in `run_baseline.py`, which has no planner.
      Inside `coverage` it is disqualifying: `artifacts/sarif.py` copies
      `coverage` **wholesale** into `findings.sarif.json`.
      **Shipped.** `build_findings` calls `order_checks` at the edge and
      passes the returned order to `workflow.audit`; it now returns
      `(findings_document, planner_document)` and `main.py` writes
      `planner.json` as an eleventh artifact.
      **The measurement that matters, and it is uncomfortable**: the model's
      ordering has **no observable effect on any artifact** unless the step cap
      binds. `checks_run` is sorted, findings and probes are sorted, every
      eligible check runs regardless -- so `MAX_STEPS` (20) against six graph
      checks means the order changes nothing a reader can see. `test-writer`
      found this by mutation: passing `planned` instead of `order` was caught by
      **exactly one test**, and only because that test sets `MAX_STEPS = 1`.
      The planner is real, recorded and monotone; it is not yet consequential.
      Deciding whether that is acceptable, or whether the planner should choose
      *what to probe* rather than only the order, is the open question for 7.4.
      The honest cost, recorded not discovered: **nothing reads `planner.json`,
      so the planner's decision never reaches a score**
- [x] **7.3 -- prompt-template semantic probe, shipped opt-in.**
      `src/checks/semantic_probe.py`, `CHECK_NAME = "semantic_probe"`,
      `OWASP_ID = "LLM01"`, title "Prompt template interpolates a value into
      instruction text without delimiters" -- a description, not a verdict, the
      same correction the LLM02 title took. Pure: no `model_client` import, the call is injected as
      `model_ask_fn` and made at the edge in `build_findings`; `main.py`'s
      `probe_inputs` is the one place an audit hands `model_client.ask` to a
      check.
      **`detection` is `probe`, not a new `semantic_probe` value.** A novel
      value would need `SCHEMA_VERSION` 6 -> 7, which makes every artifact on
      disk unreadable to `report.py` and `vex.py` -- and worse, it would walk
      past two guards that branch on `== PROBE` literally
      (`findings_document._check_probe_citations` and `report._probe_lines`),
      so a finding could cite no evidence at all and still serialise and
      render. Using `PROBE` *forces* the model's rationale to be published as
      probe evidence, which is what makes the verdict weighable.
      **Off by default** (`--semantic-probe`), so `findings.json` stays
      byte-identical for every run that does not ask for it; when it is asked
      for, `model_run.status` says `used` and names the model and decode
      settings rather than claiming `disabled` beside model-authored findings.
      **Measured against the real model**, `qwen2.5-coder:7b-instruct`
      (digest `dae161e27b0e...`), on `damn-vulnerable-llm-agent`: one
      prompt-template surface, one confirmed probe, and the finding lands on
      `main.py:21` -- `VULN1-01`'s anchor, one of the two misses previously
      attributed to a check that ran and stayed silent.
      **This is not a recall claim and must not be quoted as one.** The grading
      keys went with the corpus on 2026-09-04, so nothing re-scores; and the
      verdict is model-dependent, so another Ollama build may not reproduce it.
      That is why `model_run` records the digest and why the flag is opt-in.
      **Seven defects were found across two review rounds, and every one was a
      false claim in an artifact rather than a crash.** Worth keeping in full:
      `_probe_run` keyed on "did a probe exist", and a `NOT_RUN` probe is still
      a probe -- so a run whose every model call was refused wrote
      `status: "used"` and named the model. It now asks whether a call was
      *answered*: `disabled` / `unavailable` / `used`, matching what
      `outputs.build_remediation` and `checks/planner.py` already do.
      `read_verdict` matched `VULNERABLE` as a **substring**, so "NOT
      VULNERABLE" produced a finding -- then, over-corrected to a first-word
      test, it missed a fenced reply and "The template is VULNERABLE", which is
      how `qwen2.5-coder` actually answers. It now strips fences, looks for the
      token anywhere in the verdict line, and checks for a negation in front of
      it. It also returns **`None`** for a reply carrying neither word: an
      empty or unparseable answer was being recorded as "the model read the
      template as structurally safe".
      `template_text` collected string constants only, so it **deleted every
      f-string variable and joined the halves with a newline** -- the tool
      removed the value and inserted a delimiter, then asked the model whether
      a value sat there without one. Systematically biased toward SAFE. It now
      rebuilds the expression, keeping interpolation points as `{name}`; and a
      rendering that is only placeholders (`from_template(TEMPLATE)`) answers
      "" rather than earning a verdict about text nobody saw.
      `_probe_run` collapsed a **fourth** state: a run whose every template was
      unreadable placed no call yet recorded `unavailable`.
      `checks_run` named the check on a run where every call was refused, which
      `docs/SCHEMAS.md` defines as "looked and found nothing".
      And `main.probe_inputs` called `model_client.model_digest()` unguarded,
      so `--semantic-probe` with the server down **wrote no artifacts at all**
      and every degradation path was unreachable through the CLI.
- [ ] **7.3 (superseded, kept for the trail) -- prompt-template structure probe**, own artifact, own report
      section, own schema; after 7.0-7.2. Named
      `prompt_template_lacks_delimiters`, **not** an injection test: a model's
      opinion about a payload is a fact about `qwen2.5-coder:7b-instruct`, which
      is the third of the three reasons this work was parked and the one that
      still stands. Rule 18 -- its judging rules go in their own module; do not
      add to `taint.py` (214 lines) or `findings_document.py` (211), both
      already over the cap

**Segregate, do not qualify.** `findings_document.strip_model_authored` removes
two *fields* and cannot strip a *record*, so a model-authored finding would pass
through it silently. Probe results therefore get their own artifact, precedent
`remediation.json` and `coverage.advisory_unreached_components`. The honest
cost, stated rather than discovered: **segregated, the probe reaches no OWASP
score**, so this phase does not improve the published 2-of-6.

**The byte-identity claim is structural, not tested.** `README.md:44` and `:512`
say `findings.json` is byte-identical whether the model ran or not; that holds
only because `run_checks.py:73` hardcodes `model_run(MODEL_DISABLED)`, and
`test_determinism.py` compares two model-off runs. Nothing compares model-on to
model-off. Task 7.2's test for it is the falsifier the suite has never had.

- [ ] `evaluation.json`'s `model_disabled` qualification is misnamed, found by
      `schema-keeper` on the way past. `src/evaluation/scorer.py:86` appends it
      whenever `model_run.status != MODEL_USED`, so it fires on `unavailable`
      too -- collapsing "we turned the model off" and "we could not reach it"
      into one word, which are different claims about a run. Renaming it is not
      local: `QUALIFICATIONS` is pinned as an exact tuple by
      `tests/evaluation/test_scorer_qualifications.py:41` and published in
      `docs/SCHEMAS.md` and `docs/PHASE_4_PLAN.md`, and a vocabulary change
      bumps `evaluation.json`'s own schema version
- [ ] `workflow.act` dispatching `undeclared_dependency` with a null
      `mapping_document` dies as `AttributeError: 'NoneType' object has no
      attribute 'get'` inside `supply_chain.py:43`, not as a clear error
      (rule 8). Unreachable through `run_checks`, which plans that check only
      when a mapping exists -- so it is a latent trap for the next caller, not
      a live bug. Found by `test-writer` while testing 7.0
- [ ] Transcribe the proposal's two relevant sentences into
      `docs/PHASE_7_PLAN.md`. **The proposal is not in `docs/`** -- nothing
      tracked lets an examiner check what was promised, so the claim this phase
      answers is currently unfalsifiable

- [ ] The two languages file `ToolNode` under different tables, so one construct
      extracts as two different kinds: Python has it in `TOOL_CLASSES` ->
      `TOOL_CALL`, `detector_names_js.py` has it in `AGENT_FACTORIES` ->
      `AGENT_DEF`, with a comment arguing that counting it as a tool
      double-counts the tools it wires up. A grading key joining on
      `llm_surface`, and any check filtering on kind, get different answers for
      the same code depending on the language. `TavilySearch` is likewise
      Python-only. Pinned by a test rather than left silent; decide which table
      is right and make both languages agree
- [x] `init_chat_model` in `MODEL_CLASSES` also makes `artifacts/aibom.py` emit
      it as a `MODEL` component named `init_chat_model` with
      `model_source: "unstated"`. Covered by two tests in
      `tests/artifacts/test_aibom.py` that build their own one-file loader app.
      **The pinned five-component list was deliberately left alone** -- it
      describes a different app, and editing a fixture to admit a new case is
      how a pinned list stops pinning anything
- [ ] `artifacts/vex.py` subscripts `finding["purl"]` unguarded and then sorts
      the grouped items. `Finding` does not require `purl` alongside
      `advisory_id` -- only `known_advisory` supplies it, via `_reached()`
      filtering on a truthy purl -- so a future advisory producer omitting it
      would sort `str` against `None` and raise `TypeError`. Latent, not live

- [ ] **Duplicate passage citations crash the advice writer.** Found by
      `test-writer` on 2026-09-05: `retrieval/passages.as_source` returns
      `{source, path, heading, url}` and **drops `hit.id`**, so two chunks of
      one long section collapse to the same attribution triple and
      `artifacts/remediation._check_sources` raises "the same passage is cited
      twice". Nothing between `store.query` and `advice_entry` dedupes. Fix in
      the producer -- dedupe, or let `as_source` distinguish chunks -- not in
      the guard, which is doing its job.
      Exposed rather than caused by the AUDITABILITY check: that fixture app
      produced 0 findings before and 1 now, so `advise_all` had something to
      advise for the first time.
- [ ] `tests/cli/test_main_dependencies.py::test_run_returns_zero_when_called_directly`
      calls `run(args)` directly instead of `run_cli`, so unlike every other CLI
      test it never calls `stub_knowledge` and hits the **real ChromaDB index**
      on the developer's machine. It passes on a clean checkout only because
      there is no index to hit -- luck, not hermeticity, and against rule 13.
      Stub knowledge there like its neighbours

- [x] **Evidence-link coverage (proposal: "percentage of findings containing
      valid code, SBOM/AIBOM and CSAF/VEX evidence links").**
      `src/evaluation/evidence.py`, wired through `scorer.score_app` and
      `document._totals`; `evaluation.json` **schema 2 -> 3**, documented in
      `docs/SCHEMAS.md`. `report.py` gained a `- **VEX Status**:` line on
      advisory findings. Counts plus `findings_considered` plus
      `apps_included` -- never a rate, see the blocker below

- [x] `tests/test_vex_unread.py`'s allow-list gate stays **case-sensitive**,
      decided 2026-09-05. Its thesis is "who could open the folder or run the
      program", and a lower-case `vex` is how a module spells a path (`vex/`),
      a filename (`emit_vex.py`) or a program (`vexctl`). The bare acronym in
      rendered prose -- `"## VEX (exploitability statements)"`, `"no VEX: this
      audit read no advisory data"` -- can open nothing. Folding case widened
      it to "who says the word VEX", which would have pulled `artifacts/vex.py`,
      `pipeline.py` and `report_gaps.py` into the list and diluted it until
      nobody read it -- and made `artifacts/vex.py`'s "deliberately absent, it
      needs no exemption at all" comment false.
      **Accepted residual risk, recorded not hidden**: a module writing only
      the acronym escapes this gate. It still cannot name a path, and
      `test_no_source_module_names_a_path_into_the_committed_folder` -- the
      invariant the file's own docstring calls the real one -- is unaffected.
      `report.py` is allow-listed, which was required regardless of case: its
      status line names `emit_vex.py`

- [ ] Five tests import a private helper where a public path exists, against
      the convention `tests/test_sbom_duplicates.py` writes down ("a test
      reaching past it would keep passing after the builder stopped calling the
      helper at all"): `evaluation.harness._check_key` in `test_key_check.py`
      and `test_key_entry_check.py`, `artifacts.advice_rules._joined`, and
      `checks.output_handling._method_of`. `emit_vex._environment` conforms --
      its public path would launch vexctl, which the test must not do. Found
      while settling the convention for `test_report_advisory.py`
- [ ] Three test files sit just over rule 18's ~200 after the splits:
      `test_evidence.py` 224, `test_vocabulary.py` 230, `test_check_scope.py`
      206. The seams taken were the right ones; each needs a second cut, and
      none is urgent

- [x] `src/main.py` grew to **246 lines**, well over rule 18's ~200, as the
      audit gained a planner, a probe and a timer. Split 2026-09-05: the
      dependency half -- `MIXED_MANIFEST_REASON`, `declared_ecosystems`,
      `dependencies_readable`, `_declarations`, `dependency_artifacts` -- moved
      to `src/dependency_inputs.py` (80 lines), leaving `main.py` at 180 as the
      command: parse, run, write, report. `probe_inputs` stayed: it is the edge
      where a model enters an audit and belongs beside the flag that asks for it

- [x] **7.4 -- the planner chooses surfaces, not just order.** Requested by the
      project owner with the consequence stated, on the proposal's authority:
      "`auditor_planner`: uses a local LLM and deterministic risk heuristics to
      **choose the next surface and probe**". This **overturns** the phase's
      "ADD and ORDER, never SUBTRACT" rule for 7.4 only;
      `docs/PHASE_7_PLAN.md`'s rejection paragraph is annotated in place rather
      than deleted, because it is the reasoning behind `merge_monotonically`,
      which still ships.
      **The harm, and the five rules that contain it.** A surface the model
      skips yields no finding, and a check named in `coverage.checks_run` would
      otherwise claim it "looked and found nothing". So: a check the model does
      not name examines everything; an empty selection is refused, not
      honoured; surfaces the prompt never described always run (`describe_surfaces`
      caps at 40, and under selection semantics that cap would silently exclude
      everything past it); a check this app does not plan cannot be narrowed;
      and `supply_chain`/`known_advisory` are never narrowable, because they
      read the mapping document and filtering their surfaces makes a component
      vanish from **both** sides of the ledger -- no finding, and not counted as
      unreached either, which would silently break the README's
      "79 advisory-carrying components reached by no LLM surface".
      **New**: `src/checks/plan_selection.py` (pure), top-level
      `findings.json.checks_narrowed` (**schema 7**), `planner.json` schema 2
      with `surface_selection` and `refused_narrowing`,
      `src/artifacts/coverage.py` split out of `findings_document.py`.
      `checks_narrowed` is **top level, not in `coverage`**: `sarif.py` copies
      `coverage` wholesale into an artifact published as byte-identical, and
      this is the one field a model can move.
      **The stated limit**: `src/evaluation/scorer.py` does not read
      `checks_narrowed`, so `evaluation.json` scores a narrowed run exactly as
      it scores a full one. The field makes narrowing visible to a reader; it
      does not make the score account for it
- [ ] Teach `src/evaluation/scorer.py` about `checks_narrowed`, so a key entry
      at a surface the planner skipped is not scored as an ordinary miss.
      Deferred deliberately: it is a Phase 4 change and needs a re-measure.
      **Do not attempt it with per-surface probes** -- `scorer.py:132` keys its
      probe map on `(file, line)` and discards `probe_name`, so one skip probe
      would set the miss reason for every key entry at that line, of every risk
      class, turning an honest silence into an excuse
- [ ] Nothing version-gates `findings.json` at score time.
      `evaluation/harness.py` gates the grading key at `KEY_SCHEMA_VERSION` and
      nothing gates the findings document, so a stale artifact scores silently
      against fresh code. Pre-existing; the 6 -> 7 bump is the moment it can bite

- [ ] **`coverage.checks_run` means two different things, and 7.4 let a model
      move a check between them.** `workflow.act` appends a graph check the
      moment it is dispatched, so for a graph check the name means "was
      dispatched"; the edge check is named only when it found a subject and got
      an answer. Measured, same shape, two artifacts: `high_privilege_tool`
      narrowed to one data source stays in `checks_run` and publishes
      `examined 1 of 3`; `semantic_probe` narrowed to two non-templates leaves
      `checks_run` and publishes `[]` -- byte-identical coverage to an app with
      no prompt template at all. That is a rule-1 violation: the app still has
      its template and only the model's request changed.
      **Not fixed here on purpose.** Making the probe unconditionally present
      undoes a 7.3 fix (`_probe_run` keying on "did a probe exist" wrote
      `status: "used"` on a run whose every call was refused), and would name
      the probe on an app with no template, which is the correct absence every
      other check follows. The real fix is telling the two absences apart, which
      needs the unnarrowed template count at the edge. Held by a strict xfail in
      `tests/checks/test_narrowing_defect.py` so it cannot be forgotten.
      **The cost today is bounded**: `semantic_probe.OWASP_ID` is LLM01 and so
      is taint's, and both walk `python_files`, so LLM01 is in
      `risk_classes_checked` regardless. An honesty defect in `findings.json`,
      not a measured recall loss

- [x] **The sandbox is out of scope, by decision, 2026-09-05.** The proposal's
      `probe_injection` specified "in a sandboxed environment"; the shipped
      check is static. Recorded in `docs/REPORT.md`'s Addendum with three
      reasons, two of which are about coherence rather than cost: a dynamic run
      of `damn-vulnerable-llm-agent` reaches `gpt-4-1106-preview` through
      LiteLLM, so it either transmits the audited app's prompts to an external
      provider -- the exposure this project argues against -- or, pointed at
      Ollama, measures `qwen2.5-coder` rather than the app; and it would trade
      away the never-executes guarantee that `test_no_mutation.py` and
      `test_no_write_commands.py` enforce, which is what makes auditing an
      unknown URL safe. The engineering cost is the third reason, not the first.
      **Do not reopen without answering the first two.** The coverage row stays
      Partial: the proposal did specify a sandbox, and a stated shortfall is
      still a shortfall

- [x] **A grading key ships, and the new checks are measured for the first time.**
      `grading_keys/damn-vulnerable-llm-agent.{ground_truth,manifest}.json`,
      pinned to upstream `c0cf9a14`. **AI-drafted and `verified: false`**, so
      every score carries `key_ai_drafted` and `key_unverified`; a human reading
      the six entries against that commit is what removes them.
      **Result, re-measured 2026-09-05 on the six-entry key: 4 of 6 static, 5 of
      6 with `--semantic-probe`, against 5 of 6 for `baseline_static_rules` and
      0 of 6 for `baseline_sbom_only`.** The auditor reaches DVLA-07 alone and
      the grep baseline DVLA-02 alone, so the union is all six. The earlier
      3-of-5 and 4-of-5 were read off a five-entry draft that dropped
      `main.py:60` and `utils.py:75` -- precisely the two the auditor reaches --
      and the entry that graded `transaction_db.py:76`, whose one caller passes
      the literal `1`, was dropped with it. DVLA-01 is the
      entry taint runs at and stays silent on -- `argument_names` collects
      `ast.Name` only, so an f-string system prompt yields nothing to follow --
      and the probe reads the template and reports it. The remaining miss,
      DVLA-02, is `checked_and_silent`: `GetUserTransactions` grants no shell,
      interpreter or network reach, so `permissions.py` is silent; what makes it
      a finding is a *missing authorisation check*, an absent comparison rather
      than a present capability. A known gap, now measured.
      **Three defects `test-writer` found in my first draft of the key**, all
      fixed: every entry omitted `llm_surface`, which `grading.matches_key`
      reads with `.get()` -- so the join silently dropped its surface-kind
      clause and every entry matched any kind at its file and line; the manifest
      said `role: "graded"`, outside the documented vocabulary and enforced by
      nothing in `src/`; and it omitted `framework` and `language`, required for
      a graded app. **Both figures were re-measured on the tightened join and
      are unchanged.**
      The pin was nearly wrong too: `git -C fetched/... rev-parse HEAD` returns
      **this project's** HEAD, because `fetched/` is not a clone. The real pin
      is in the manifest `fetch_repo.py` writes.
      **A second field silently weakened the join before it was caught**:
      `component: "pyyaml"` on DVLA-07, which `grading.matches_key` compares
      against the finding's *purl* -- an undeclared package has none, so the
      true match was suppressed until it was set to `null`. Both that trap and
      the published six entries are now held by tests:
      `tests/test_shipped_key_join.py` and `tests/test_shipped_key_entries.py`
- [x] **`ComponentRef` exists** (`src/artifacts/component_ref.py`), the
      data-model name from the proposal that had never been written down.
      `ComponentRef.as_entry()` produces the dict `mapping.json` already
      held, so the artifact and its schema are untouched. **`Component` was
      written and then deleted**: nothing under `src/` constructed one, so its
      only callers were its own tests -- dead code by rule 14, and
      `docs/PROPOSAL_COVERAGE.md` records that half as not delivered rather
      than counting it. A first draft asserted
      "a purl names exactly one component" and was refuted by the
      ambiguous-purl tests -- `_join_purl` deliberately drops the version when a
      surface cannot say which installed copy it loads
- [x] **AIBOM records `DATASET` and `MCP_SERVER`**, the two AI component kinds
      the proposal names that were absent. Two import-time guards, because the
      first draft named methods no detector emitted -- a kind with no path to
      it, the same trap `executescript` was.
      **The guard was not enough, and `test-writer` found why**: it checks name
      *membership* while the detector matches call *shape*, and the two tables
      have opposite shapes -- `DATA_SOURCE_CALLS` matches a full dotted name,
      `DATA_SOURCE_METHODS` a leaf with a receiver. So `load_dataset("x")` was
      seen and `datasets.load_dataset("x")` was not.
      **My first fix was wrong and was caught by measurement.** I spelled
      `datasets.load_dataset` into the full-name table, which covers exactly one
      module spelling -- `import datasets as ds` defeats it -- and counts one
      published API name twice in the registered-name total, an import-style
      detail inflating a write-up denominator, which is the very thing the
      dedupe rule exists to prevent. The right fix is to treat both loaders
      alike: the bare call in `DATA_SOURCE_CALLS`, the receiver form in
      `DATA_SOURCE_METHODS`, whose leaf match survives **any** receiver.
      All six spellings now extract and yield a `DATASET`, and the count
      returned to 86 -- proof the extra entry had added no detection
- [ ] **An MCP client under two of its three spellings is filed as a `TOOL`.**
      Found by `test-writer` on 2026-09-05: `aibom._kind_of` tests
      `surface.name.split(".")[0]` against `MCP_CLASSES`, but the tool detectors
      replace that name -- `_tool_from_call` prefers a `name=` keyword and
      `_tool_from_class` uses the subclass's name -- so `MCPToolkit(name="orders")`
      and a class subclassing `ClientSession` both come out `TOOL`. The same
      shape-versus-membership gap the `DATASET` fix closed, and the import guard
      structurally cannot see it. Cost is confined to `aibom.json`: no check
      reads an AIBOM kind. The fix is for a surface to carry the class it
      matched, which changes the extractor's contract, so it is its own task.
      Held open by the strict xfails in
      `tests/artifacts/test_aibom_mcp_defect.py`
- [ ] `artifacts/aibom.py`'s `_kind_of` is inconsistent about language:
      `_is_model_client` picks the per-language `MODEL_CLASSES`, while the
      `DATASET` and `MCP_SERVER` branches read Python's tables whatever the
      language. Harmless today -- the JS tables register none of those names --
      but it means the import guards cover the Python backend only

## Proposal coverage — measured 2026-09-05

`docs/PROPOSAL_COVERAGE.md` answers every commitment in the submitted proposal
with a file path or an admission, and transcribes the proposal's own sentences
so the claim is falsifiable. **~74% of 33 concrete commitments** (24.5/33, partials at
half): nearer 80% over the engineering, nearer 50% over the research design.
The proposal itself is still not tracked in this repository -- only its quoted
commitments are.

- [x] **Objective 5 is at 0%, and now says so in the report.** "To determine if Open weights models can compete
      with frontier AI offerings as an alternative", and the corpus was to
      "compare local open-weight and cloud-hosted frontier LLM configurations".
      Nothing in `src/` touches it -- no cloud path, no comparison harness, no
      data-exposure measurement. The tool being offline is the study's
      *premise*, not its *finding*. Either run some form of it or state in the
      report that it was dropped, and why
- [x] **A risk class was substituted, and the report now states it.** The proposal names "RAG/data-layer
      retrieval risks" as the fourth risk; the repo ships AUDITABILITY, this
      project's own invention, in its place. Retrieval points *are* extracted as
      `DATA_SOURCE` surfaces and taint treats them as untrusted, so indirect
      injection is partly reachable via LLM01 -- but no check reports a
      retrieval-layer risk as its own class, and retrieval poisoning has no
      detector. Decide: build it, or state the substitution
- [x] **"audit execution time" -- instrumented 2026-09-05.** `src/main.py`
      times each run with `time.monotonic()` and prints
      `audit completed in N.NN seconds`. **Printed, never written into an
      artifact**: a duration changes on every run and would break the
      byte-identical guarantee for a fact about the machine rather than about
      the audited app. No figure is published in `docs/REPORT.md` yet
- [ ] **"precision and recall of LLM surface extraction" is not scored.**
      `expected_surfaces` explains why a finding was missed; extraction itself
      has no precision/recall figure
- [ ] **`ComponentRef` does not exist**, though the data model and the Month 1
      schedule both name it
- [ ] **AIBOM records models, tools and agents only.** The proposal also names
      **datasets and MCP servers**; `AIBOM_KINDS` has no entry for either
- [ ] **CSAF/VEX ingestion is promised as an input and exists only as an
      output.** Objective 3 lists "exploitability information" among what
      findings link to; `src/emit_vex.py` writes a document and nothing reads
      one. Task 5.3 declared the filter out of scope because no upstream
      document exists -- correct, and it leaves the objective partly unmet

## Blocked / needs a decision

- **The three `pct_*` fields were requested and I refused them. That was the
  requester's call, not mine, and this row exists so it can be over-ruled.**
  Asked for: `pct_findings_with_code_evidence`, `pct_findings_with_sbom_evidence`,
  `pct_findings_with_vex_evidence` as fields in `evaluation.json`, with the
  percentages printed by `src/evaluate.py`. Refused because `docs/SCHEMAS.md`
  says "**No field in this file is a float**" and
  `test_no_value_anywhere_in_the_document_is_a_float` enforces it, and because
  `tests/cli/test_evaluate_output.py` pins "no `%` in stdout" and "no float
  token in stdout" -- my first attempt broke both and I papered over it by
  rewriting a docstring, which is the wrong way to change an invariant.
  Shipped instead: numerator, denominator and `apps_included`, from which the
  percentage is one division. **To over-rule**: amending the rule means editing
  `docs/SCHEMAS.md`, `docs/PHASE_4_PLAN.md`, `docs/REPORT.md`, `docs/FLOW.md`
  and `README.md` (twice), narrowing the two printed guards to exempt exactly
  the evidence lines, and accepting that the guard is weaker permanently.
  Say the word and it is a contained change.

Anything that stops work or needs a human call. Clear these as they are
resolved; do not tick the task above until its blocker is gone.

| # | Blocker | Who / what unblocks it |
|---|---|---|
| ~~B8~~ | ~~`oss-app-react-agent`'s grading key is unverified.~~ **Cleared.** It now carries `verified: true` with `verified_by: "Hein Thet Naung"` and `verified_date: "2026-08-28"`, so `key_unverified` no longer fires on it and its false-positive count has a human behind it. It stays `source: ai_drafted`, like the other two: who drafted a key and who checked it are different facts. | Cleared. |
| ~~B3~~ | ~~The two grading keys of the time were AI-drafted and unverified.~~ **Cleared**, and B8 later cleared the third. All three now carry `verified: true` with `verified_by: "Hein Thet Naung"` and `verified_date: "2026-08-28"`, so a Phase 4 number has a human behind it. The keys stay `source: ai_drafted` -- that records who wrote them, which is a different fact from who checked them. | Cleared. |
| ~~B6~~ | ~~The corpus exercised no LLM03 finding.~~ **Cleared with B3.** `VULN1-06` records PyYAML used but never declared, with `SURF-06` as its expected surface, and the human read it covers. | Cleared. |
| B7 | **Phase owners are unassigned** across Hein / Bing Hong / JW. | Agree the split. |
| B10 | **`docs/CODING_RULES.md` rule 13 was amended without the user's sign-off** (2026-09-04). It named `corpus/`, which the corpus removal deleted, so it could not stand as written -- but it is the *graded standard*, and rewriting it is a human's call, not the tooling's. Two things now depend on the new wording: `.claude/agents/project-guard.md` cites "rule 13, amended 2026-09-04" as binding, and `.claude/agents/test-writer.md` instructs building a tree in the test rather than validating against fixtures. **Reject the amendment and both gate definitions become incoherent**, so this is one decision, not three. | The user signs off on the new rule 13 text, or replaces it. |
| ~~B9~~ | ~~`oss-app-langgraphjs-starter`'s key was edited and its `verified` flag reset, so `key_unverified` fired on every score it touched.~~ **Closed 2026-09-04 with the corpus removal**: the key it blocked no longer exists. The human check it was waiting for is therefore never owed, and no score can be qualified by it. The entry itself is not lost -- `STARTER-01` is transcribed field by field into `docs/REPORT.md` Appendix A, including the reset `verified` flag, so a reader of Phase 4's numbers can still see what was unverified when they were taken. | Closed. |

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
- [x] ~~**`docs/report.docx` is stale and it is the tracked one.**~~ **Task 4.9
      decided and done**: `docs/REPORT.md` is tracked (rewritten to current,
      every number carrying its run label and key state), `report.docx` and
      `build_report.py` are deleted, and `.gitignore`'s comment now records the
      decision instead of contradicting it. The original entry is kept below as
      the record of the problem. *(Phase 5
      considered and deliberately did not resolve this: Task 5.2 was written so
      it does not depend on the answer -- every document it generates is
      gitignored, so no new binary and no new gitignored-source pair was
      created either way. The decision below is still owed, and is now the only
      place the problem lives.)* Built
      2026-08-23, it still says Phases 2 to 4 are unimplemented, the grading
      key is unverified, and the suite is 236 tests -- none of which is true
      at this commit. Its source, `docs/REPORT.md`, is **gitignored**, so an
      examiner reads only the binary and no correction to the Markdown reaches
      the repository. Two things to decide: rebuild the docx from a corrected
      `REPORT.md` (needs `python-docx` in a throwaway env, see
      `docs/build_report.py`), and settle whether the Markdown should be
      tracked and the binary dropped -- a diffable source is worth more to a
      reviewer than a Word file, which is the reason `build_report.py` gives
      for the split in the first place

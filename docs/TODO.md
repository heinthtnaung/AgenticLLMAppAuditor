# Open work

Ticked history is in git before commit `a78482c`; what shipped is in
`docs/HISTORY.md`. This file is only what is *not* done.

## Known defects

| Where | What |
|---|---|
| `checks/known_advisory.py` | A component whose version the SBOM cannot establish gets a versionless purl, but Trivy indexes advisories by versioned purl. They never join, so the component is published as **unreached** — a positive claim of safety from a version gap. |
| `checks/taint.py` | Multi-hop propagation has no notion of a sanitiser: `safe = sanitise(q)` taints `safe` exactly as `copy = q` does, so a finding titled "reaches the model without validation" can name a value a validator was called on. Over-approximating is the right direction for a tool that reports rather than patches, but the title is a positive claim. |
| `checks/output_handling.py` | Judges only the argument expression. `q = f"SELECT {x}"` then `execute(q)` is silent, and so is `.format_map`. Pinned by tests. |
| `checks/output_handling.py` | `%` is judged by shape: `execute("SELECT %s" % ("lit",))` is reported, `% "lit"` is not. Arbitrary. |
| `artifacts/aibom.py` | `_kind_of` reads Python's name tables whatever the language, so the import guards cover the Python backend only. |
| `artifacts/aibom.py` | An MCP client given `name=` files as `TOOL`, not `MCP_SERVER`. Shape-versus-membership, same family as the dataset gap. Strict xfail. |
| `artifacts/vex.py` | A finding with a null `purl` groups under `""`, so its statement names no subcomponent and the `component_name` it carried is not used instead; two unversioned components under one advisory collapse into one statement. Schema-valid input today's check cannot produce. Pinned by tests. |
| `coverage.checks_run` | Means "was dispatched" for a graph check and "found a subject" for the edge check, so a model can move the probe between them. Strict xfail. |
| `evaluation.json` | `model_disabled` fires on `unavailable` too, collapsing "turned off" and "unreachable". |
| Scoring | Nothing version-gates `findings.json`, so a stale artifact scores silently against fresh code. |
| `web/run_jobs.py` | One audit at a time: a second request is refused with 409 rather than queued. Two concurrent runs would race between the "already fetched?" check and the clone, and two over one app would overwrite `artifacts/<app>/` mid-write. A queue is the real answer. |
| `web/downloads.py` | Artifacts are keyed on the app name, not on the run, so a second audit of one URL writes over the first one's files. A superseded run reports `artifacts_current: false` and its downloads are refused with 409 rather than serving the newer bytes under the older timestamp -- which is honest but total: those files are simply not recoverable. Keying artifacts on the run would fix it and would change `--artifacts-dir`'s meaning for the CLI too. |
| `web/run_jobs.py` | An audit cannot be stopped once it starts. The page shows progress and no cancel, because a cooperative cancel raising through `progress.stage` would be swallowed by five `except` clauses in `src/` (`export_reports.py`, `main.py`, `retrieval/retrieve.py`, `remediation_run.py`, `checks/planner.py`) and reported as a user-fixable refusal -- a cancel silently becoming a partial success. Doing it properly needs a `stop_requested` field beside `status` and an AST sweep over those clauses. |
| `POST /api/audit` | **No authentication**, and same-origin gives it none: it removes a browser's protection *of other sites*, not of this one. Loopback is the only thing between it and a clone-anything endpoint. |
| `frontend/` | Ticking **Compare models** sends the audited source to a third party. `main.py` puts that behind a flag on the grounds that a flag is something a reader sees in the command they typed; a checkbox is weaker, and the page states the cost rather than the design pretending otherwise. |
| `tests/test_web_framework_containment.py` | The sweep names `fastapi`, `starlette`, `uvicorn`, `http.server` and `socketserver`, but `ast_scan.imported_modules` records `from http import server` as plain `http`, so that one spelling evades it. Naming `http` would also forbid `http.client` — the outbound half, which is `test_offline_containment.py`'s subject, not this one. Closing it properly needs a second scanner. The file's docstring lists exactly which spellings it does and does not name. |
| `tests/web/test_import_path_bootstrap.py` | Counts two directories (`web/`, `src/`) in two import orders. A wrapper module that inserted some *third* directory would go unmeasured. The narrower half of this is closed: the probe now reads `web/*.py` off disk and asserts every module in the folder was loaded, so a module no import chain reaches is named rather than silently left out of the counts. |
| `tests/web/jsx_sweep.py` | Comments are stripped before the accessor sweep runs, so an accessor written inside one is ignored -- intended, since a comment naming `src/artifacts/finding.py` was reported as the field `finding.py` -- but so is the rest of any line where a bare `//` opens what is not a comment. String literals and a scheme's `://` are exempted, both because the page really writes them; `and//or` in prose would still hide the accessors after it. The per-record floors in `test_jsx_record_fields.py` and `test_jsx_coverage_fields.py` are what bound the loss. |
| The whole suite | **Nothing in it can see a rendered page.** Three defects shipped green and were caught only by a screenshot: a wave layer painted behind an ancestor's background (a descendant at a negative `z-index` does), tints twice as strong as intended, and a `1fr` grid track that overflowed the viewport. A `className`-to-bundle join cannot see any of them. Three of the mechanisms *are* guardable textually and should be, shrinking this row rather than leaving it as a blanket excuse: no `background` on the wave layer's ancestors with a non-negative `z-index` on it; the same custom properties in all three `tokens.css` blocks; `minmax(0, ...)` on every flexible track in the top bar. What genuinely needs an eye after that is tone, contrast and overflow. |
| `frontend/` | The page no longer says the endpoint is unauthenticated. The panel saying so was removed at the user's request; `README.md` and the `POST /api/audit` row above still record it, but for a security tool the operator is now told less by the thing they are looking at. |
| `frontend/src/useRun.js` | Two `setState` calls run synchronously inside an effect (the resets when a run id changes), which `oxlint` flags as cascading renders. They are correct -- clearing is what stops a previous run's data showing under a new one -- but the clean form derives the value instead of resetting it, and that is a hook refactor. `frontend/.oxlintrc.json` now ignores `dist/`, so these are the only warnings left and they are visible. |
| `frontend/dist/` | Build output is committed, so a source edit without `npm run build` in the same change serves a stale page. `tests/web/test_built_page_shipped.py` puts a floor under it -- every static `className` literal in the JSX must appear in the built bundle, and every asset `index.html` names must exist -- and `tests/web/test_jsx_advisory_vocabulary.py` covers the braced ones that sweep skips by design, by deriving the tone class stems from the source and requiring a rule for each. Still slipping through: a reworded string, a class name *removed* from the JSX, a changed handler, and a CSS-only edit that touches no class name -- the sweep runs source to bundle, so it cannot see what the source no longer says. An mtime check would be the real answer and cannot be used: `git clone` writes `dist/` before `src/`, so every source file comes out newer on a fresh checkout. |

| `frontend/` + `src/main.py` | A `--compare-models` run announces no stages: `main.run` threads `on_stage` into the ordinary audit but not into `compare_run.run`, so the progress panel stays empty and every stage shows as never reached. Threading it would announce `fetch`…`write` twice, once per arm, which breaks the page's assumption that announcements are a prefix of `STAGES` -- so the real fix is a per-arm shape, not another argument. |

## Open tasks

- **The web UI's remaining polish.** Built: downloads of every file a run wrote,
  the SQLite run history with its own page, live stage progress, timestamps,
  light/dark, and a risk-class filter over the findings. Not built, and each is
  a line rather than a plan:
  - **Stop a running audit**, and `DELETE /api/runs/{id}` to forget one. Both
    are in Known defects above with the reason the first is not trivial.
  - **A queue** instead of the 409, which is the honest answer to one-at-a-time.
  - **Search and sort the history.** It is capped at `HISTORY_LIST_LIMIT` newest
    first with no paging, so a long history is simply not reachable from the
    page.
  - **Render more than two artifacts.** The remediation advice and the SARIF and
    OpenVEX documents are downloadable but not shown; `report.md` is still the
    thing to read.

- **LLM01: what the taint trace still cannot follow.** The entry
  `tests/checks/test_taint_defect.py` cites, which did not exist until now.
  Two shapes are recorded there as strict xfails -- a deeper receiver chain
  (`agent.runnable.invoke(q)`) and a value through a nested call
  (`agent.invoke(build(q))`) -- and two more are open and unrecorded in code:
  - **Cross-function within a file.** `self._analyze(page_text)` hands the value
    to another method and the taint stops. This is what
    `indirect-prompt-injection-poc` needs and does not get; the LLM01 that run
    reports comes from the semantic probe reading one line, not from dataflow.
  - **Nothing distinguishes a sanitiser** -- now a row in Known defects, since
    multi-hop shipped and the cost is real rather than hypothetical.

- **Inline messages are matched on one key, `content`.** Every mainstream chat
  API spells it that way, but a provider that does not -- or a wrapper building
  `{"text": ...}` -- extracts nothing, and the artifacts cannot tell that from
  an app with no prompts. Same shape as the two blindspots that hid LLM01 on
  `indirect-prompt-injection-poc`: absence of a surface is indistinguishable
  from absence of a defect.

- Teach `evaluation/scorer.py` about `checks_narrowed`, so a key entry at a
  surface the planner skipped is not scored as an ordinary miss. Phase 4 change;
  needs a re-measure. **Not with per-surface probes** — `scorer.py` keys its
  probe map on `(file, line)` and would attribute one skip to every entry on
  that line.
- Report `executescript` beside `execute` and `executemany`. Needs a detector
  entry first; the import guard refuses a method no detector emits.
- Python lockfiles: `Pipfile.lock` is JSON and ships on the stdlib today;
  `poetry.lock` and `uv.lock` need `tomllib`, which is 3.11+ against a declared
  3.10 floor. **Decide the floor.**
- Grading-key entries for `known_advisory`, and the before/after re-measure that
  advisory ingestion was supposed to produce.
- Score surface extraction as its own precision/recall figure.
- MITRE ATLAS as a second knowledge source (Phase 6 task 6.5).
- Make the two languages agree about `ToolNode` — Python files it as a tool, JS
  as an agent, so one construct extracts as two kinds.
- `owasp_reference.REFERENCES["LLM02"]` describes model output reaching a sink,
  which `output_handling.py` explicitly disclaims. The finding title is honest
  and the advice prompt beside it is not.
- Tests import private helpers where a public path exists; the study's tests add
  `_arm`, `_note` and `_check_partition`, whose only public path opens sockets.
- Many files sit over the ~200-line rule -- **39 under `tests/` and 11 under
  `src/`**, plus `web/history_store.py` at exactly 201. The largest is
  `src/checks/semantic_probe.py` (317). The web layer's tests are most of the
  growth: 8 of the `tests/web/` files added with the background job, the history
  and the UI guards are over 200. Counted on 2026-09-09, and recounted in the same change
  that made the earlier figure wrong -- which is the whole argument for counting
  rather than quoting.

- **Objective 5 needs repeating, and one of its figures is withdrawn.**
  - The exposure byte count is gone from `docs/REPORT.md`: it counted the
    planner's prompt as a probe prompt, and "one request per prompt template"
    was never true (3 requests for 5 templates in the saved run). Re-measure it
    over an app that has prompt templates.
  - The agreement counts moved. `agreement.py` now excludes subjects no model
    was asked about, which turned the saved three-arm run from "agree on 5 of 5"
    into "agree 2, no model asked 3". Any figure quoted from the old shape is
    wrong.
  - It is still **one run per app**, and hosted models take no `seed` —
    `glm-5.2` gave different verdicts on the same template across runs.
  - `damn-vulnerable-llm-agent` can no longer serve as the comparison app: its
    one template interpolates nothing, so the probe refutes it statically and
    neither model is ever asked.

- **`--compare-models` narrowed the offline guarantee.** `src/` now holds two
  modules that can open a socket, not one. `cloud_client` is constructed only
  behind the flag and a test proves a default audit still attempts nothing but
  Ollama -- but the sentence a reader remembers is weaker than it was, and that
  was bought deliberately.
- **The `cloud_auditor` arm is not reproducible.** A hosted model takes no seed,
  so `artifacts/cloud_auditor/` breaks the byte-identical rule every other
  artifact keeps. Exempted in `docs/SCHEMAS.md` rather than fixed; it cannot be
  fixed from this side.
- **`--artifacts-dir` half-applies under `--compare-models`**: the local arm
  follows it, the cloud arm is always `artifacts/cloud_auditor/`.
- **One of four model-driven stages stays local under `--compare-models`**: the
  knowledge-base embeddings (`retrieval/retrieve.py`). Threading the ask through
  it would make the cloud arm whole.
- **A drafted key is bounded above by the extractor.** The model is shown the
  extracted surfaces and `draft` drops any entry naming a file, line or risk
  class it was not shown, so such a key can never falsify the extractor. The
  output does not record that ceiling.
- **Drafted keys live under `grading_keys/drafts/`, which is gitignored**, so a
  figure scored against one is unreproducible from a clean checkout until a
  human promotes it. Acceptable only because `tool_drafted` makes the number
  self-describing.
- **A tool-drafted key a human has checked cannot be represented.** Schema 3
  forbids `tool_drafted` with `verified: true`, so promotion cannot clear
  `key_unverified` without also changing `source` -- which clears
  `key_drafted_by_scored_system` too, and that one is meant to survive. The
  vocabulary needs a fourth state or the pairing needs relaxing.

## Blocked on a decision

- **The `pct_*` fields were requested and refused.** `evaluation.json` forbids
  float fields and two tests pin "no rate in stdout". Shipped instead: counts,
  denominators and `apps_included`. To overrule: six documents and two guards
  change, and the guard is weaker permanently.
- **Objective 5 was dropped, then reinstated 2026-09-05** when API access was
  supplied, and is now measured. The original refusal stands in
  `docs/REPORT.md` and is not deleted: what changed is access, not the
  reasoning.
- **The sandbox for `probe_injection` was refused.** Reasons in
  `docs/REPORT.md`; two are about coherence, not cost.
- **A drafted key fails at classification, not detection.** Measured twice: 3 of
  12 entries sit on lines the auditor found independently and describe them
  correctly, but every entry is labelled `LLM06`. `matches_key` joins on
  `owasp_id`, so a right location under a wrong class scores what a
  hallucination scores. Whether a better prompt -- one that explains what each
  class means rather than listing the ids -- closes that gap is the cheapest
  experiment left on this feature, and nobody has run it.
- **No grading key ships.** The one that did was removed on 2026-09-06;
  `git show f9bd9ff:grading_keys/damn-vulnerable-llm-agent.ground_truth.json`
  recovers it. Every figure in `docs/REPORT.md` was measured against it, so none
  of them is reproducible from a clean checkout, and `src/evaluate.py` refuses
  rather than scoring zero. Writing or restoring a key is what makes the
  measurement claim true again.
- **A key can no longer be held to the one rule that made it independent.**
  `grading_keys/README.md` records it: at least one entry should sit where no
  extracted surface does, or recall is measured over the tool's own inventory.
  The test that held it needed a real key as its subject and went with it.

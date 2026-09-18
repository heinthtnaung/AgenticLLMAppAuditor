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
| `web/run_jobs.py` | An audit cannot be stopped once it starts. The page shows progress and no cancel, because a cooperative cancel raising through `progress.stage` would be swallowed by five `except` clauses in `src/` (`export_reports.py`, `main.py`, `retrieval/retrieve.py`, `remediation_run.py`, `checks/planner.py`) and reported as a user-fixable refusal -- a cancel silently becoming a partial success. Doing it properly needs a `stop_requested` field beside `status` and an AST sweep over those clauses. **The cost of this rose on 2026-09-17:** the page now covers itself with a fixed overlay for the length of a run it cannot stop. The overlay refuses to close for that reason -- a dismiss would hide a run that carries on. **It offers no exit either, from 2026-09-18 at the user's request**, so the nav bar is covered for the length of a run nobody can stop: the page leaves the overlay only by navigating itself when the run finishes, or by dropping it when the run fails. That is the cost of this defect made visible, and it is the one line the user is owed about that trade. |
| `GET /api/model` | Hands an unauthenticated caller every model this machine has pulled and its digest. Loopback is the only thing between that and anyone who can reach the port -- the same mitigation as the row below, on a wider surface. |
| `runs/uploads/` | An unauthenticated endpoint writes attacker-chosen bytes to disk, bounded only by `MAX_UPLOAD_BYTES`, `MAX_UPLOAD_TOTAL_BYTES` and `MAX_UPLOADS_PER_RUN`. They change no finding and nothing under `src/` reads them, but the surface is a write primitive where there was none. **Sharper since 2026-09-17:** the panel that exercised it was removed at the user's request, so this is now a write primitive with no UI reaching it -- still tested by six files, still loopback and hand-started, and still there. Keeping the route for a future panel and dropping it are both coherent; forgetting it is not, which is why this sentence exists. **And since 2026-09-18 the bytes can outlive their record:** `DELETE /api/runs/{id}` forgets a failed run's row and leaves `runs/uploads/<run_id>/` on disk, unreachable afterwards because the upload route answers 404 without a record, and cleaned by nothing. `docs/SCHEMAS.md` says the record outlives the files; this is the one case where that reverses. |
| `POST /api/audit` | **No authentication**, and same-origin gives it none: it removes a browser's protection *of other sites*, not of this one. Loopback is the only thing between it and a clone-anything endpoint. |
| `frontend/` | Ticking **Compare models** sends the audited source to a third party. `main.py` puts that behind a flag on the grounds that a flag is something a reader sees in the command they typed; a checkbox is weaker, and the page states the cost rather than the design pretending otherwise. |
| `tests/test_web_framework_containment.py` | The sweep names `fastapi`, `starlette`, `uvicorn`, `http.server` and `socketserver`, but `ast_scan.imported_modules` records `from http import server` as plain `http`, so that one spelling evades it. Naming `http` would also forbid `http.client` — the outbound half, which is `test_offline_containment.py`'s subject, not this one. Closing it properly needs a second scanner. The file's docstring lists exactly which spellings it does and does not name. |
| `tests/web/test_import_path_bootstrap.py` | Counts two directories (`web/`, `src/`) in two import orders. A wrapper module that inserted some *third* directory would go unmeasured. The narrower half of this is closed: the probe now reads `web/*.py` off disk and asserts every module in the folder was loaded, so a module no import chain reaches is named rather than silently left out of the counts. |
| `tests/web/jsx_sweep.py` | Comments are stripped before the accessor sweep runs, so an accessor written inside one is ignored -- intended, since a comment naming `src/artifacts/finding.py` was reported as the field `finding.py` -- but so is the rest of any line where a bare `//` opens what is not a comment. String literals and a scheme's `://` are exempted, both because the page really writes them; `and//or` in prose would still hide the accessors after it. The per-record floors in `test_jsx_record_fields.py` and `test_jsx_coverage_fields.py` are what bound the loss. |
| The whole suite | **Nothing in it can see a rendered page.** Three defects shipped green and were caught only by a screenshot: a wave layer painted behind an ancestor's background (a descendant at a negative `z-index` does), tints twice as strong as intended, and a `1fr` grid track that overflowed the viewport. A `className`-to-bundle join cannot see any of them. Three of the mechanisms *are* guardable textually and should be, shrinking this row rather than leaving it as a blanket excuse: no `background` on the wave layer's ancestors with a non-negative `z-index` on it; the same custom properties in all three `tokens.css` blocks; `minmax(0, ...)` on every flexible track in the top bar. What genuinely needs an eye after that is tone, contrast and overflow. |
| `frontend/` | The page no longer says the endpoint is unauthenticated. The panel saying so was removed at the user's request; `README.md` and the `POST /api/audit` row above still record it, but for a security tool the operator is now told less by the thing they are looking at. |
| `frontend/src/useRun.js` | Two `setState` calls run synchronously inside an effect (the resets when a run id changes), which `oxlint` flags as cascading renders. They are correct -- clearing is what stops a previous run's data showing under a new one -- but the clean form derives the value instead of resetting it, and that is a hook refactor. `frontend/.oxlintrc.json` now ignores `dist/`, so these are the only warnings left and they are visible. |
| `frontend/dist/` | Build output is committed, so a source edit without `npm run build` in the same change serves a stale page. `tests/web/test_built_page_shipped.py` puts a floor under it -- every static `className` literal in the JSX must appear in the built bundle, and every asset `index.html` names must exist -- and `tests/web/test_jsx_advisory_vocabulary.py` covers the braced ones that sweep skips by design, by deriving the tone class stems from the source and requiring a rule for each. Still slipping through: a reworded string, a class name *removed* from the JSX, a changed handler, and a CSS-only edit that touches no class name -- the sweep runs source to bundle, so it cannot see what the source no longer says. **Narrowed on 2026-09-17 for two declarations specifically**: `min-width: 0` on `.overlay__card` and `overflow: auto` on `.viewer__text` are joined to the built bytes by value rather than by selector, because "source fixed, `dist/` stale, suite green, user still sees the bug" was a live failure mode for exactly the positioning fix that closed it. An mtime check would be the real answer and cannot be used: `git clone` writes `dist/` before `src/`, so every source file comes out newer on a fresh checkout. |
| `frontend/` + `src/main.py` | A `--compare-models` run announces no stages: `main.run` threads `on_stage` into the ordinary audit but not into `compare_run.run`, so the progress panel stays empty and every stage shows as never reached. Threading it would announce `fetch`…`write` twice, once per arm, which breaks the page's assumption that announcements are a prefix of `STAGES` -- so the real fix is a per-arm shape, not another argument. |

## Open tasks

### The 2026-09-18 history UI change has no tests yet

Four UI changes landed at the user's request with **pytest deliberately not
run**, so the guards below are known to disagree with the markup and the suite
is expected to fail until they are brought in line. Listed here rather than
discovered later, because a stale enumeration that nobody has re-measured is
worth less than none: it reads as a passing guard.

What changed: the local and cloud model names left the `Options` cell for two
columns of their own (`RunOptions.jsx` now exports `localModel`/`cloudModel`
and renders flags only, `N/A` when no second arm ran); the open group became
one panel with the header (`.group--open`, `.group__runs` in place of
`.table-scroll`, top padding the `<th>` row never carried); and the page gained
`Forget all N failed` plus a destructive `Clear all`, the latter on a new
`DELETE /api/runs` documented in `docs/SCHEMAS.md`.

| Guard | Why it now disagrees |
|---|---|
| `test_jsx_history_columns.py` | The `(th, td)` enumeration is eight pairs; the table has ten. This is the enumeration that was just closed, so it must be *extended*, not loosened. |
| `history_attribute_register.py` | `table-scroll` became `group__runs`, `.group`'s class is now conditional, two `run-options__model` spans and their `mono` children left `RunOptions.jsx`, and `ModelCell` adds new triples. The `BY_FILE` shares and the forty-four figure both move. |
| `test_jsx_run_options.py` | Pins the model spans that are no longer in that component. |
| `test_jsx_page_heads.py` | The heading and hint now sit inside `.history__head` beside the two controls. |
| `test_jsx_stored_option_fields.py`, `test_jsx_run_flags.py` | Read `RunOptions.jsx`, whose shape changed. |
| `test_jsx_history_refresh.py`, `test_jsx_forget_busy.py` | `HistoryPage.jsx` gained a `working` flag and a second delete path. |
| **Missing entirely** | Nothing covers `DELETE /api/runs`, `HistoryStore.clear`, `clearHistory()`, the two-step confirm, or `forgotten_count`. The store-level wipe wants the shape `test_history_store_delete.py` already uses. |

`HistoryStore.clear` deliberately has **no status guard**, matching `delete`:
the narrowing lives on the route so the rule stays in one place. A test should
hold that, or the next reader will add a guard in the wrong module.

**A second untested batch, same day: the arm toggle and the stage-mark fix.**

`--compare-models` announced no stages at all, because `main.run` called
`compare_run.run` without the listener and that function had no parameter to
take one. Every `progress.stage` in the compare path therefore got `None`, the
row stored `stages: []`, and `StageProgress` rendered all eight boundaries as
`unreached` -- work that had happened *twice*, shown struck through as work
that never started, on a run that finished. The listener now reaches the
**local arm only**: it appends, so threading it into both would send sixteen
announcements for eight stages and `index === announced.length` would walk off
the end on the ninth. Runs already stored keep their empty list; the fix is for
new runs. **A test wants the local-arm-only property specifically** -- the
naive fix is the one that breaks the overlay.

The report page now chooses which arm to read (`ArmToggle.jsx`), switching the
rail, findings, advisory components, surfaces and coverage together, because
the alternative was a rail saying ten beside a hosted arm's nine. `comparison`
already carries that arm's own `findings` and `surfaces`, so nothing is fetched.
Two honest edges, both worth a test:

- **Advice is not shown for the hosted arm at all.** `remediation.json` joins on
  `finding_id`, both arms audit the same tree, and a finding both found carries
  the same id -- so fetching the served document anyway would caption the
  hosted arm's finding with the *local* model's advice. `useAdvice(runId,
  served)` leaves it null and `FindingAdvice`'s `unservedIn` says where the real
  document is. The test that matters is the negative one: that selecting the
  hosted arm issues no request for `remediation.json`.
- **`ComparisonCard` lost its caveat** because the Download card now makes the
  same statement where a reader looks for those files. One statement, not two.

`FindingList.jsx` is **220 lines**, over the rule and further over than it was
at 208; `web/history_store.py` 236 and `web/run_record.py` 224 are the other
two. Three modules now disclosed rather than split, which is two more than the
rule intends.

**A third batch, and it closed three of this file's own Known-defect rows.**
Those rows have been deleted from the table above, because this file holds what
is *not* done; they are named here so the deletion is not silent.

- **Artifacts are keyed on the run now**, not on the app. `web/run_jobs.py`
  passed no `--artifacts-dir` at all, so every audit of one app wrote to
  `artifacts/agentic_auditor/<app>/` and the history's files column read
  "overwritten" for all but the newest row. It now passes
  `artifacts/runs/<run_id>/<system>/`, and `compare_run.cloud_artifacts_dir`
  derives the hosted arm from the local one instead of a module constant, so
  both arms are isolated. **Nothing in `src/` changed to achieve it** and the
  command line is byte-identical: the default local directory's parent is
  `artifacts`, so the hosted arm still resolves to `artifacts/cloud_auditor`.
  The old row claimed this "would change `--artifacts-dir`'s meaning for the
  CLI too", which was wrong -- the caller choosing a value is not a change of
  meaning.
- **The hosted arm's files are served**, by `?arm=cloud` on the three download
  routes, and its own `remediation.json` is what its findings are captioned
  with. `HistoryStore.overwritten_since` generalises `superseded` to a
  directory the record's own column does not name, via `json_extract` over the
  stored envelope, so the hosted arm is refused with 409 on the same terms as
  the local one rather than on none.
- **`DELETE /api/runs/{id}` is no longer failed-only**, and what changed was a
  filesystem fact rather than a mind: the refusal existed because a finished
  run's files had already been overwritten by the next audit of that app, so
  its envelope was the only copy. Per-run directories end that, so any run that
  is not *running* may be forgotten, and forgetting it removes the tree it
  wrote. A running one is still refused because its worker is writing there.
  `web/run_files.py` owns that rule, covers both arms, and returns None for a
  pre-change row whose files sit in a shared directory nothing may delete.

Still open, and sharper rather than softer now: **`runs/uploads/<run_id>/` is
the one thing a forgotten run leaves behind.** Every other file it wrote goes
with it, which makes the upload directory the exception rather than one case
among several.

- **`web/run_record.py` does two jobs, and the cut is a two-line move.** The
  record's shape on the wire is one; flattening it for the database is another,
  and that half is `ENVELOPE`, `as_json`, `to_columns` and `from_columns` --
  42 lines that belong in `web/run_columns.py`. The blast radius was traced
  rather than guessed: **one import statement in `web/history_store.py` and one
  in `tests/web/test_run_record_columns.py`**, nothing in `src/`, nothing in
  `frontend/`, no schema and no artifact. `DURABLE_FIELDS` stays where it is
  because both jobs need it, and `test_import_path_bootstrap.py` needs no edit
  because the new module is reached through the store. Written down with the
  seam rather than left as "224 lines, worth a reader's eye", which records a
  symptom nobody can act on -- the `src/fetch_repo.py` row above is the
  precedent for naming the cut instead.

- **The web UI's remaining polish.** Built: downloads of every file a run wrote,
  the SQLite run history with its own page, live stage progress, timestamps,
  light/dark, and a risk-class filter over the findings. Added since that line
  was written and not previously recorded here -- only their *defects* were, so
  a reader of this roadmap could not tell the page had them: a **drafted-key
  editor** with a verify route, **evidence uploads** attached to a run, an
  **Ollama status pill and model picker**, a **required auditor name**, a
  **source window** showing the lines a surface names, a **history grouped by
  repository** with each run's options and both model names and a per-group
  delete for failed runs (2026-09-18) -- which also *removed* the App column,
  since the group header now carries the repository and a failed run has no app
  to show -- and (2026-09-17) a
  **fixed overlay** carrying the stage list while an audit runs, which navigates
  to the run's own page the moment it finishes, plus a **file viewer** that
  opens any artifact from the download list. Removed the same day at the user's
  request: the rendered-report card, which framed two of the sixteen files the
  viewer now opens, and the **attached-evidence panel**. Not built, and each is a line rather than a
  plan:
  - **Stop a running audit.** In Known defects above with the reason it is not
    trivial, and the reason the overlay now covers the page with no way out.
  - ~~**`DELETE /api/runs/{id}` to forget one.**~~ Shipped 2026-09-18, narrowed
    to **failed** runs. Split from the line above rather than ticked with it:
    one half shipped and the other did not. What makes the narrowing safe is a
    constraint rather than a convention -- `(status = 'finished') = (envelope IS
    NOT NULL)` means a failed row's envelope is NULL, so forgetting one destroys
    no findings. A finished run's envelope is the only copy of its findings once
    `artifacts/` is cleaned, and a running one still has a worker writing to it;
    both are refused 409.
  - **A queue** instead of the 409, which is the honest answer to one-at-a-time.
  - **Search and sort the history.** It is capped at `HISTORY_LIST_LIMIT` newest
    first with no paging, so a long history is simply not reachable from the
    page.
  - ~~**Render more than two artifacts.**~~ Closed 2026-09-17: the file viewer
    opens every name `howToShow` accepts, which is fourteen of the sixteen --
    the SARIF and OpenVEX documents included, since both are `.json` whatever
    their middle word says. What is left is not a shortfall but a decision: the
    two PDFs are refused by suffix before a fetch, because the download route
    makes every reply an attachment and the viewer's only paths are a `<pre>`
    and a frame over a string.

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
- Many files sit over the ~200-line rule -- **69 under `tests/` and 15 under
  `src/`**, plus 2 under `web/` (`history_store.py` 220, `run_record.py` 224)
  and 3 under `frontend/src/` (`FindingList.jsx` 208, `results.css` 341,
  `controls.css` 235). `web/run_record.py` (224) and `history_store.py` (220)
  both grew again on 2026-09-18 for the delete and the served
  `canonical_repo_url`; `run_record.py` crossed on 2026-09-16 and has gone up
  by 68 lines since, which is worth a reader's eye before it grows further. The `tests/` growth is the overlay's and the file
  viewer's, all docstring-heavy rather than doing two jobs and in line with the
  siblings already in that folder; the two stylesheets grew for the viewer's
  rules and the hover and focus states, and `results.css` grew *despite* losing
  the dead `.report-frame` block.
  The largest is `src/fetch_repo.py` (329), which passed
  `src/checks/semantic_probe.py` (317) on 2026-09-16 when the pin read was
  guarded; the row above says where its seam is. Counted on 2026-09-09 and
  recounted on 2026-09-15 and four times on 2026-09-16, each time in the change
  that made the earlier figure wrong -- which is the whole argument for counting
  rather than quoting. What this change grew, recorded rather than left to be
  noticed:
  - **Seven files crossed**, the last being `tests/web/test_jsx_forget_report.py`
    (203), kept whole on purpose: one subject, 45 of those lines the docstring
    carrying the argument, and a fourth split would leave a file whose prose
    outweighs its assertions.
  - **Six of them**: `src/compare_run.py` (173 -> 206),
    `src/keys/key_promotion.py` (164 -> 202), `src/keys/key_drafting.py`
    (191 -> 202), `src/evaluation/harness.py` (170 -> 221),
    `web/run_record.py` (**156** -> 207) and
    `frontend/src/components/FindingList.jsx` (146 -> 208). Almost all of the
    `src/` and `web/` growth is guard code and the comments explaining *why*
    each guard is there, which is the cost of the fault class above being
    written down rather than merely fixed.
  - **`frontend/` was missing from this inventory entirely** until 2026-09-16,
    which is how `FindingList.jsx` crossed unrecorded while the same change
    recounted the other three trees four times. Counting three trees and calling
    it the count is the same shape of mistake as guarding a document's root and
    calling it guarded. Also over, if CSS counts -- and it should, since the
    palette rules are as much a contract as a module:
    `frontend/src/results.css` (179 -> 274) and `frontend/src/controls.css`
    (118 -> 211).
  - `web/run_record.py` was earlier recorded here as `200 -> 207`. It was
    **156** at `HEAD`: this change grew it by 51 lines, not 7. The `today()`
    sentence below was true of the crossing and wrong about the growth.
  - `tests/web/key_fixtures.py` (242) and `tests/web/test_key_draft_store.py`
    (209). The honest split of the first is the drafted-key *data* from the
    *client plumbing*, now about ten import lines across sixteen files.
  - `frontend/src/results.css` (298) and `controls.css` (231), both grown on
    2026-09-17 by the file viewer's rules and the hover and focus states --
    `results.css` grew *despite* losing the dead `.report-frame` block.
- **The frontend spelled the run-status vocabulary five times**, and the fifth
  had no quotes to be grepped for: `HistoryTable.jsx`'s
  `const TONE = { finished: ..., running: ..., failed: ... }` used bare object
  keys, so the sweep that found the other four walked straight past it. All five
  now read `frontend/src/runStatus.js`, which is held equal to
  `run_record.RUN_STATUSES` name-for-name, and the test that closed it looks for
  object keys as well as string literals. Recorded rather than just fixed
  because the *shape* recurs: a vocabulary can be duplicated in a form your
  search for duplicates cannot see. **`runStatus.js`'s own header is the one
  place that counts them** -- this entry said six for a while, because the
  count included a file written the same hour that never spelled a status, and
  a provenance note repeated in three documents drifted into three stories.

- **Three CSS containment defects have now shipped green, and they are one
  family.** A stylesheet that reads correctly is not a page that lays out
  correctly, and every one of these was found by the user looking at it:
  - a descendant with a negative `z-index` painting behind its own ancestor's
    background, so the wave layer was invisible;
  - a `1fr` grid column that would not shrink, so the page scrolled sideways;
  - and on 2026-09-17, `backdrop-filter` on `.card` establishing a containing
    block, so a `position: fixed` modal opened from inside a card was laid out
    from that card's corner rather than the window's -- compounded by
    `.overlay__card` being a grid item, whose `min-width: auto` refused to
    shrink below a `white-space: pre` child's longest line.

  The last one is now guarded as a **chain** rather than a symptom
  (`tests/web/test_modal_containment.py`, `test_css_fixed_ancestry.py`): the
  card establishes a containing block, the panel is rendered inside the card,
  the viewer is opened by the panel, the modal portals to the body, and
  `:root`/`body`/`.shell` establish no containing block -- that last being what
  a portal actually rests on. A blanket "every fixed element is portalled" rule
  was considered and **rejected on measurement**: of ~20 containing-block
  declarations in the stylesheets, 8 are `@keyframes` steps and 7 more are
  decoration, and 2 of the 3 fixed elements are correctly *not* portalled, so
  the rule would have fired on decoration four times in five and trained the
  next reader to add a registry line without thinking.
- **The palette was retuned on 2026-09-17 and one token had to be fixed by
  measurement.** 99 values across the three `tokens.css` blocks: the accent
  moved off a stock blue to cyan (`#22d3ee` dark, `#0e7490` light), the page
  deepened, the severity ramp widened, and cards, buttons and rows gained depth
  and hover and focus states. **Nothing in this suite can see colour**, and
  `--ink-faint` came out of it failing WCAG AA for normal text in *both*
  themes -- 4.18 on the dark page, 3.83 on the light one, against the 4.5 its
  uses demand, since every one of them is small text (field labels,
  placeholders, card hints, file sizes, pending stages). Raised to `#7b8a9b`
  (5.59 / 4.96) and `#5f6d7d` (4.74 / 5.29) and verified by computing the
  ratios. Two pre-existing non-text failures are still open: `--line` against
  the control it bounds is 1.21 dark and 1.43 light where 1.4.11 wants 3.0 --
  the `.field__input` and `.pick` boundaries, which is the only thing
  identifying them -- and `--on-source-mark` on `--source-mark` is 3.49, which
  is fine only while that control carries an icon and no text.
- **The file viewer trusts the suffix, which is the inverse of the risk it
  guards.** `howToShow` refuses `.pdf` and the archive before a byte is
  fetched, because the viewer's only two paths are a `<pre>` and `srcDoc` on a
  string and the download route sets `Content-Disposition: attachment` on every
  reply -- so there is nothing an `<embed>` could display. What it cannot
  refuse is a file *named* `.json` that is not text: it would be fetched and
  shown as text. Bounded because only this project's own writers create those
  names, which is why it is a line here and not a check.
- **One export in `frontend/src/api.js` has no caller: `fetchDrafts`.** It
  predates 2026-09-17 and is the only one left -- `attachFile` and `uploadUrl`
  went with the evidence panel the same day, so the "three" first written here
  was wrong by the time the sentence was saved. A guard over that module would
  be `export (async )?function NAME` joined against every `import { ... } from
  ".../api.js"` specifier across the sources, **both ways**: an unused export,
  and an import of a name `api.js` does not export -- the second is a build
  failure today and silent in this suite. It lands red on `fetchDrafts`, which
  is the correct state: either the drafts list gets a caller or the function
  goes. Its own change, not folded into a feature.
- **Eleven guards in this suite asserted a token's presence where the claim
  was a relationship, and every one of them passed over the defect it named.**
  Found across five review rounds on 2026-09-18, each measured by building the
  mutated source rather than by reading the assertion. The generalisation, so
  the next reader applies it instead of rediscovering it: **the fault appears
  wherever a claim is about a relationship -- this *before* that, this *inside*
  that, this *gated by* that, this *rendered* rather than merely computed -- and
  the test names only one of the two things.** Five relations, the fifth added
  after the first four proved incomplete: this *before* that, this *inside*
  that, this *gated by* that, this *rendered* rather than computed, and this
  **reached from** that -- a function defined versus handed to its consumer, a
  prop declared versus passed, a callback written versus wired. Worked
  examples, all real:
  - `position_of("<Modal") < position_of(THE_WAIT_NOTICE)` compared against the
    *opening* tag, so a notice written after `</Modal>` -- under the scrim,
    which is the failure the file names -- passed all ten checks in it.
  - `"setError(" in page()` was satisfied by the `setError(null)` at the top of
    the function, so a catch that collapsed the whole list into an error notice
    passed.
  - `"gone += 1" in page()` was satisfied with the count *before* the `await`,
    so a round where two runs were refused would report "5 of 5 forgotten" --
    a result-shaped lie the page authors about itself.
  - `"held.stored_run_count" in page()` was satisfied by the `capped`
    comparison alone, so a page that computed both figures and rendered neither
    passed.
  - Two `failed.length > 0 &&` gates in one file meant a check for "the gate
    appears" passed with the button's own gate replaced by `true &&`.

  The fifth relation is the one that matters most and was found last, because
  **an assertion-first sweep cannot find it.** Enumerating every presence check
  and asking "is the token's presence the claim?" only finds guards that are
  too weak; a relationship with *no assertion at all* has no check to
  interrogate. Measured on 2026-09-18: deleting `onForget={forget}` from
  `HistoryPage.jsx` leaves the whole delete feature unreachable -- every group's
  button calls an `undefined` -- and **the full suite stays green at 5096
  passed**, with two test files pinning that round's internals and neither
  pinning that a click can reach it. So the search needs a second pass in the
  opposite direction: **enumerate the claims, not the assertions.** Two cheap
  forms, either of which catches that class: list every prop and callback each
  changed component passes or receives and ask which are pinned; and read each
  test file's docstring paragraph by paragraph, naming the assertion that holds
  it -- that second one alone finds a docstring promising ", 2 refused" in a
  file where no line mentions it.

  **Three forms, not two, and the third runs the other way.** Both of the above
  go from a *claim* to an assertion. The one they cannot see goes from an
  *assertion to the premise it rests on*: a guard is often written in its strong
  form **because** of a property of the source -- a second occurrence of the
  same token, a weaker line that satisfied the naive check, an explanatory
  sentence in a response body. The guard is right today and the docstring is
  honest. Delete the premise and the guard silently degrades into exactly the
  weak form it replaced, and nothing reports it: form two ticks the paragraph
  off, because its *promise* is asserted and it is the *premise* that is not,
  and form one never sees it, because a premise is not a prop. Measured on
  2026-09-18: deleting the `{failed.length} failed` tag leaves the whole suite
  green *and* removes the reason `THE_GATED_CONTROL` had to be a regex at all.

  **The sharpest instance was self-inflicted while fixing another, and it is
  the form to watch for: tightening a guard can delete the only assertion that
  covered its premise.** `setSaid(` was narrowed to the whole report
  expression *because* `setSaid(null)` satisfied the loose check -- and the
  narrowing took that clear's only assertion with it, so the clear became
  deletable and a second delete round would render the first round's "3 of 5
  forgotten" while it ran. Every tightening should ask what the loose form was
  incidentally covering.

  **And the domain was wrong as well as the direction.** Both claim-first forms
  read *source text*, so they were run over the JSX sweeps alone. The sharpest
  instance was a **behavioural** assertion over a response body:
  `assert read_run(client, run_id)["status"] in detail` was satisfied by the
  detail's own *explanation*, which names both non-failed statuses in prose --
  so `f"this run is {record.status}"` could become `f"this run is not failed"`
  with the suite green, in a file whose title promises the other statuses are
  refused "by name". Ask "is presence the claim?" of every assertion, not only
  of the ones that read files.

  **A premise that holds today is worth disclosing even when nothing can be
  asserted about it.** `THE_GATE_EXPRESSION`'s lazy `.*?\)\}` assumes the first
  `)}` after the gate is the gate's own -- true only because nothing inside that
  block writes one, which JSX does not forbid. A `{f(x)}` added there would end
  the span early and put a later read outside it: a false pass. There is no
  mutation to write, because the premise is not currently violated; the comment
  saying so is the whole mitigation, and it is worth more than silence.

  **The stopping rule, which took seven passes to find and is the useful part
  of all of them: a sampled sweep finds the relations you thought of; a
  rendered relation is only closed by enumerating a finite inventory.** Every
  round here sampled -- and the round whose own docstring declared this
  relation closed was followed by **seven measured MISSED in one 104-line
  component**, including a `<td>` handed the wrong object while 417 lines
  pinned that component's internals. So the terminating move is not another
  search but two enumerations over whatever a change creates: every `(th, td)`
  pair, and every attribute on every element, ticked off once rather than
  spot-checked. After that, further findings of this class are worth recording
  rather than gating on, because the inventory is exhausted instead of merely
  longer -- which is the difference between a loop that ends and one that does
  not.

  **Both enumerations are done for this change, 2026-09-18.**
  `tests/web/test_jsx_history_columns.py` pairs all eight headings with the cell
  expressions under them and walks the two lists pairwise;
  `tests/web/test_jsx_history_attributes.py` checks a closed register of all
  **forty-four** `(element, attribute, value)` triples the three components
  write -- held as data in `tests/web/history_attribute_register.py` -- so an
  attribute cannot leave, change or be duplicated away without a failure that
  asks whether a claim holds it. Together they caught the seven that the seventh
  sampled pass measured MISSED -- among them `options={run}` for
  `options={run.options}`, which had left 5,134 tests green while every row
  reported the options of a record that carries none.

  **The first register was itself closed only by inspection, which is the last
  instance of the pattern and worth recording as such.** It compared two *sets*
  and a length, and its own docstring claimed the length caught "a duplicate
  moving"; three escapes were then measured green -- one duplicated `className`
  becoming another already-registered value, a tag carrying `{...spread}`
  parsing as nothing so its wires landed invisibly, and a scope sentence that
  excused `HistoryTable.jsx`'s "Open every repository" button, which nothing
  anywhere pinned. The fixes: a `collections.Counter` in place of the two sets
  and the length, a per-file floor of parsed tags against opening angle brackets
  (32, 7 and 3), and reading that third file whole rather than one element of
  it. **An enumeration is closed only once its own extractor and its own
  comparison are** -- the same lesson one level up, and the reason the count in
  this paragraph was forty before it was forty-four. Sampling is closed for this
  change; the next pass over it is a read of the diff.

  **That diff read found two more, both in the register file itself**, which is
  the prediction above coming true one level further down: `REGISTERED` and
  `BY_FILE` were each defined twice, identically, by a copy-paste at the foot of
  the data module; and the plant for the duplicate-swap escape asserted
  `Counter` arithmetic over a hand-built multiset without ever calling the
  parser, so it demonstrated the fix nowhere -- the same tautology that had just
  been removed from the columns file's own plant (`3 != 8`). It now parses two
  synthetic snippets in which no value enters or leaves the set and the total is
  unchanged, and the swap is re-measured against the real component: three of
  the seven tests fail, because a `Counter` difference is multiplicity-aware in
  both directions. **A plant that does not run the code it is planted against is
  documentation, not a measurement.**

  **And the review pass after it found the same fault twice more, in prose.**
  `README.md` still said the run overlay "offers one exit, a link to the run's
  page" -- the control this change deletes -- and the sentence had been carried
  verbatim through the README restructure, so the commit would have shipped a
  false claim that contradicted its own Known-defects row above. A comment in
  `test_jsx_overlay_props.py` gave its regex's premise as "a handler prop
  contains an arrow: `onOpenRun={() => navigate(...)}`", naming a prop that no
  longer exists, above a floor that said "Four props today" over
  `MINIMUM_PROPS = 3`. Both are the assertion-to-premise form already recorded
  here, in the one place nothing executes: **a docstring, a comment and a README
  bullet are readers of the code too, and deleting what they describe degrades
  them silently.** The habit that catches it is the one that caught these --
  grep the deleted identifier across prose, not only across code.

  **And one more of the same class survived all of that, in the element the
  register was widened to cover.** The register holds *which* attributes the
  "Open every repository" button writes, not *when* it renders, so its gate was
  never pinned by anything: `groups.length > 1 &&` replaced by `true &&`, or
  deleted outright, left all 5,148 tests green. `test_jsx_history_fold.py` now
  matches the condition joined to the control it hides, with the ungated
  spelling planted as a non-match; both that plant and the off-by-one `> 0`
  were measured caught. **An enumeration of attributes does not close a claim
  about rendering** -- the two are different inventories over the same element.

  Two gaps on that same button are left open deliberately, and named here
  because the register's docstring can no longer claim to cover it whole. Its
  label is `{open.allOpen ? "Close every repository" : "Open every repository"}`
  -- children rather than an attribute, so no register reaches it, and a swapped
  ternary would offer to close what is already closed. The precedent for pinning
  it exists next door in `test_jsx_forget_busy.py`'s `THE_LABELS` /
  `THE_LABELS_SWAPPED` pair, so this is a small piece of work rather than an
  open question. And it carries no `aria-expanded`, while `ExpandAll.jsx`'s
  equivalent control carries `aria-expanded={allOpen}` -- an asymmetry in the
  very convention `test_jsx_history_fold.py` pins for the group headers. That
  one is a source decision, not a missing guard, which is why nothing was
  changed for it here.

  It is not a JSX fault: `test_run_refusal_names.py` exists because the same
  shape was reachable in Python, where two 409s under different constants are
  indistinguishable from a response. The fix in every case was to join the two
  halves into one regex and **plant the alternative as a non-match**, which is
  the only thing that tells a guard that works from a guard that is merely
  green. Five rounds each produced at least one, and the last sweep found five
  at once -- which is information about how hard the search is, not evidence it
  has converged.

- **Nine props in the page are handed from one component to another with
  nothing asserting the handoff**, which is the "reached from" relation above
  applied to the components this change did *not* touch. Found by the same
  claim-first sweep, left alone under rule 15, and listed because a list is the
  useful artifact: `RunStamps record=`, `StageProgress stages=` /`announced=`
  /`status=`, `TopBar page=`, `RunPage stages=` /`onRerun=`, `AuditPage key=`
  /`stages=` /`prefill=`. The measured cost of one of these in the part that
  *was* fixed: dropping `group={group}` from `<HistoryGroup>` left every header
  rendering `undefined.key` with the suite green. `key=` is deliberately not on
  the list -- React's reconciliation hint is not a wire carrying data, and
  pinning it would be stricter than the claim. **`aria-expanded` joins that
  list on five components** -- `HistoryGroup.jsx`, `DownloadPanel.jsx`,
  `FindingList.jsx`, `SurfaceList.jsx`, `ExpandAll.jsx` -- where deleting it
  leaves the suite green and a folded control telling a screen reader nothing
  about its state. A convention gap rather than one change's debt:
  `aria-modal`, `aria-labelledby` and `aria-label` *are* pinned by three
  existing files, so the convention exists and this attribute is outside it.

- **The mutation harness should live in the checkout, and the rule that says so
  is not rule 13.** Rule 13 governs the product's tests. The standard that
  decides this is the one this file already applies to `grading_keys/`: a figure
  measured against something that does not ship is unreproducible from a clean
  checkout. The 47/47 table and every measured-MISSED claim recorded in this
  file are load-bearing evidence produced by a tool nobody else can re-run --
  and on 2026-09-18 a shared scratchpad path proved it can be destroyed
  mid-measurement, which happened to one agent's harness in the middle of a
  round. Two conditions when it lands: a **script**, not a collected
  `test_*.py`, so an ordinary suite run cannot trigger it; and it mutates a
  **copy** of the tree, never the tree, which keeps true of this repository the
  property `test_no_mutation.py` asserts of audited code. Its own task, with the
  node-id, control-row and `(\d+) failed` disciplines below built in.

- **The mutation harness has the same blind spot as the tests it checks, and
  lives outside the checkout, so this entry is the only record of it.**
  Mutations are applied by hand
  and their guards recorded as *file paths*; on 2026-09-18 one came back MISSED
  purely because its guard list still named a file that had since been split.
  An unresolvable name and a guard that does not fire produce the same answer,
  which is the false negative every sweep in `tests/web/` already carries a
  non-vacuity floor to refuse -- one level up, and unrefused. Two structural
  fixes, neither expensive: record each guard as a **pytest node id** and
  resolve every id against `--collect-only` before applying any mutation, so an
  unknown id is a harness error and never a MISSED; and run the guard list
  green on the unmutated tree first, since a mutation result means nothing if
  the named test was already red. The generalisation this project already owns
  fits verbatim: a guard that validates a root and nothing below only moves the
  traceback one frame, and a record that names a file rather than a resolvable
  test cannot tell "no guard" from "wrong name".

  **A second spelling of the same false negative, found the same day and worth
  as much:** a detector testing `"failed" in tail` against pytest's summary
  reported four MISSED mutations as CAUGHT, because `1632 passed, 1 xfailed`
  contains the substring "failed". A MISSED read as a CAUGHT is the direction
  that costs something -- it retires a search. Both cures are the same
  discipline: parse `(\d+) failed` and print the failing node ids, so a result
  nobody can read is not treated as a result.

  **A third discipline, and the one that makes the other two worth having: end
  every run with a control the guards cannot see** -- a comment appended where
  nothing reads it -- and require it to come back MISSED. A harness that cannot
  report a MISSED cannot report anything, and that is the failure direction
  that retires a search rather than prolonging it. The 47-mutation table this
  change ends on carries that row.

- **No test in this suite renders a React component.** Every guard over the page
  is one of three things: a text sweep of the JSX, a lifted plain-JavaScript
  module run under node (`theme.js`, `useExpanded.js`, and `ModelStatus.jsx`'s
  head above its component), or an assertion about the artifact the page reads.
  So a component that reads the right fields, spells the right classes and never
  renders them passes everything here. Closing it means a DOM and a renderer in
  the test dependencies, which is a decision and not a chore. **Three things
  about the run overlay are in exactly that gap** and were checked by eye on
  2026-09-17: whether the fixed card actually covers the page at every width,
  whether it scrolls rather than clipping on a short window, and -- after the
  positioning fix below -- whether it is really centred on the window. A
  portalled, floored card can still be put somewhere wrong by a rule none of
  the guards read.
- Three page changes shipped with no test, judged as presentation with no
  statement to hold: the download disclosure defaulting closed, the sticky
  header, and the re-run button moving into the page head. Named so the judgement
  is visible rather than looking like an oversight.

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
- **Four readers of hand-editable files still crash instead of refusing, and
  the guard is spelled five times.** Found by asking `project-guard` for the
  *next* instance rather than for a verdict, after the same fault had been fixed
  three times in three different files. Nine were closed on 2026-09-16 --
  `key_draft_store`, `fetch_repo._pinned_commit`, `source_routes`,
  `model_client.list_models`, `harness._read`, `promote_key._read` and
  `_object`, `compare_run._standing` -- two of which were introduced *by* the
  fixes. These four are reproduced, not inferred, and are older than this
  change, so they are recorded rather than swept into it:
  - **`emit_vex.product_iri`** is the sharpest, and the first version of this
    entry got it wrong in both directions -- corrected here by measurement, not
    by re-reading. It reads the hand-written
    `grading_keys/<app>.manifest.json` with a bare `json.loads` and then
    *subscripts* it. **Two escapes, not four:** `emit_vex.main` catches
    `OSError` and `ValueError`, so `PermissionError` and the parser's own error
    are already handled; what escapes is `KeyError` (a missing `upstream_url`
    or `upstream_commit`) and `TypeError` (subscripting a list). Both were
    reproduced. The understatement is the part that matters: `product_iri` is
    not only reached from its own command. `pipeline.publish` calls
    `emit_vex.emit` with **no `try`/`except`**, and `export_reports.export_all`
    is the next statement -- so a hand-edited pin missing one field aborts
    publish *after the audit succeeded and `findings.json` is on disk*, takes
    the HTML/PDF export with it, and reaches `main.EXPECTED_FAILURES`, which
    lists neither `KeyError` nor `TypeError` -- nor `PermissionError`, which
    `emit_vex.main` catches and `main` does not, so the pipeline path has three
    escapes where the command has two. That is the same fault class and
    the same after-the-work-succeeded position as `compare_run._standing`, on
    the audit path and with a wider blast radius. The value it computes is the
    **product** every statement in a signed OpenVEX document is about. What
    keeps it a record rather than an emergency: reaching it needs `vexctl`
    installed, advisory data read, *and* a hand-edited pin -- none true on a
    clean checkout, which is also why no test can reach it without those tools.
    Fix it with `pipeline._reused` below: same file, same pin.
  - **`fetch_repo.pin_document`** catches both open and parse faults correctly
    and then passes a non-object straight through; `compare_run` and
    `pipeline._reused` both `.get()` the result.
  - **`pipeline._reused`** reads the pin bare, and its own comment claims "a
    hand-edited or truncated pin is refused with this message rather than a
    KeyError traceback" -- true only for a *missing* key.
  - **A grading key can be silently wrong about its surfaces, in one narrow
    pair.** `harness.check_key` validates that `findings` is a list and does not
    validate `expected_surfaces`. On its own a scalar there is *not* silent --
    promotion refuses it, because the count disagrees. The genuinely silent
    document is the **pair** `expected_surfaces: <scalar>` with
    `expected_surface_count: 0`, where the recomputed length and the stale count
    agree at zero. It needs a deliberate two-field hand edit, nothing in `src/`
    reads the field as a list except the counter and the drafter, and the same
    silence is reachable by writing `expected_surfaces: []`, which no type check
    would stop. Tightening the scorer's gate is a `schema-keeper` question, not
    a fix to slip into a feature.
  - **`config.read_env_file`**: `.env` is the most hand-edited file in the
    project, `parse_env_text` guards the shape, nothing guards the open, and
    `config` is imported at start-up by every command.

  **The generalisation, which is worth more than the list:** a guard that
  validates a document's *root* and nothing below it only moves the traceback
  one frame. Every guard added on 2026-09-16 did exactly that at first --
  `key_draft_store`, `fetch_repo._pinned_commit` and `promote_key._object` all
  confirmed "this is an object" and handed it to callers that subscript its
  members, so a key that *was* an object with a wrong-shaped member crashed
  exactly as before, on all three key routes. Only `harness.check_key` walks
  down. When reading a hand-editable document, guard the field you are about to
  use, not just the document you found it in.

  **And a guard that coerces instead of refusing can be worse than the crash.**
  Treating a malformed `findings` as "no entries" turned a 500 into a 200 that
  wrote an empty list over a draft holding real ones -- a correction request
  destroying what it was meant to correct, reachable from an unauthenticated
  body with no hand-edited file involved. Coercion is right when reading what is
  already on disk and wrong when accepting what someone sent. The same loss was
  then still reachable by *omitting* `findings` rather than mangling it; an
  absent field is now refused while an explicit `[]` still deletes every entry,
  because deletion is a decision somebody makes and omission is a page bug.

  The structural half is that the same six-line guard now appears in
  `harness._read`, `key_draft_store._json_object`, `fetch_repo._pinned_commit`,
  `promote_key._object` and `compare_run._standing`. It belongs in one module
  that each of them calls -- `grading_keys._pinned_commit` had it right before
  any of them and nobody reused it. Doing that is a five-module change and was
  not folded into a feature at the end of a session. **`src/fetch_repo.py` (329,
  now the largest file in `src/`) is where to start**: it does two jobs, the
  `git` subprocess and clone (`_environment`, `_run`, `_check_size`,
  `_fetch_into`, `fetch`) and the pin document (`read_pin`, `manifest`,
  `write_manifest`, `_pin_for`, `pin_document`, `_pinned_commit`,
  `check_tree_matches_pin`, `manifest_path` -- about 130 lines, consumed by
  `emit_vex`, `pipeline` and `web/source_routes`). That second cluster is also
  where the shared guard belongs, so the split and this row are one task.

- **`HistoryStore.delete` takes any run id, and the whole safety of the
  feature is one `if` in its only caller.** The route refuses anything that is
  not `failed`; the store method does not, deliberately -- the route's docstring
  argues correctly against a second enforcement point, since a check written
  twice is a check that can disagree with itself. But **nothing names the route
  as `delete`'s only caller**, so a second caller would bypass the narrowing in
  silence. The cheap guard is an import sweep: exactly one module under `web/`
  may call `store.delete`.

- **`--accept-verification` leaves no trace in the key it let through.** A
  verified draft is refused by `promote_key.py` unless a local human passes the
  flag, which is the counterweight to `verified` being settable through an
  unauthenticated endpoint. But once it is passed, the promoted key is
  byte-indistinguishable from one a human verified by hand-editing the file: the
  flag is a one-time acknowledgement that the artifact does not record. That cuts
  against this project's own discipline, which is that a claim travels with what
  bounds it. Closing it means a field saying *how* the check was recorded, which
  is a schema change and a wider vocabulary -- deliberately not made for a
  feature this size.
- ~~**A tool-drafted key a human has checked cannot be represented.**~~ Closed
  2026-09-16 by relaxing the pairing, which is the option this row named. Schema
  3 forbade `tool_drafted` + `verified: true`, so recording a check meant editing
  `source` -- which erases `key_drafted_by_scored_system`, the warning that
  matters. The pairing is now legal at no version bump (the valid set only
  widened and an old reader refuses by name; see `docs/SCHEMAS.md`, "When a
  version bumps"), the check is recorded through
  `POST /api/keys/{app}/verify`, and the scorer needed no change: verifying
  clears `key_unverified` alone, so a verified draft still carries both drafting
  qualifications. `promote_key.py` will not publish such a draft without
  `--accept-verification`, because the route has no authentication. **What is
  still open is what this never promised:** `key_drafted_by_scored_system` is
  not closable by verification at all, so the circularity in `docs/REPORT.md`'s
  threats-to-validity stands until a human *writes* a key rather than checking
  a drafted one.

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

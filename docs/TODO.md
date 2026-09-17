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
| `web/run_jobs.py` | An audit cannot be stopped once it starts. The page shows progress and no cancel, because a cooperative cancel raising through `progress.stage` would be swallowed by five `except` clauses in `src/` (`export_reports.py`, `main.py`, `retrieval/retrieve.py`, `remediation_run.py`, `checks/planner.py`) and reported as a user-fixable refusal -- a cancel silently becoming a partial success. Doing it properly needs a `stop_requested` field beside `status` and an AST sweep over those clauses. **The cost of this rose on 2026-09-17:** the page now covers itself with a fixed overlay for the length of a run it cannot stop. The overlay refuses to close for that reason -- a dismiss would hide a run that carries on -- and offers one exit, a link to the run's own page, because the scrim covers the nav bar too. |
| `GET /api/model` | Hands an unauthenticated caller every model this machine has pulled and its digest. Loopback is the only thing between that and anyone who can reach the port -- the same mitigation as the row below, on a wider surface. |
| `runs/uploads/` | An unauthenticated endpoint writes attacker-chosen bytes to disk, bounded only by `MAX_UPLOAD_BYTES`, `MAX_UPLOAD_TOTAL_BYTES` and `MAX_UPLOADS_PER_RUN`. They change no finding and nothing under `src/` reads them, but the surface is a write primitive where there was none. **Sharper since 2026-09-17:** the panel that exercised it was removed at the user's request, so this is now a write primitive with no UI reaching it -- still tested by six files, still loopback and hand-started, and still there. Keeping the route for a future panel and dropping it are both coherent; forgetting it is not, which is why this sentence exists. |
| `POST /api/audit` | **No authentication**, and same-origin gives it none: it removes a browser's protection *of other sites*, not of this one. Loopback is the only thing between it and a clone-anything endpoint. |
| `frontend/` | Ticking **Compare models** sends the audited source to a third party. `main.py` puts that behind a flag on the grounds that a flag is something a reader sees in the command they typed; a checkbox is weaker, and the page states the cost rather than the design pretending otherwise. |
| `tests/test_web_framework_containment.py` | The sweep names `fastapi`, `starlette`, `uvicorn`, `http.server` and `socketserver`, but `ast_scan.imported_modules` records `from http import server` as plain `http`, so that one spelling evades it. Naming `http` would also forbid `http.client` — the outbound half, which is `test_offline_containment.py`'s subject, not this one. Closing it properly needs a second scanner. The file's docstring lists exactly which spellings it does and does not name. |
| `tests/web/test_import_path_bootstrap.py` | Counts two directories (`web/`, `src/`) in two import orders. A wrapper module that inserted some *third* directory would go unmeasured. The narrower half of this is closed: the probe now reads `web/*.py` off disk and asserts every module in the folder was loaded, so a module no import chain reaches is named rather than silently left out of the counts. |
| `tests/web/jsx_sweep.py` | Comments are stripped before the accessor sweep runs, so an accessor written inside one is ignored -- intended, since a comment naming `src/artifacts/finding.py` was reported as the field `finding.py` -- but so is the rest of any line where a bare `//` opens what is not a comment. String literals and a scheme's `://` are exempted, both because the page really writes them; `and//or` in prose would still hide the accessors after it. The per-record floors in `test_jsx_record_fields.py` and `test_jsx_coverage_fields.py` are what bound the loss. |
| The whole suite | **Nothing in it can see a rendered page.** Three defects shipped green and were caught only by a screenshot: a wave layer painted behind an ancestor's background (a descendant at a negative `z-index` does), tints twice as strong as intended, and a `1fr` grid track that overflowed the viewport. A `className`-to-bundle join cannot see any of them. Three of the mechanisms *are* guardable textually and should be, shrinking this row rather than leaving it as a blanket excuse: no `background` on the wave layer's ancestors with a non-negative `z-index` on it; the same custom properties in all three `tokens.css` blocks; `minmax(0, ...)` on every flexible track in the top bar. What genuinely needs an eye after that is tone, contrast and overflow. |
| `frontend/` | The page no longer says the endpoint is unauthenticated. The panel saying so was removed at the user's request; `README.md` and the `POST /api/audit` row above still record it, but for a security tool the operator is now told less by the thing they are looking at. |
| `frontend/src/useRun.js` | Two `setState` calls run synchronously inside an effect (the resets when a run id changes), which `oxlint` flags as cascading renders. They are correct -- clearing is what stops a previous run's data showing under a new one -- but the clean form derives the value instead of resetting it, and that is a hook refactor. `frontend/.oxlintrc.json` now ignores `dist/`, so these are the only warnings left and they are visible. |
| `frontend/dist/` | Build output is committed, so a source edit without `npm run build` in the same change serves a stale page. `tests/web/test_built_page_shipped.py` puts a floor under it -- every static `className` literal in the JSX must appear in the built bundle, and every asset `index.html` names must exist -- and `tests/web/test_jsx_advisory_vocabulary.py` covers the braced ones that sweep skips by design, by deriving the tone class stems from the source and requiring a rule for each. Still slipping through: a reworded string, a class name *removed* from the JSX, a changed handler, and a CSS-only edit that touches no class name -- the sweep runs source to bundle, so it cannot see what the source no longer says. **Narrowed on 2026-09-17 for two declarations specifically**: `min-width: 0` on `.overlay__card` and `overflow: auto` on `.viewer__text` are joined to the built bytes by value rather than by selector, because "source fixed, `dist/` stale, suite green, user still sees the bug" was a live failure mode for exactly the positioning fix that closed it. An mtime check would be the real answer and cannot be used: `git clone` writes `dist/` before `src/`, so every source file comes out newer on a fresh checkout. |
| `frontend/` | Auditing one app with a second model overwrites the first run's files: artifacts are keyed on the app name, not the run, so the earlier run is marked superseded and its downloads 409. The model picker says so; keying artifacts on the run is the fix and is not one this change makes. |
| `web/downloads.py` | The hosted arm of a comparison is rendered but its files are not downloadable: `artifacts_present`, `artifacts_current`, `superseded()` and every download route join on the run record's single `artifacts_dir`, which is the local arm's. `artifacts/cloud_auditor/<app>/` is keyed on the app name and just as supersedable, and nothing checks it. The page says so rather than offering a link with no evidence path behind it. |
| `frontend/` + `src/main.py` | A `--compare-models` run announces no stages: `main.run` threads `on_stage` into the ordinary audit but not into `compare_run.run`, so the progress panel stays empty and every stage shows as never reached. Threading it would announce `fetch`…`write` twice, once per arm, which breaks the page's assumption that announcements are a prefix of `STAGES` -- so the real fix is a per-arm shape, not another argument. |

## Open tasks

- **The web UI's remaining polish.** Built: downloads of every file a run wrote,
  the SQLite run history with its own page, live stage progress, timestamps,
  light/dark, and a risk-class filter over the findings. Added since that line
  was written and not previously recorded here -- only their *defects* were, so
  a reader of this roadmap could not tell the page had them: a **drafted-key
  editor** with a verify route, **evidence uploads** attached to a run, an
  **Ollama status pill and model picker**, a **required auditor name**, a
  **source window** showing the lines a surface names, and (2026-09-17) a
  **fixed overlay** carrying the stage list while an audit runs, which navigates
  to the run's own page the moment it finishes, plus a **file viewer** that
  opens any artifact from the download list. Removed the same day at the user's
  request: the rendered-report card, which framed two of the sixteen files the
  viewer now opens, and the **attached-evidence panel**. Not built, and each is a line rather than a
  plan:
  - **Stop a running audit**, and `DELETE /api/runs/{id}` to forget one. Both
    are in Known defects above with the reason the first is not trivial.
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
- Many files sit over the ~200-line rule -- **65 under `tests/` and 15 under
  `src/`**, plus 2 under `web/` (`history_store.py` 204, `run_record.py` 207)
  and 3 under `frontend/src/` (`FindingList.jsx` 208, `results.css` 298,
  `controls.css` 231). The `tests/` growth is the overlay's and the file
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
  - **Six files crossed**: `src/compare_run.py` (173 -> 206),
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

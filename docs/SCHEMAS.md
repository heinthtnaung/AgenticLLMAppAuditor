# Artifact contracts

Every artifact is JSON with a fixed schema and its own `schema_version`. Change
one and you update every reader. Full prior wording is in git before commit
`c10daa0`.

| Artifact | Version | Holds |
|---|---|---|
| `surfaces.json` | 3 | LLM surfaces + files skipped |
| `sbom.json` | 3 | packages, with how each version was established |
| `sbom.cyclonedx.json` | — | the same scan in CycloneDX |
| `aibom.json` | 1 | models, tools, agents, datasets, MCP servers |
| `mapping.json` | 2 | surface → component, and why |
| `findings.json` | 7 | findings, probes, coverage |
| `findings.sarif.json` | — | findings re-emitted as SARIF |
| `findings.openvex.json` | — | OpenVEX, written by `emit_vex.py` |
| `remediation.json` | 2 | per-finding advice + what grounded it |
| `planner.json` | 2 | the check order and what chose it |
| `evaluation.json` | 4 | scores against grading keys |

## Rules that hold across all of them

- **Deterministic.** Same input, same bytes. Records sorted, keys sorted, no
  timestamps, paths repository-relative POSIX.
- **Three exceptions, all model-authored, all inert by default**:
  `findings.json`'s prose fields and its probe records, `remediation.json`'s
  advice, and `planner.json`'s `order`.
- **And one whole directory.** Nothing under `artifacts/cloud_auditor/` is
  byte-identical: a hosted model takes no `seed`, so the arm `--compare-models`
  writes there differs run to run in the fields a model authored. The rule holds
  for every other system.
- **No rate is ever a field in `evaluation.json`.** Counts and denominators
  only, so no number can be quoted without what it is out of.

## Vocabularies

Closed sets. Adding a value bumps the artifact's `schema_version`.

| Field | Values |
|---|---|
| `Surface.kind` | `PROMPT_TEMPLATE`, `AGENT_DEF`, `TOOL_CALL`, `DATA_SOURCE` |
| `Finding.owasp_id` | `LLM01`, `LLM02`, `LLM03`, `LLM06`, `AUDITABILITY` |
| `Finding.detection` | `static`, `probe` |
| `Probe.outcome` | `confirmed`, `refuted`, `inconclusive`, `not_run` |
| `Probe.reason` | `trace_left_static_analysis`, `app_not_runnable`, `step_cap_reached`, `model_unavailable` |
| `mapping.reason` | `third_party`, `stdlib`, `first_party`, `used_but_undeclared`, `unresolved` |
| `aibom.kind` | `MODEL`, `TOOL`, `AGENT`, `DATASET`, `MCP_SERVER` |
| `model_run.status` | `used`, `unavailable`, `disabled` |
| `evaluation.system` | `agentic_auditor`, `baseline_static_rules`, `baseline_sbom_only`, `cloud_auditor` |
| `ground_truth.source` | `ai_drafted`, `manual_review`, `tool_drafted`, `upstream_docs` |

`LLM02` is the **2023** spelling of improper output handling; 2025 numbers it
LLM05. Every other id is 2025.

## findings.json

Keys: `schema_version`, `coverage`, `model_run`, `probe_count`, `checks_narrowed`, `probes`, `finding_count`, `findings`.

- **`coverage.checks_run`** — checks that had something to examine, sorted.
  Absent means "could not look at all", which the scorer reads as
  `no_check_for_risk_class`. A name here no longer implies *every* surface: see
  `checks_narrowed`.
- **`checks_narrowed`** — `{check, examined_surface_count, eligible_surface_count}`
  per narrowed check, `[]` when none. Top level, not inside `coverage`, because
  `sarif.py` copies `coverage` wholesale into an artifact published as
  byte-identical. `examined` counts surfaces *handed to* the check, not subjects
  found. An entry where examined equals eligible is refused, so `[]` is a
  reliable test.
- **`finding_id`** — `{surface_id|component_name|purl|probe_id}:{rule_id}`, plus
  `:{advisory_id}` when set. Unique within the document.
- **A `probe` finding must cite a `confirmed` probe.** Enforced at build time
  and again at render.
- **`advisory_*` fields are non-null iff `rule_id == known_advisory`.** Severity
  is quoted from a named source, never this tool's own rating.

## Grading keys

`grading_keys/<app>.ground_truth.json` + `.manifest.json`. The manifest must
pin `upstream_commit`; a key without one is refused.

**None ships today.** One did, from 2026-09-05 to 2026-09-06; `git show
f9bd9ff:grading_keys/damn-vulnerable-llm-agent.ground_truth.json` recovers it,
and `docs/REPORT.md`'s figures were measured against it. With no key,
`evaluate.py` refuses rather than scoring zero.

**Top-level fields**, thirteen, all required: `schema_version`, `app`,
`upstream_commit`, `source`, `verified`, `verified_by`, `verified_date`,
`findings`, `finding_count`, `findings_complete`, `expected_surfaces`,
`expected_surface_count`, `expected_surfaces_complete`. `harness.check_key`
enforces nine of them — the ones the scorer would crash on; the other four are
held by the promotion checks and by the tests over a promoted key.

**Entry fields.** Required: `id`, `file`, `line`, `owasp_id`, `llm_surface`,
`title`, `description`, and `code_anchor` — the first seven by
`key_promotion.ENTRY_FIELDS`, the anchor by its own check because an absent one
and an empty one are different faults. Optional and nullable: `surface_name`,
`component`, `detection`, `line_end`. The join reads the optional three behind a
truthiness test, which is what makes the next paragraph a trap rather than a
detail.

Two that silently weaken the join if wrong: `llm_surface` is compared against
the finding's `surface_kind`, and **`component` is compared against the
finding's `purl`** — so a bare package name never matches, and an undeclared
package must leave it `null`.

`verified: false` means the scorer attaches `key_unverified` to every figure. A
run against `false` is not thesis-grade and says so.

**Discovery is non-recursive, and that is a contract.** `discover_graded_apps`
globs one level, so `grading_keys/drafts/` is invisible to it, to
`evaluate.py`, to `fetch_repo.check_not_a_graded_app` and to `emit_vex`. That is
what lets the auditor draft a key without enrolling the app against it. Three
modules depend on it; changing the glob to `rglob` breaks all three silently.

Drafts also carry `expected_surfaces` (what the extractor found, so a miss can
be told from a bad find), a per-entry `code_anchor` read from the source rather
than asked of the model, and entries sorted by `(file, line, id)`. A draft that
lacks any of those is refused by `promote_key.py` rather than moved.

**`source` is validated against the vocabulary**, not merely required: a typo
used to be accepted and earn no qualification at all. `ai_drafted` and
`tool_drafted` both earn `key_ai_drafted`; `tool_drafted` earns
`key_drafted_by_scored_system` as well and may never be `verified: true`, since
a tool cannot verify the key it wrote for itself. That qualification is about
**validity, not quality** — it survives a human checking every entry, because
checking cannot make the tool's own choice of what to include independent.

Schema 3 widened `source`. The check is exact equality, so a version-2 key is
refused rather than read by a scorer whose vocabulary has moved under it.

## Study output, not an audit artifact

`model-comparison.json` and `comparison.html`, written by
`experiments/compare_models.py` beside the audit's artifacts. **Deliberately
absent from the table above**, because it fails all three rules those rows
share: it is not produced by `src/`, it is not byte-identical (the hosted arm
takes no `seed` and `seconds` is wall clock), and it cannot be produced offline
or without a key.

It still carries `schema_version` — 1. Nothing validates it, because nothing
reads the document back: it is written once and rendered from memory, and a
loader with no reader would be dead code. The field is there because the shape
has already changed once silently — two incompatible files sit in the untracked
`experiments/results/` with nothing to tell them apart, and the next reader
should not have to guess.

Keys: `schema_version`, `repository`, `subjects_seen`, `arms`, `agreements`, `disagreements`, `not_put_to_a_model`, `not_examined_by_every_arm`, `unmeasurable_exposure`.

- **The four buckets partition `subjects_seen`**, and the producer raises if
  they do not. Only subjects every arm actually put to its model can agree or
  disagree; `not_put_to_a_model` holds the ones the probe settled on the text
  alone, or where no model answered, each with a reason. Counting those as
  agreement is how a run that consulted nobody reported "agree on 1 of 1".
- **`not_examined_by_every_arm` takes precedence**: the planner may narrow the
  probe per arm, and a subject one arm never saw is not comparable whatever the
  others concluded.
- **The one join on `Probe.detail` in the project.** `agreement.py` tells a
  template refuted from its own text apart from one a model called safe. Both
  are `refuted` carrying no reason — `Probe.__post_init__` forbids a reason on a
  concluded outcome — so the sentence is the only marker. It joins on
  `semantic_probe.STATIC_REFUTATION`, a constant `src/` owns rather than model
  prose, and `tests/checks/test_semantic_probe_static_refutation.py` pins the
  two together. A second such join would mean the field is carrying a
  vocabulary and should be given one.
- **`exposure.field_kinds_transmitted` is derived, never asserted.** It comes
  from `prompt_kinds` — the kinds of prompt actually recorded — because the
  planner and the probe share one seam and carry different things.

## evaluation.json

Counts only. `apps[]` carries `true_positives`, `false_negatives`,
`false_positives` (null when the key does not claim completeness),
`matched_key_ids`, `misses` with a reason each, `qualifications`, and
`evidence` — how many findings carry a code, SBOM or VEX link, with the
denominator beside it.

Miss reasons: `no_check_for_risk_class`, `surface_not_extracted`,
`checked_and_silent`, `probe_unresolved`.

## A view, not an artifact

The result envelope, built by `web/run_jobs.py`. It used to be the whole body of
`POST /api/audit`; since the audit became a background job it is the `result`
key of a run record (below), unchanged in every other respect. **Deliberately
absent from the table above**, and for a sharper reason than the study output:
this one is never written to disk as itself. It lives inside an HTTP reply and,
serialised, inside one column of the run history; no loader validates it.

It carries `schema_version` -- **2**, `web/run_record.py::REPLY_SCHEMA_VERSION`,
one constant for everything under `/api/`. It went to 2 when the endpoint
stopped blocking: the seven keys below did not change, the protocol around them
did, and the number exists to tell a page which protocol it is talking to. **The
page that reads it is built separately into `frontend/dist/` and committed**, so
an ordinary checkout can serve a stale bundle against a fresh server.

Keys: `schema_version`, `app`, `artifacts_dir`, `seconds`, `advisories_read`,
`findings`, `surfaces`. All seven always present, exactly as before.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | int | 2. The same constant the enclosing run record carries; the two are equal by construction and a difference is a defect, not a case to handle. |
| `app` | string | The audited tree's directory name, as `audit_run.audit` resolved it. |
| `artifacts_dir` | string | Where the audit really wrote, relative to the server's working directory. Read back from the run, never re-derived. |
| `seconds` | float | The audit's own timer. **Not the run record's `seconds`**: `audit_run.audit` starts counting after the repository is resolved, so a clone sits in the difference between the two. |
| `advisories_read` | bool | Whether advisory data was read at all. `false` means the supply-chain check had nothing to join against -- a gap, not a clean bill. |
| `findings` | object \| null | `findings.json`, verbatim. |
| `surfaces` | object \| null | `surfaces.json`, verbatim. |

- **The two documents are passed through unmodified.** `web/artifacts_read.py`
  parses the file and returns it: it re-keys nothing, drops nothing, adds
  nothing and validates nothing away, so each document's own `schema_version`
  arrives intact.
- **`null` means the audit did not write that artifact. That is not an empty
  one.** "No findings" is a result; "no `findings.json`" is a gap. Rendering the
  two the same way would let a run that *could not look* read as a run that
  looked and found nothing clean, which is the failure mode this whole tool
  exists to make visible. `frontend/src/components/MissingArtifact.jsx` is the
  branch that says it out loud.
- **The seven keys are frozen on purpose.** `ResultsDashboard.jsx` reads four of
  them and was not touched when the endpoint became a job.
- **No determinism claim.** `seconds` is wall clock and `artifacts_dir` resolves
  against the server's working directory, so two identical audits produce two
  different envelopes.

## The run record

What `POST /api/audit`, `GET /api/runs/{run_id}` and `GET /api/runs` answer with.
Not an artifact either, and for a fourth reason beyond the envelope's three: it
is a statement about a *job*, not about an audited app.

**One shape, not two.** The 202 body is this record at the moment of acceptance
-- status `running`, everything not yet established `null`, `stages` empty,
`result` null -- and a poll returns the same keys later in the same run's life.
A page needs one parser. The list endpoint carries the **summary form**, which
is these fields without `result` or `schema_version`; that is the only variation,
and it exists because `result` holds two whole artifacts and fifty of them is
not a view.

| Call | Answers |
|---|---|
| `POST /api/audit` | **202** and the record. `400` for a refusal from `AuditRequest.refusals()`, before any row is written. `409` while another run is in flight. `422` for a body pydantic rejects. |
| `GET /api/runs/{run_id}` | **200** and the record. `404` for an id no row carries, and for an id that is not 32 lowercase hex characters -- "no run has that id" is true of both, and checking the shape keeps a request-supplied string out of a filesystem join. |
| `GET /api/runs` | **200** and `{schema_version, stored_run_count, runs}`. |
| `GET /api/stages` | **200** and `{schema_version, stages}` -- the whole vocabulary, in order, so the page can show what has *not* happened without restating it in JavaScript. |

A tool refusal is no longer an HTTP status. `main.EXPECTED_FAILURES` -- an
unreachable URL, a name a grading key owns, a tree over the size cap -- is
raised *after* the 202, so it lands as `status: failed` and `error`, carrying the
same sentence the command line would have printed. The `400` that remains is the
request rules only.

### Fields

**Every key is always present**; absence is spelled `null`, never a missing key
-- the same choice `web/artifacts_read.py` makes for a document the audit did
not write.

| Field | Type | `null` means |
|---|---|---|
| `schema_version` | int | never null. 2. Top level of each body; list rows do not repeat it. |
| `run_id` | string | never null. `uuid4().hex` -- 32 lowercase hex characters. |
| `repo_url` | string | never null. What was asked for, as asked. The only fact known at acceptance. |
| `options` | object | never null. Exactly `AuditRequest`'s fields, so a re-run is exact. |
| `status` | string | never null. One of `RUN_STATUSES`. |
| `started_at` | string | never null. ISO 8601 UTC, seconds precision. |
| `finished_at` | string \| null | the run is still going. Never "finished at an unknown time". |
| `seconds` | float \| null | the run is still going. The **whole job**, acceptance to terminal status -- not `result.seconds`, which times the audit alone. |
| `stages` | array of string | never null. `[]` means nothing has been announced yet, which is not "no stages ran". Announcement order, values from `progress.STAGES`. |
| `app` | string \| null | the tree has not been resolved yet, or the run failed before it was. **Never guessed from the URL's last segment** -- a guess in a history list is a fact-shaped guess. |
| `artifacts_dir` | string \| null | no directory has been named. Read back from the run, never re-derived. |
| `artifacts_present` | bool | never null. Computed **per request**: the directory exists and holds at least one downloadable name. Coarse on purpose -- not a claim that every artifact is there, and the download endpoint answers per file. Always `false` when `artifacts_dir` is null. |
| `artifacts_current` | bool | never null. Computed per request. `false` when a **later run wrote to the same directory**: artifacts are keyed on the app name, not on the run, so two audits of one URL share `artifacts/<system>/<app>/`. Downloads are refused with 409 when this is false, rather than serving a newer run's bytes under an older run's timestamp. |
| `finding_count` | int \| null | **no `findings.json` stands behind it** -- still running, failed, or finished without the document. It is not `0`. Copied from the document's own `finding_count`, never recounted. |
| `surface_count` | int \| null | the same, from `surfaces.json`'s own count. |
| `error` | string \| null | the run did not fail. Non-null exactly when `status == failed`. |
| `result` | object \| null | the run has not finished. Non-null exactly when `status == finished`. Absent from list rows by design. |

`stored_run_count` on the list body is the **total rows in the store**, not
`len(runs)`: the list is capped at `HISTORY_LIST_LIMIT` newest-first, ordered by
`(started_at DESC, run_id)` so the order is total. A reader comparing the two is
how they learn the history is longer than the page shows.

### Vocabulary

Closed, named in `web/run_record.py` beside the record, the way `OWASP_IDS` and
`PROBE_OUTCOMES` are named beside `Finding`. Adding a value bumps
`REPLY_SCHEMA_VERSION`.

| Field | Values |
|---|---|
| `status` | `running`, `finished`, `failed` |
| `stages[]` | `fetch`, `surfaces`, `dependencies`, `advisories`, `checks`, `advice`, `write`, `publish` -- `progress.STAGES`, in that order |

**`cancelled` is deliberately not a status.** Nothing can write it until a cancel
endpoint exists, and a value no producer writes is a branch every reader carries
for ever against a case that cannot happen -- the same reason `artifacts/vex.py`
refuses `not_affected`.

**A `running` row is only true inside the process that owns it.** A server that
stops mid-run would otherwise leave a row saying `running` for ever, and a
history view spinning on it -- a gap rendered as work in progress. The store
reconciles on open: every `running` row becomes `failed` with the reason named.

### Invariants, all testable

- `status == finished` **iff** `result` is non-null.
- `status == failed` **iff** `error` is non-null.
- `status == running` **iff** `finished_at` is null **iff** `seconds` is null.
- `schema_version == result.schema_version` whenever `result` is non-null.
- `artifacts_dir` null implies `artifacts_present` false.

The first three are enforced twice: by `RunRecord.__post_init__` and again as
`CHECK` constraints on the table, so a row that cannot be true cannot be stored.

## A store, not an artifact

`runs/history.sqlite3`, written by `web/history_store.py` with the standard
library's `sqlite3` and no new dependency. The first durable state this project
owns that is not an artifact, so it is worth saying what it is not: not JSON,
not byte-identical, not produced by `src/`, and not read by any phase. `src/`
does not know it exists and the command line's behaviour is unchanged -- an
audit run from a terminal writes no row.

**Not under `artifacts/`.** Everything there is a documented artifact with a
schema and a byte-identical guarantee, and `/artifacts/` is what
`--artifacts-dir` names; a mutable database would be a new kind of object in a
directory a reader has already learned. `runs/` is gitignored.

**Its version is its own.** `PRAGMA user_version` holds
`history_store.STORE_SCHEMA_VERSION` -- **1** -- and it is unrelated to
`REPLY_SCHEMA_VERSION`: one versions a file, the other versions a wire. A `meta`
table was the alternative and was refused for the reason that *is* the point of
the mechanism: a table must be **found** before it can be read, so `SELECT ...
FROM meta` raises `no such table` on exactly the files whose schema you are
trying to detect. `PRAGMA user_version` answers `0` for any SQLite file ever
written, which makes "0 means not ours, or not initialised" a total answer
rather than an exception. SQLite forbids a bound parameter in a PRAGMA value, so
the number is interpolated from the constant and may never come from a request.

### Table `runs`

One column per durable field of the run record, plus `envelope`.
`artifacts_present` and `artifacts_current` are **not** columns -- they are
computed at read time, because a stored flag about the filesystem becomes a lie
the moment someone cleans `artifacts/`, and a stale claim that a run's evidence
is present is the shape of failure this tool exists to expose.

`stages` and `options` are JSON text rather than tables of their own: both are
read whole and never queried by their parts, `stages`' order is its entire
content, and `options` must round-trip *exactly* -- a column per option would
silently drop an option added to `AuditRequest` later, which is the trap
`PASS_THROUGH_FLAGS` exists to avoid. Both are written with `sort_keys=True` so
the stored text is stable.

`envelope` is what keeps a past run viewable after `artifacts/` is cleaned, which
is why a row is never deleted for having lost its files. **Byte-identity with
the artifact files is not claimed**: the envelope is stored compact and sorted,
the files are written `indent=2, sort_keys=True`. Equality is of content after
parsing. The list query names its columns and never selects `envelope`.

### What opening must do

`sqlite3.connect()` **creates the file**, exactly as `chromadb.PersistentClient`
does -- which is why `src/retrieval/store.py` checks for an index before opening
a client. This store copies that shape, `create: bool = False` and all.

| On open | The store |
|---|---|
| file absent, `create=False` | refuses, **without connecting** |
| file absent, `create=True` | creates it, sets `user_version`, creates the table. The only path that may write a new file. |
| `user_version` matches | uses it, then reconciles stale `running` rows |
| `user_version` differs | **refuses**, naming the path, the version found, the version expected, and that the file must be moved aside |
| not a SQLite file, or unreadable | refuses, wrapping `sqlite3.DatabaseError` with the path |

It never migrates and never deletes. That is the grading key's precedent
verbatim: a version-2 key is refused rather than read by a scorer whose
vocabulary has moved under it, and a run record read by a store whose columns
have moved is the same mistake with worse consequences, because the reader here
is a page showing a person a security result.

**The refusal is fatal at startup, and deliberately not survivable.** A missing
Syft degrades to no bill of materials, because the rest of the audit is still
true. A broken history store cannot degrade: a finished run's findings now
*live* in it, so `GET /api/runs/{id}` would be an endpoint the server advertises
and cannot serve. It is opened once, when `web/api.py` is imported.

**Threads.** The audit runs on a background thread and requests are answered on
a threadpool, so a `sqlite3.Connection` is never shared: each operation opens
its own connection to the path the store holds.

**What it retains.** Every repository URL anyone audited through this server, and
the findings of every finished run, in a file that outlives `artifacts/`. The
endpoints have no authentication, so that history is readable by anything that
can reach the port.

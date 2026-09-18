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

## When a version bumps

A `schema_version` exists so a reader can tell whether it understands the
document in front of it. One criterion covers every case: **bump when a
document that is legal at the old number stops being read correctly at the new
one.** That makes the test a question about **readers and about documents that
exist**, not about whether the rules changed:

- **Bump when an existing reader would be wrong and not know it.** A field that
  changes meaning, a field that is removed, a value added to a closed set the
  reader matches exhaustively, a required field added to something a client must
  *send*. The reader either misreads silently or cannot comply.
- **Do not bump when the valid set only widens and an old reader refuses by
  name.** A document that was illegal and is now legal cannot break a reader
  that already refuses it -- it gets the refusal it was written to give, with
  the reason in it, which is exactly the protection the number exists to
  provide. Bumping there costs something real: every document on disk at the old
  number is orphaned, and for drafts under `grading_keys/drafts/`, which git
  ignores, orphaned means gone.
- **Narrowing is the third direction, and it splits.** Making a rule stricter
  matters only if some document that was legal, *and that a producer really
  wrote*, becomes illegal. Then bump: those documents exist and their holder
  must be told the vocabulary moved under them. But a rule that only refuses
  documents no producer could ever emit — a type every writer already wrote and
  every reader already assumed — narrows nothing that exists. It closes a gap
  between what the schema *said* and what it always *meant*, and the fix is to
  write the meaning down, not to move the number. Read the test backwards: a
  bump warns whoever holds a document at the old number, so it earns its cost
  only when such a document is out there.

The worked case for narrowing: `harness.TYPED_ENTRY_FIELDS` began refusing
`"line": "4"` on 2026-09-16 and did **not** bump schema 3. `key_drafting.draft`
drops any entry whose `(file, line)` is not one the extractor found, and the
extractor's line is `Surface.line: int` — so no key this project has ever
written could carry a string there. Only a hand edit could, and a hand edit is
not a version. The documents that changed treatment were never legal; they
crashed, and a `TypeError` is not a reader being wrong without knowing it.

The worked case for widening is the same file. Relaxing `tool_drafted` + `verified: true`
from refused to legal did **not** bump schema 3: an old `check_key` meeting such
a key raises with its own sentence naming the pairing, and a bump would have
discarded the drafts that existed at the time in exchange for nothing. The
counter-case is under "The run record" below -- the reply went to 3 when
`auditor` became **required**, because a stale bundle cannot post a body without
a required field, so it gets a 400 instead of a degraded render.

## Vocabularies

Closed sets. Adding a value bumps the artifact's `schema_version` -- a reader
matching one exhaustively is the first case above.

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

**Entry fields.** Required: `id` (string), `file` (string), `line` (int),
`owasp_id` (string), `llm_surface` (string, nullable), `title` (string),
`description` (string), and `code_anchor` (string, non-empty) — the first seven
by `key_promotion.ENTRY_FIELDS`, the anchor by its own check because an absent
one and an empty one are different faults. Optional and nullable:
`surface_name` (string), `component` (string), `detection` (string), `line_end`
(int). The join reads the optional three behind a truthiness test, which is what
makes the next paragraph a trap rather than a detail.

**Four of those types are enforced, and the rest deliberately are not.**
`harness.TYPED_ENTRY_FIELDS` refuses a `file` that is not a string, a `line`
that is not an int and an `id` that is not a string;
`NULLABLE_TYPED_ENTRY_FIELDS` does the same for `line_end` when it is present
and not null. Those four are the ones the scorer does *arithmetic and ordering*
on — `grading.line_window` adds to `line` and `line_end`, and both
`key_promotion._out_of_order` and `scorer`'s `matched_key_ids` and `misses` sort
on `id` — so a wrong-typed one is a `TypeError` out of the scorer rather than a
refusal. The others cannot crash: `owasp_id` is only ever compared,
`llm_surface` sits behind a truthiness test, `code_anchor` is truthiness-tested,
and `title` and `description` are never read by the scorer at all. **Typing them
anyway would be a check stricter than this schema, which is as wrong as a looser
one and harder to spot, because its own tests pass.**

`id` was left out of that list at first, on the reasoning that its crash needs
two entries of *mixed* type where `line` needs one, so it required a hand edit.
That was measured false on 2026-09-16 and is recorded here because the wrong
reasoning is instructive: **`key_drafting._is_grounded` bounded `owasp_id`,
`file` and `line` against the extracted surfaces and not `id`**, so a model
reply naming one surface twice with the ids `1` and `"K-02"` — the exact shape
`_colliding_pairs` exists to refuse — reached the `(file, line, id)` sort and
raised. No hand edit, and `TypeError` is in neither `pipeline.DRAFTING_FAILURES`
nor `main.EXPECTED_FAILURES`, so `--draft-key` ended in a traceback *after* the
audit had succeeded. The drafter now drops such an entry and the gate types the
field. The exclusion argument was also self-contradicting: this schema calls
`id` a string three paragraphs up, so typing it refuses nothing the schema
allows.

**`true` is refused for all three, and that clause is not pedantry.** `bool`
subclasses `int` in Python, so `isinstance(x, int)` accepts `true` — and a
boolean is the one shape in this family that fails *silently*. A string `line`
raises and somebody reads the traceback; `line: true` scores against whatever
was found in the first four lines, and `line_end: true` windows to `(7, 4)` for an entry
at line 7 — a start *after* its end, so the entry matches nothing and reads as a
miss the tool earned. (At `line: 1` the two failures coincide; it is the entries
further down a file where `line_end: true` is its own fault.) Both were
measured. A reader who does not know `bool` is an `int` would
take "line: int" to exclude `true` already; it does not, and only a second
clause does.

Two that silently weaken the join if wrong: `llm_surface` is compared against
the finding's `surface_kind`, and **`component` is compared against the
finding's `purl`** — so a bare package name never matches, and an undeclared
package must leave it `null`.

`verified: false` means the scorer attaches `key_unverified` to every figure. A
run against `false` is not thesis-grade and says so. `true` clears that one
qualification and **no other** -- see the `source` paragraph below, which is
where the pairing with `tool_drafted` is explained.

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
`key_drafted_by_scored_system` as well. That qualification is about **validity,
not quality** — it survives a human checking every entry, because checking
cannot make the tool's own choice of what to include independent.

**`source` and `verified` are orthogonal, and since 2026-09-16 the pairing
`tool_drafted` + `verified: true` is legal.** `harness.check_key` refused it
until then, on the reasoning that a tool cannot verify the key it wrote for
itself — but that conflated two different facts. Who *chose* the entries is
`source`; whether a human has *read* them is `verified`. The refusal left a
human who had checked every entry with no way to say so except by editing
`source`, which would have erased `key_drafted_by_scored_system` — losing the
warning that actually matters in order to record a weaker one. The qualification
sets make the distinction safe:

| `source` | `verified` | qualifications **from these two fields** |
|---|---|---|
| `tool_drafted` | `false` | `key_ai_drafted`, `key_drafted_by_scored_system`, `key_unverified` |
| `tool_drafted` | `true` | `key_ai_drafted`, `key_drafted_by_scored_system` |
| `manual_review` | `true` | none |

Those three are the only qualifications these two fields earn --
`_qualifications` attaches others (`findings_not_complete`, `no_key_findings`,
`scan_partial`, `small_sample`) from the artifacts and from the rest of the key,
so no row above is the whole list a run carries. Verifying clears
`key_unverified` and nothing else, so **a verified drafted key can never read as
an independent measurement** — that property is the whole safety argument for
allowing the pairing, and `tests/compare/test_drafted_key_circularity.py` is
where it is held, in both directions.

Schema 3 widened `source`. The check is exact equality, so a version-2 key is
refused rather than read by a scorer whose vocabulary has moved under it.
**Relaxing the pairing did not bump the version**, for the reason under "When a
version bumps" near the top of this file.

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

It carries `schema_version` -- **3**, `web/run_record.py::REPLY_SCHEMA_VERSION`,
one constant for everything under `/api/`. It went to 2 when the endpoint
stopped blocking: the keys below did not change, the protocol around them did,
and the number exists to tell a page which protocol it is talking to. It went
to 3 when a run gained a **required** `auditor` -- an old bundle ignores a key
it does not know, but it cannot post a body without a required field, so it
gets a 400 rather than a degraded render. The `comparison` key added in the
same change would not have earned a bump on its own. **The
page that reads it is built separately into `frontend/dist/` and committed**, so
an ordinary checkout can serve a stale bundle against a fresh server.

`canonical_repo_url` was added on 2026-09-18, for grouping the history by
repository, and did **not** bump the number by the widening rule above: an old
bundle ignores a key it does not know and simply groups nothing. **The
tolerance runs one way only, and this is the direction the rule does not
cover.** The new bundle *requires* that key -- `repoGroup.js::groupRuns`
groups on it with no fallback, so a reply without it puts **every run into one
group** whose key is `undefined`: a `Map` matches that key after the first row,
so the page renders one repository holding everything rather than failing --
a gap shown as a result, which is the one thing this page may not do. That is
safe here only because `frontend/dist/` is committed beside the server and both
moved in the same commit; it is not a property of the addition. A key a page cannot render
without is a required field in everything but name, and the next one added to a
reply the page *must* have should be read against the first bullet above, not
the second.

Keys: `schema_version`, `app`, `artifacts_dir`, `seconds`, `advisories_read`,
`findings`, `surfaces`, `comparison`. All eight always present.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | int | 3. The same constant the enclosing run record carries; the two are equal by construction and a difference is a defect, not a case to handle. |
| `app` | string | The audited tree's directory name, as `audit_run.audit` resolved it. |
| `artifacts_dir` | string | Where the audit really wrote, relative to the server's working directory. Read back from the run, never re-derived. |
| `seconds` | float | The audit's own timer. **Not the run record's `seconds`**: `audit_run.audit` starts counting after the repository is resolved, so a clone sits in the difference between the two. |
| `advisories_read` | bool | Whether advisory data was read at all. `false` means the supply-chain check had nothing to join against -- a gap, not a clean bill. |
| `findings` | object \| null | `findings.json`, verbatim. |
| `surfaces` | object \| null | `surfaces.json`, verbatim. |
| `comparison` | object \| null | The hosted arm of `--compare-models`. `null` means one arm ran -- never that a second arm found nothing, and never an empty object. |

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
- **Seven keys about one audit, plus an optional eighth.** `comparison` is
  `null` on every ordinary audit and non-null only under `--compare-models`. It
  is *added*, never a restructure, and the difference is not cosmetic: a stale
  bundle ignores a key it does not know and shows the local arm, whereas
  reshaping the seven would leave `result.findings` undefined and render a run
  that audited *twice* as a run that wrote no `findings.json` -- a gap shown as
  a result, which is the one thing this page may not do. That rules out
  reshaping them, permanently.

- **The hosted arm is the envelope's six audit keys plus two names**: `system`
  is `cloud_auditor` and `compared_with` is `agentic_auditor`, both from
  `evaluation.document` -- the vocabulary `evaluation.system` already lists,
  so the page spells neither.
  `schema_version` is deliberately **absent** from it: the envelope carries it
  once, and one constant repeated inside one reply is two numbers that can
  disagree. The two arms differ in `artifacts_dir` and `seconds` and are
  identical in shape otherwise.

  **Nothing under `artifacts/cloud_auditor/` is byte-identical**, so
  `comparison.findings` carries model-authored prose that differs run to run.

  **Downloads are the local arm only.** `record.artifacts_dir` is one value, and
  `artifacts_present`, `artifacts_current` and every route in `downloads.py`
  join on it. The hosted arm's files are shown and are not downloadable, and
  nothing checks whether a later run overwrote them -- which the page says
  rather than implies.
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
| `DELETE /api/runs/{run_id}` | **200** and `{schema_version, forgotten}`. `404` for an id no row carries and for a malformed one, on the same reasoning as the row above. `409` when the run is not `failed`: the request is well formed and the run's *state* refuses it, which is the distinction `ALREADY_RUNNING` and `SUPERSEDED` already draw. The body echoes the id and carries nothing a caller needs -- it exists so every reply under `/api/` has a `schema_version`. |
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
| `schema_version` | int | never null. 3. Top level of each body; list rows do not repeat it. |
| `run_id` | string | never null. `uuid4().hex` -- 32 lowercase hex characters. |
| `repo_url` | string | never null. What was asked for, as asked. The only fact known at acceptance. |
| `auditor` | string | **never null, never blank.** Who ran this audit, stripped of surrounding whitespace, capped at `MAX_AUDITOR_LENGTH` with control characters refused -- it is the one operator-supplied string that is not a URL and it is rendered. Free text on an endpoint with no authentication, so it is a claim and not an identity. |
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
| `canonical_repo_url` | string | never null. **Computed per request, never stored.** `repo_url` in the one spelling that decides whether two runs are of the same repository, from `src/repo_url.py::canonical_url`: a trailing slash and a `.git` suffix removed and **nothing else normalised**, because two owners with the same repository name are two repositories. Served rather than re-derived by the page: `pipeline._reused` joins on the same function, and a page that disagreed would show two groups for a repository the tool treated as one. |
| `finding_count` | int \| null | **no `findings.json` stands behind it** -- still running, failed, or finished without the document. It is not `0`. Copied from the document's own `finding_count`, never recounted. |
| `surface_count` | int \| null | the same, from `surfaces.json`'s own count. |
| `error` | string \| null | the run did not fail. Non-null exactly when `status == failed`. |
| `uploads` | array of object | **never null.** `[]` means nothing was attached -- a fact the endpoint can always establish, not a gap. |
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
`history_store.STORE_SCHEMA_VERSION` -- **2** -- and it is unrelated to
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
is why a row is never deleted for having lost its files. A *failed* row may be
forgotten on request, which is a different reason and a row with no envelope to
lose. **Byte-identity with
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
| `user_version` differs | **refuses**, naming the path, the version found, the version expected, and that the file must be moved aside -- saying also that it is **not deleted** and stays readable with any sqlite3 client |
| not a SQLite file, or unreadable | refuses, wrapping `sqlite3.DatabaseError` with the path |

**Version 2 is the first time that rule cost anything, and it still holds.**
The change adds three things and they do not migrate alike: an old row named no
model, so `null` is *true* of it, and attached nothing, so `[]` is *true* of it
-- but **`auditor` has no true value at all**, because nobody recorded who ran
it. An `ALTER TABLE ADD COLUMN auditor` would have to fabricate a name or admit
a null, and this document already forbids the first by name: `app` is never
guessed from the URL's last segment, because a guess in a history list is a
fact-shaped guess, and a guessed auditor is that sentence with a person's name
in it. So refusing is not a preference chosen over migration -- a required,
never-null `auditor` makes a version-1 row unrepresentable, and refusing is what
that means. A future column where every old row has an honest value is a case
this paragraph does not decide.

It never migrates a file and never deletes one. That is the grading key's precedent
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

**Rows are a different subject, and one kind may be forgotten.**
`DELETE /api/runs/{id}` removes a **failed** run's row on request. What makes
that safe is a constraint and not a convention: `(status = 'failed') = (error IS
NOT NULL)` and `(status = 'finished') = (envelope IS NOT NULL)` together mean a
failed row's envelope is NULL, so forgetting one destroys no findings -- and a
failed row names no `artifacts_dir`, so it cannot move another run's
`artifacts_current`. Every other status is refused with 409. The *file* is still
never migrated and never deleted.

`runs/uploads/<run_id>/` survives a forgotten row and is then unreachable: the
upload route answers 404 without a record, and nothing cleans the directory.
Recorded in `docs/TODO.md` rather than swept.

## Attached evidence, and not an artifact either

`runs/uploads/<run_id>/<upload_id>`, written by `web/uploads.py`. Files a person
attached to a run. **Not artifacts** on every count this document uses: not
produced by `src/`, not byte-identical, not read by any phase, not part of a
schema a later phase consumes. And one count no other object here has -- they
are attacker-chosen bytes arriving at an endpoint with no authentication.

**They change no finding.** Nothing under `src/` reads this directory, no check
joins on an upload, and `findings.json` is untouched -- which a test asserts
rather than the prose claiming it. They are evidence for a person reading the
page; the audit does not know they exist.

**No control on the page reaches these routes since 2026-09-17**, when the
attached-evidence panel was removed at the user's request. The routes, the
record's `uploads` field and their six test files are all untouched, so this
section still describes what the server does -- but a reader should know that
this is now a write endpoint with no UI behind it, and that
`docs/TODO.md` carries that as an open decision with both options named.

**The stored filename is the `upload_id`, never the client's name.** That is the
security property and not a naming convention: attacker-chosen bytes never
choose a path component. The name a browser sent lives only in the record, where
it is data. Both ids in the route are server-generated 32-hex, checked against
the pattern the run routes apply.

| Field | Type | Meaning |
|---|---|---|
| `upload_id` | string | `uuid4().hex`. Server-generated. The only name that reaches the filesystem. |
| `name` | string | The client's filename. Display only; never a path, never joined. |
| `bytes` | int | Size as stored. |
| `sha256` | string | Of the stored bytes. Evidence with no digest cannot be shown to be the bytes that were attached, and the record outlives the files -- except when the run is *forgotten*, which is the one case where the files outlive the record and become unreachable. |

The client's declared `Content-Type` is deliberately **not** stored: it is
attacker-chosen and could only ever be echoed back, which is how a sniffed
upload renders in this origin.

Caps, all named constants: `MAX_UPLOAD_BYTES`, `MAX_UPLOAD_TOTAL_BYTES`,
`MAX_UPLOADS_PER_RUN`, `MAX_UPLOAD_NAME_LENGTH`. No content allowlist --
evidence may be any bytes -- so the protection is on the way out instead. The
body is **streamed** and refused past the cap rather than buffered and measured:
a cap enforced after buffering is not a cap, and `Content-Length` is the
client's claim while the running total is the fact.

### A separate route, not a wider allowlist

`POST /api/runs/{run_id}/uploads?name=...` with the bytes as the body, and
`GET /api/runs/{run_id}/uploads/{upload_id}`. Always an attachment, always
`application/octet-stream` with `nosniff`, never inside `artifacts.zip`.

`web/downloads.py` serves only names `artifacts/names.py` owns, and that stays
true. Widening `DOWNLOADABLE` would put attacker-supplied names into a constant
**`src/` owns** and five modules there read. `test_artifact_inventory.py` holds
`ALL_NAMES` against what the writers actually produce, a join an upload can
never satisfy. `bundle()` would ship attacker bytes inside an archive a reader
takes for the run's own output. And `_directory()` refuses on `superseded`, so
an upload would become unreachable exactly when a later run overwrote a
different directory. The simplest reason last: an allowlist of sixteen fixed
names cannot describe an open set.

**How a reader tells the two apart**: a different route, a different directory
root, and the record -- `uploads[]` lists uploads, and
`GET /api/artifacts/{run_id}`'s `files[].name` is always a member of `ALL_NAMES`.

## Model status, which is a reply and not a file

`GET /api/model`. Carries `schema_version` because every body under `/api/`
does -- one constant, seven bodies, and an exception here would be something a
reader has to learn for no gain.

**A gap must not read as "no models".** `models` is `null` when the local Ollama
did not answer and `[]` when it answered holding nothing. Two different facts,
and the same distinction `findings: null` carries against `findings: []`.

| Field | Type | `null` means |
|---|---|---|
| `schema_version` | int | never null. `REPLY_SCHEMA_VERSION`. |
| `reachable` | bool | never null. Whether the local model server answered. |
| `error` | string \| null | it answered. Non-null exactly when `reachable` is false, carrying `model_client`'s own sentence -- which already names the fix. |
| `models` | array \| null | **not reachable.** `[]` is "reachable, nothing pulled". |
| `models[].name` | string | -- as Ollama reports it, tag included. |
| `models[].digest` | string \| null | Ollama listed none. |
| `models[].bytes` | int | -- |
| `configured_model` | string | never null. What `AUDITOR_MODEL` resolves to. |
| `configured_model_pulled` | bool \| null | not reachable, so not knowable -- which is not `false`. |
| `embed_model` | string | never null. `AUDITOR_EMBED_MODEL`. |
| `embed_model_pulled` | bool \| null | the same. |

`models` is sorted by `name`. **No determinism claim**: this is live status, on
the same footing as the envelope's `seconds`.

**200 even when Ollama is unreachable.** This server answered; the model server
did not, and that is the body's subject. A 503 would be discarded by the page's
own error path, which keeps only `detail` -- turning a stopped model server into
a generic failure, which is the gap-as-noise this body exists to prevent.

**`configured_model_pulled` is the field that earns its keep**: a configured
model that is not pulled raises `ModelNotPulled` mid-run, after the repository
has already been cloned. `embed_model_pulled` carries the tag trap this project
measured -- Ollama lists a pulled model as `name:latest`, so
`AUDITOR_EMBED_MODEL` must carry its tag or the match silently fails.

The list comes from `src/model_client.py`, never a second `urllib` call in
`web/`: that module already parses `/api/tags` for `model_digest`, and a test
forbids the transport under `web/` outright.

## Drafted grading keys, corrected in a browser

`GET /api/keys`, `GET /api/keys/{app}`, `PUT /api/keys/{app}`, served by
`web/key_routes.py` over `grading_keys/drafts/` and **nothing else**.
`grading_keys/` holds the answers this tool is scored against; an unauthenticated
endpoint able to rewrite those would let anyone who reaches the port rewrite the
project's own measurements. A draft is invisible to scoring until
`promote_key.py` publishes it, because `discover_graded_apps` globs one level --
which makes that non-recursive glob load-bearing for a fourth reader.

| Field | Type | Meaning |
|---|---|---|
| `drafts` | array of string | On the list body: every app with a drafted key, sorted. `[]` is a fact -- no drafts exist. |
| `app` | string | On a single-key body: the app the key is for. |
| `key` | object | The grading key document, schema 3, verbatim. |
| `frozen_fields` | array of string | What an edit may not change, served so the page does not restate the list. |
| `refusals` | array of string | What `key_promotion.refusals` would still say. `[]` means promotion would accept it. |

**An edit never upgrades a key's standing.** `source`, `verified`,
`verified_by`, `verified_date`, `schema_version`, `app`, `upstream_commit`,
`findings_complete`, `expected_surfaces_complete`, `expected_surfaces` and
`expected_surface_count` are refused **by name**, not silently restored -- an
editor that quietly put `source` back would accept a request that meant to
launder the key and answer as though it had worked. The case that makes this
necessary: `tool_drafted` + `verified: false`, `tool_drafted` +
`verified: true` and `manual_review` + `verified: true` are *all* valid
documents, so a save free to move the *pair* passes every check there is and
turns a drafted key into one that reads as human-authored. A drafted key stays
`tool_drafted` however much of it a human corrects, and promotion leaves that
alone too, because `key_drafted_by_scored_system` is about **validity, not
quality**: checking the entries cannot make the tool's own choice of *what to
include* independent of the tool.

The list is `web/key_edit_guard.py`, not `key_routes.py` -- both routes consult
it, and it is the editor's whole security argument in one file.

### `POST /api/keys/{app}/verify`

Records that a human checked every entry of a draft. Body: `{verified_by}`.
Answers the same envelope as `GET /api/keys/{app}`.

**Its own route, deliberately not part of a save.** Correcting a title and
signing off a key are different acts, and keeping them apart is what lets every
field above -- `source` and `verified` included -- stay frozen for a save. This
route moves `verified` alone, so the pair can never travel together.

| Rule | Why |
|---|---|
| `verified_by` is validated by `run_record.auditor_refusals` | The same spelling the auditor name uses, and the same reason: this server has no authentication, so the name is a claim, not an identity. Empty, over `MAX_AUDITOR_LENGTH`, or carrying control characters is a 400. |
| `verified_date` is **server-observed**, never accepted from the body | A date the client supplies can be backdated, and a key's verification date is a fact about when a person looked, not about what they typed. |
| A key already `verified` is refused, 400, naming the first verifier | A second claim must not quietly replace the first. Withdrawing one is a hand edit of the file. |
| `source` is not touched | The key stays `tool_drafted`, so `key_ai_drafted` and `key_drafted_by_scored_system` both go on firing. This route clears `key_unverified` and nothing else. |

**Promotion gates what this route records.** The claim is made through an
endpoint with no authentication, and promotion is the moment it starts bounding
a published figure -- so `promote_key.py` refuses a verified draft unless a
local human passes `--accept-verification`.

**An anchor may not be typed.** `file`, `line` and `code_anchor` are quotations
from source the browser has not read -- the same rule the drafting prompt puts
on the model. An entry the draft never held counts as moving one: appending a
well-formed entry with a fabricated anchor passes every downstream check, so
promotion would publish ground truth quoting a line nobody looked at.

**`finding_count` is recomputed and `findings` re-sorted** by `(file, line, id)`
on every save, because `key_promotion._miscounted` and `_out_of_order` refuse a
key that is neither.

**Validation is reported, not enforced.** `key_promotion.refusals` is the only
validator -- a second copy here would drift from the one promotion uses -- but a
save is not gated on it. Most of what it reports concerns the *manifest*, which
names a framework and a language that are human judgements a draft cannot
supply and this page cannot edit; gating on those would make a draft impossible
to correct at all. The gate is `promote_key.py`, which is what actually
publishes.

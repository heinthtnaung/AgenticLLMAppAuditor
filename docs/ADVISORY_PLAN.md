# Advisory ingestion — Phase 2's unfinished item

**Not a phase plan.** This is one cross-cutting item that Phase 2 left open, and
it is planned on its own because three other things are queued behind it: a
vulnerability check, the VEX layer, and any claim this tool makes about
supply-chain risk beyond "this package was never declared".

**Goal:** know what is *wrong* with a component, not only that it is there. An
SBOM states presence; only advisory data states risk.

**Input:** a pinned advisory snapshot on disk, plus the `sbom.json` and
`mapping.json` this tool already builds. **Output:**
`coverage.advisory_data: "snapshot"` instead of `not_ingested`, and a new check
reporting a declared dependency with a known advisory against its exact version.

## Precondition: the corpus is not on disk

**A4 cannot run today, and neither can most of A2's and A3's done-criteria.**
All nine `corpus/evidence/*.json` — every grading key, manifest and baseline —
are deleted in the working tree. `TODO.md:347`'s **Task 3.8a**, "restore corpus
fixtures from their pinned manifests", is unticked, and the manifests it would
restore from are themselves among the deleted files, so the restore path needs
settling before it can be walked.

**Task 3.8a is a hard precondition of A4** and of any done-criterion phrased
against a fixture. A1 and A2 can proceed without it — a matcher is testable on
OSV records alone.

## Why now, concretely

`Kilo-Org/security-agent-testbed` was audited and reported **0 findings** across
528 components. Its README names **45 packages** as deliberately vulnerable (47
counting the no-fix pair `request`/`ip`), all 47 present in the SBOM and 46
declared in `package.json`. The tool had already found every one of them at
exact versions — `ejs@3.1.6`, `lodash@4.17.19`, `jsonwebtoken@8.5.1` — and had
no way to know any of them mattered. That is this item, demonstrated rather than
argued.

**What that repo is not is a grading key.** Its README reports **71 npm-audit
advisories bucketed by severity** (17 critical / 32 high / 18 moderate / 4 low).
It contains **no CVE ids at all** — `grep -c "CVE-"` returns 0 — and no code
locations. A key entry needs `file`, `line`, `owasp_id` and `llm_surface`, and
the README supplies none of them. It is a source of *component-level
expectations* for validating the matcher, not an evaluation fixture. See
settle-first item 6.

**Measured against a scanner that has the data.** Trivy 0.74.0 on the same tree
reports **311 vulnerabilities** -- 22 critical, 128 high, 284 unique CVEs across
68 packages -- where this auditor reports 0. That is the size of the gap
advisory data closes, and it is the number to quote when arguing this item is
worth doing. Three of Trivy's findings have no fix available, in `dompurify`,
`ip` and `request`, which matches the README's own "no fix available" pair and
is independent evidence the tree is being read correctly.

**And it will still report zero findings after this work**, for a reason worth
understanding before starting rather than after: it has no LLM surfaces. It is
the example that shows why advisory data is needed, not the example that
demonstrates the result. Settle-first item 1 has the detail.

## ~~The source: OSV~~ — reversed: the source is Trivy, run like Syft

**Reversed deliberately, on the project's own argument.** The section below is
kept as the record of the alternative. What changed: a version matcher — four
OSV event types, two ordering schemes, alias collapsing — is a spec this
project does not own, and re-implementing it puts this project's code between
the advisory database and the reader. That is word for word the argument that
made `vexctl` the right consumer for VEX and Syft the right producer for the
SBOM. So the advisory engine is **Trivy**, the fourth external binary, run
offline the way Syft is (`src/deps/trivy_runner.py`), and tasks A1 and A2
collapse into that runner. Task A3 — the anchoring join, which is the thesis
contribution — is unchanged.

Measured before deciding, Trivy 0.74.0:

| Property | Result |
|---|---|
| Offline once the DB is cached | `--skip-db-update --offline-scan` exits 0 with a PATH-only env; telemetry and version check disabled by flag |
| Pinnable | the DB's `metadata.json` carries `UpdatedAt` (a property of the build); `DownloadedAt` is the local clock and is never recorded |
| Deterministic | byte-identical across runs except top-level `ReportID`/`CreatedAt`, which are not stored — no raw Trivy artifact is written |
| Join key | `PkgIdentifier.PURL` on all 311 findings of the testbed — the exact key `mapping.json` holds |
| Identifier schemes | `CVE-` and `GHSA-` only — both match `vexctl filter` |
| Matching rule agreement | on the Python fixture's unpinned `requirements.txt` Trivy reports **0**, matching this project's own pinned/locked-only rule |

And the join itself, measured on the corpus: `oss-app-langgraphjs-starter`
carries **26 advisories** in its locked tree, of which exactly **2** sit in a
component an LLM surface reaches — `@langchain/community@0.3.3`, reached by the
`TavilySearchResults` tool call at `src/agent.ts:9` — with 11 advisory-carrying
components reached by nothing. So the anchoring design yields 2 findings and an
honest count of 11, not a wall of CVEs: the volume concern in settle-first
item 2 is answered by measurement.

## The recorded alternative: OSV

Measured **2026-09-01**, against the live API and the bulk endpoints:

| | |
|---|---|
| `osv-vulnerabilities.storage.googleapis.com/npm/all.zip` | 222 MB, HTTP 200 |
| `.../PyPI/all.zip` | 34 MB, HTTP 200 |
| `api.osv.dev/v1/query` for `lodash@4.17.19` | 5 records — but only **3 distinct vulnerabilities** (see A2) |

OSV fits the policy already written at `SCHEMAS.md:464-473`: bulk-downloadable,
so it is fetched **out-of-band as a documented manual step** and read from disk,
with no network call at audit time. It covers both ecosystems this tool reads,
and it carries **GHSA and CVE ids** — the identifier schemes `vexctl filter`
matches, unlike PyPI-native `PYSEC-` ids.

**256 MB is too large to commit**, and the policy anticipated that: "committed
**or pinned** like the corpus is". Pinning is the sanctioned branch, not a
workaround. Downloaded, gitignored, pinned by a committed manifest — and that
manifest copies `vex/manifest.json` **completely**: `schema_version`,
`document_count`, per-entry `upstream_url` / `snapshot_date` /
`document_digest`, and the **required** `note`, which `SCHEMAS.md:501` makes
required precisely so an empty file says why it is empty. Add `advisories/` to
`.gitignore`; no existing pattern covers it.

## Before starting: six things to settle

### 1. An advisory finding cannot be scored as currently shaped — decide the anchor

**This is the blocking one.** `grading.py:matches_key` joins on `file` equality
*and* a line window. A component-anchored finding has `file: None` and
`line: None` — `baselines/sbom_only.py` is the existing precedent — so **no
advisory finding can ever be a true positive** against a key entry with a real
path. Worse, on a key with `findings_complete: true`, `scorer.py:163` computes
`len(produced) - len(answered)`, so every one becomes a false positive **by
construction**. This is already measured: `TODO.md:587` records the SBOM-only
baseline reaching 0 of 6 while producing **187 false positives**, for exactly
this structural reason.

A4's "every number moves" would otherwise move them all in one direction, for a
reason that has nothing to do with detection quality.

**Recommendation — anchor the finding on the surface that reaches the
component**, which `mapping.json` already knows. This solves three problems at
once:

- The finding gets a real `file` and `line`, so it is scorable on the existing
  join with no change to `matches_key`.
- It bounds volume (item 2) without a cutoff invented after seeing the number.
- It is the claim worth making: "this vulnerable component is in the execute
  path of an LLM surface" is something no off-the-shelf scanner says, and it is
  precisely the evidence OpenVEX's `vulnerable_code_not_in_execute_path`
  justification wants.

**The mechanism, precisely, because the obvious shortcut is wrong.** A mapping
entry carries `surface_id` and `purl` — and `purl` is non-null **only** when
`reason == "third_party"`, so it is exactly the set of components reached by a
surface, and exactly the advisory join key. But an entry carries **no `file` and
no `line`**. Those live on the surface, so the check joins entry → surface for
them. Do **not** parse them out of `surface_id`: it is documented as an opaque
composite (`file:line:kind:name`) whose parts are each their own field
elsewhere, and splitting a string on `:` breaks on a Windows path or a colon in
a name.

`finding.py:_check_surface_copy` already enforces the rest: a finding that sets
`surface_id` **must** copy the surface's kind, name, file and line, with the
file a repo-relative POSIX path. So the anchoring works with no change to
`Finding`'s validation — the constraint is already the one this design needs.

Components with an advisory but **no reaching surface** are reported as a
**count with the evidence retained**, the way `unresolved_component_count`
already sits beside the findings — not as findings, and not silently dropped.

**One multiplication the plan must accept rather than dodge.** `mapping.json`
holds one entry *per surface*, so three surfaces importing `lodash` give three
entries with the same purl. Under `(surface, component, advisory)` granularity
that is 3 × 3 = **nine findings** for one package. The tempting fix — pick one
surface and report once — is barred by the project's own rule at
`SCHEMAS.md:440`: choosing among equally valid joins by sort order "would put a
guess in the advisory join key". So the multiplication stands, and it is
defensible (each is a real, distinct, individually scorable location), but it
means **the grading key needs an entry per location too**, and item 6's human
cost is higher than one entry per vulnerable package. Size that before
promising A4 a date.

**Accept the consequence, and state it in the write-up.** Under this design
`security-agent-testbed` — the repo that motivated the whole item — still
reports **zero findings**, because its `mapping.json` has `surface_count: 0`.
It is a Next.js app with no LLM surfaces, so nothing reaches any of its 528
components. That is the correct behaviour for an LLM-application auditor and it
is the honest demonstration of what this tool is *for*, but it must be said
out loud: the fix for "0 findings on a repo full of CVEs" is not that the
number goes up on that repo. It goes up on apps that actually call an LLM.

The alternative — giving `matches_key` a component-anchored branch — is a
change to the one join rule the whole evaluation rests on. If it is taken
instead, it goes through `schema-keeper` **before** A3 and is re-justified in
`PHASE_4_PLAN.md`, because it changes what scoring means.

### 2. Volume, which item 1 mostly answers

`Finding.id` is `f"{anchor}:{rule_id}"` and `findings_document.py:130-134` **raises**
on duplicates. `sbom_only.py:43-49` documents having already hit this wall:
"One finding per *name*, never per (name, version)". So:

- With `rule_id` a fixed check name and the anchor a component name, lodash's
  three advisories produce **three identical ids** and the document refuses
  them. The id scheme must change for this check regardless of item 3.
- Unbounded, 528 matchable components in a real npm tree plausibly emit several
  hundred findings into a document that today holds single digits — swamping the
  four LLM-specific risk classes, pushing the "what was not examined" section
  past where anyone scrolls, and letting one check dominate Phase 4's counts.

**Decide granularity explicitly: one finding per `(reaching surface, component,
advisory)`**, with the advisory id participating in `Finding.id`. Decide it
**before** the first run — choosing a cutoff once the number is known is how a
result gets tuned into existence.

### 3. Identifiers: `rule_id` stays a check name

I planned to make `rule_id` the advisory id. **That breaks a documented
invariant and two readers**, and the right place for the departure is elsewhere:

- `SCHEMAS.md:776` states `rule_id` is "Which check produced it. **Fixed
  vocabulary.**"
- `run_checks.py:22-33` keys `RISK_CLASS_BY_CHECK` on the check name and derives
  `risk_classes_checked` from `checks_run` at `:62`. `CHECK_NAMES` is
  `tuple(RISK_CLASS_BY_CHECK)`, so the check needs a fixed name and `rule_id`
  must stay it.
- `sarif.py:84-98` builds `tool.driver.rules[]` from `rule_id`, so an advisory
  id there produces one "rule" per CVE, contradicting that function's own
  documented purpose.
- `report.py:68` renders "**Reached by**: `{rule_id}`, static analysis" — which
  reads correctly for a check name and oddly for a CVE.

**So:** `rule_id` is the constant `known_advisory`. A **new `advisory_id`
field** carries the GHSA or CVE id, with `advisory_aliases` beside it.

**And that is a change to the `Finding` dataclass, not just a JSON key.**
`Finding` today has no advisory field of any kind, and
`findings_document.py:153` serialises with `asdict(f)` — so **every** finding in
**every** document gains `advisory_id` and `advisory_aliases`, null and empty on
the three existing checks. Consequences to plan for rather than discover: every
stored `corpus/evidence/<app>.baseline.json` regression snapshot changes, the
findings table in `SCHEMAS.md` gains two rows, and byte-identity against any
artifact generated before the change is broken by design. This is squarely
`schema-keeper`'s job and it belongs at the **start** of A3.

The
`ruleId`-as-advisory-id departure belongs in **SARIF only**, mapped in
`sarif.py:_result`, because `SCHEMAS.md:862-864` already documents the SARIF
file as a derived copy — a copy is the right place to speak another tool's
dialect. Route all of this through `schema-keeper` in **A3**.

### 4. Severity — and the stated ground is narrower than I first wrote

Two different refusals are on the books, and the plan must amend the right one.
`SCHEMAS.md:809-810` excludes `severity` from what **the model** may write,
because it has "no field in the grading key … an unfalsifiable number that would
nonetheless be quoted". But `SCHEMAS.md:890-894` is a flat **project-level**
refusal asserted about deterministic code: "This project reports no severity —
nothing in a grading key could check one."

Carrying a CVSS vector is in tension with **:890-894**, not with :809. That is
the text to amend or exempt, and pretending otherwise would be quoting the
convenient sentence.

**Recommendation: carry it as cited evidence, not as a finding field.** The
stated ground is *unfalsifiability*, and a vector copied from an OSV record is
falsifiable by construction — a reader opens the advisory and checks it. So put
it in the finding's evidence beside the advisory id and the matched range, where
it is attributed and reads as a quotation. Do **not** add a `severity` field to
`Finding`, do not sort or rank by it, and do not let it set SARIF `level` —
that stays the constant `warning`. Write the reasoning into `SCHEMAS.md:890-894`
in the same change.

### 5. Version ordering is a dependency decision, and it is where this will be wrong

`requirements.txt` has no `packaging` and no semver library, and the project is
stdlib-first with one standing exception (the JS parser). Correct PEP 440 and
SEMVER precedence — prereleases, build metadata, `4.17.9` vs `4.17.10` — is
genuinely hard, and hand-writing it is where this check will quietly be wrong in
the tool's favour.

**Settle it before A2 and write the answer down.** `packaging` is the reference
implementation of PEP 440; a hand-rolled comparator is a second implementation
of a spec this project does not own. That is the same argument that made
`vexctl` the right call for `filter`.

### 6. Grading keys need a human, and the testbed is not one

A new check with no key entry scores nothing. Either the existing keys gain
LLM03 entries for their vulnerable components, or a fixture is adopted with a
key of its own. Both need `verified_by`, and neither may be drafted from the
auditor's own output — a key derived from the tool makes precision 100% by
construction.

**`security-agent-testbed` is matcher-validation data, not a scored fixture.**
Measured: its `mapping.json` has `surface_count: 0` and `mapped_count: 0`. With
no LLM surfaces it can validate the **matcher** — does `lodash@4.17.19` resolve
to the right advisories — and nothing above it, because the check itself would
never fire. Making the headline supply-chain evaluation rest on it is exactly
the "quietly become a vulnerability scanner" outcome this plan warns against. `PHASE_4_PLAN.md:542` also requires corpus
growth to happen *before* a measurement, with the reason recorded. If it is ever
adopted as scored, that is its own TODO line under Phase 3/4 fixtures.

### And one ordering constraint, not a decision

**This changes what the auditor detects, so it cannot land mid-measurement.**
`PHASE_4_PLAN.md:19-24` is explicit that a detector must not change during a
measurement. The order is: land the check, then re-run the whole evaluation and
report before and after. The **write-up must not be drafted across the change** —
`TODO.md:627` (thesis report) and `:694` (stale `report.docx`) are open, so
either close the write-up against the pre-advisory run first, or write it
against the post-advisory run. Not both.

## ~~Task A1 — Ingest a pinned advisory snapshot~~ — superseded by the Trivy runner

**Built as `src/deps/trivy_runner.py`**, mirroring `syft_runner.py`: offline by
six explicit flags, pinned by the database's own `UpdatedAt` in
`coverage.advisory_*` (no manifest file — the pin lives in the artifact that
used it, the way `sbom.json` pins Syft), degrading to `not_ingested` when the
binary or its database is absent. The original OSV task is kept below as the
record of the alternative.

## The recorded alternative, task by task

### Task A1 — Ingest a pinned advisory snapshot

**Do:**

- `src/deps/advisories.py`, the home `TODO.md:197` already names. It reads a
  snapshot from disk and answers "what does OSV hold for this purl" — **nothing
  else**, and it makes no network call. Range evaluation is A2's module.
- The out-of-band download step, documented, plus `advisories/manifest.json` in
  the full `vex/manifest.json` shape described above, and the `.gitignore` entry.
- **The value itself needs no schema change** — `findings_document.py:32`
  already defines `ADVISORY_SNAPSHOT = "snapshot"` and validates it
  (`:105-106`), with a passing test. It has simply never been emitted. What
  `schema-keeper` settles here is what surrounds it: the snapshot date in
  `coverage`, and the fact that `scorer.py:80` **drops the
  `advisory_data_not_ingested` qualification** the moment this flips.
- Fail clearly when the snapshot is absent: `advisory_data` stays
  `not_ingested`, the check is absent from `checks_run`, and the audit does not
  fail. Missing advisory data is a normal outcome, as a missing Syft is.

**Done when:** a real snapshot is read, a purl at an exact version returns its
records, an absent snapshot degrades rather than fails, a test asserts the
reader makes no network call, and an end-to-end test asserts the qualification
actually disappears when a snapshot is present.

### ~~Task A2 — Match versions honestly~~ — deleted by the Trivy decision

The matcher below — four event types, two ordering schemes, alias collapsing —
is exactly what Trivy maintains, and re-implementing it was where this project
would quietly have been wrong. Nothing of it was written. Kept as the record of
what the decision avoided.

### Task A2 — Match versions honestly (as originally planned)

The matcher is the part that can quietly be wrong, so it is its own task and its
own module: **`src/deps/version_ranges.py`** for ordering and range evaluation.
Existing `src/deps/` modules run 51–98 lines, and OSV semantics plus two
ordering schemes will not fit beside the snapshot reader inside rule 18's 200.

**Do:**

- **Four event types, not two** — `introduced`, `fixed`, `last_affected` and
  `limit`. Real lodash records use `last_affected`, an **inclusive** upper bound
  where `fixed` is exclusive, so a matcher written for `fixed` alone is wrong by
  one version on every range using the other. Verified on live data, not
  hypothetical.
- Both npm SEMVER and PyPI ordering, per item 5's dependency decision.
- **Refuse to match anything not `pinned` or `locked`.** A version inferred from
  a range is barred from the PURL by design; asserting against `~=0.3.25` would
  claim a vulnerability the app may not have. Coverage per fixture is recorded
  at `SCHEMAS.md:475-485` and is not restated here.
- Prove it on real data, verified 2026-09-01: `lodash@4.17.19` matches
  `GHSA-35jh-r3h4-6jhm` (`introduced: 0`, `fixed: 4.17.21`); `lodash@4.17.21`
  does not.
- Boundary tests are the point: the `introduced` version matches, the `fixed`
  version does not, the `last_affected` version **does**, and a prerelease
  either side is decided deliberately rather than by accident.

### Aliases, and why they inflate the count

OSV returns **5 records for `lodash@4.17.19`, but only 3 distinct
vulnerabilities.** `GHSA-35jh-r3h4-6jhm` and `GHSA-r5fr-rjxr-66jc` list each
other as aliases and are both CVE-2021-23337; `GHSA-f23m-r3pf-42rh` and
`GHSA-xxjr-mmjv-4gpg` are both CVE-2025-13465. Uncollapsed, that is **five
findings where three are true** — 67% inflation, in the LLM03 count Phase 4
measures, in the tool's own favour.

Two sub-problems:

- **Which id survives**, and `SCHEMAS.md:440` already rules out the easy answer:
  when a join is ambiguous, "naming one by sort order would put a guess in the
  advisory join key". Prefer the **CVE alias** as canonical where one exists —
  both records agree on it, it is stable, and `vexctl filter` matches the `CVE-`
  scheme. Keep every GHSA id in `advisory_aliases` so nothing is lost.
- **The aliases disagree about the range.** `GHSA-35jh` says `fixed: 4.17.21`;
  its own alias `GHSA-r5fr` says `fixed: 4.18.0` for the same CVE. Collapsing
  means choosing, and the honest choice is the **widest affected range** —
  under-reporting is the worse error — with both cited so a reader sees the
  sources disagreed.

**Done when:** all four event types are handled with boundaries tested in both
directions on real records, aliases collapse to a canonical id by written rule
rather than sort order, `lodash@4.17.19` yields **3** rather than 5, and an
unpinned component is reported unassessed rather than matched or cleared.

## Task A3 — The check

**Do:**

- A new check named `known_advisory`, distinct from `undeclared_dependency`.
  That one is a *hygiene* rule — used but never declared — and would not fire on
  `lodash@4.17.19`, which is declared, pinned and honestly recorded. Confirmed
  on real data: the testbed's `findings.json` has `finding_count: 0` with
  `undeclared_dependency` in `checks_run`.
- Register it in `RISK_CLASS_BY_CHECK` so `risk_classes_checked` stays derived
  from what ran.
- Anchor per item 1, granularity per item 2, identifiers per item 3 — all
  through `schema-keeper` **before** any writer exists.
- Cite evidence a reader can check: purl, advisory id, aliases, the range that
  matched, and the snapshot date. Severity only as item 4 allows, attributed.
- Report advisory-carrying components with **no reaching surface** as a count
  beside the findings.

**Done when:** the check fires on real advisory data, findings carry
`advisory_id` and are scorable on the existing join, and the unreached count is
reported rather than implied.

## Task A4 — Re-measure, and report the delta

**Blocked on Task 3.8a** (see Precondition). When the fixtures are back: re-run
the whole Phase 4 evaluation with the new check present and report before and
after side by side. The movement is the result — the first evidence this project
will have about what advisory data is worth.

**Done when:** the comparison is in the write-up, and `PHASE_4_PLAN.md`'s tables
say which run they describe.

## Exit checklist — as completed under the Trivy decision

Items about the OSV snapshot, the hand-written matcher and alias collapsing are
struck: they name work the reversal deleted, and ticking them would claim it.

- [x] No network call at audit time: every Trivy network switch is off by flag,
      asserted by value in `tests/test_advisory_launch.py`.
- [x] The data is pinned — generator name, version, database `UpdatedAt` — in
      `coverage`, validated in both directions so a snapshot cannot carry a
      null pin.
- [x] Only exact versions match, by construction: Trivy matches lockfile and
      `==`-pinned versions, measured as 0 findings on the unpinned Python
      fixture.
- [x] ~~Four OSV event types / alias collapsing~~ — deleted with the matcher.
- [x] The anchor decision held: findings anchor on the reaching surface, carry
      `file`/`line`, and score on the existing join unchanged.
- [x] `rule_id` stays the fixed name `known_advisory`; `advisory_id` is a new
      field; the advisory-id-as-`ruleId` departure exists only in SARIF.
- [x] The reached/unreached split was decided before the first run; unreached
      components are a counted coverage field, never dropped.
- [x] Severity: the CVSS **vector** is carried as an attributed quotation;
      ~~the severity word is refused~~ *(reversed at schema v6: the word is carried, attributed to its source)*; `SCHEMAS.md` amended in the same change.
- [x] ~~Version-ordering dependency decision~~ — mooted; no comparator was
      written and `requirements.txt` gained nothing.
- [x] `advisory_data: "snapshot"` is emitted, with the schema-keeper-ratified
      coverage fields beside it; `SCHEMA_VERSION` bumped 3 → 4.
- [x] `tests/cli/test_main_findings.py`'s checks_run assertion updated; the
      four-check case is asserted with stubbed advisory data.
- [x] `Finding.id` uniqueness for one component with several advisories: the id
      gains the advisory suffix, tested.
- [ ] Grading keys carry entries for the new check, human-verified — **half
      done**: `STARTER-01` is drafted (a component-named reachability entry,
      so it does not rot with the database) and both advisory findings answer
      it with zero false positives, but the key's `verified` flag is reset and
      the scorer says `key_unverified` until a human re-checks it. The human
      half is the open half.
- [x] Task A4, the re-measure — run, and the delta recorded in the README's
      headline section: recall unchanged at 2 of 6, clean-app false positives
      0 → 2, both of them true CVE findings the key does not grade yet. The
      thesis write-up of that delta is Phase 4's open writing task, not this
      plan's.
- [x] Tests pass (1844); project-guard's second pass ran, failed on seven
      stale-document items, and passed on the confirmation after each fix.
- [x] `TODO.md` ticked in the same change as the work.

## The original exit checklist (superseded)

- [ ] Task 3.8a done; the corpus fixtures are on disk before A4 is attempted.
- [ ] No network call at audit time; the reader is proved offline by a test.
- [ ] The snapshot is pinned by URL, date and digest in the full
      `vex/manifest.json` shape including the required `note`, and
      `advisories/` is gitignored.
- [ ] Only `pinned` and `locked` versions are matched; everything else is
      reported unassessed, never clean.
- [ ] All four OSV event types handled, with boundaries tested both directions
      against real records.
- [ ] Aliases collapse by written rule, not sort order; `lodash@4.17.19` yields
      3 findings.
- [ ] The anchor decision (item 1) was made before A3 and, if `matches_key`
      changed, `schema-keeper` and `PHASE_4_PLAN.md` were updated with it.
- [ ] `rule_id` is still a fixed check name; `advisory_id` is a new field; the
      advisory-id-as-`ruleId` departure exists only in SARIF.
- [ ] The two new `Finding` fields went through `schema-keeper` first, and
      every `corpus/evidence/*.baseline.json` was regenerated for them.
- [ ] The grading keys carry one entry per (surface, component, advisory)
      location, not one per vulnerable package.
- [ ] The reached/unreached split was decided **before** the first run, and
      unreached components are counted rather than dropped.
- [ ] The severity decision is written into `SCHEMAS.md:890-894` with its
      reason, whichever way it went.
- [ ] The version-ordering dependency decision is recorded in
      `requirements.txt` with its reason.
- [ ] `advisory_data: "snapshot"` is emitted, and an end-to-end test asserts
      `advisory_data_not_ingested` disappears from the scorer's qualifications.
- [ ] `tests/cli/test_main_findings.py:96` — which asserts `checks_run` equality
      against `CHECK_NAMES` — is updated for the fourth check.
- [ ] A test covers `Finding.id` uniqueness for one component with several
      advisories.
- [ ] Grading keys carry entries for the new check, human-verified (STARTER-01
      drafted; verification pending), and the
      testbed's role as matcher-validation data is stated rather than assumed.
- [ ] Phase 4 re-run, the before/after delta reported, and the write-up not
      drafted across the change.
- [ ] Tests pass; `project-guard` clean on the finished code.
- [x] `TODO.md` ticked in the same change as the work.

## What this unblocks

- **The first of Task 5.3's three blockers.** `PHASE_5_PLAN.md:166-170` lists
  three: the rule-id scheme, that only LLM03 of five risk classes is VEX-shaped,
  and that no upstream VEX document exists for any dependency of any fixture.
  Advisory ingestion clears **only the first**. *(Since closed: 5.3 was later
  declared out of scope on the other two, which are not this project's to fix —
  see TODO 5.3.)*
- **Emitting VEX rather than consuming it**, which is where this project has
  something to contribute and which answers blocker three by authoring the
  documents that do not exist upstream. `mapping.json` already knows whether a
  component is reached by an LLM surface — the evidence
  `vulnerable_code_not_in_execute_path` requires and most VEX tooling has to
  guess at.
- **The one real answer to "so what"** for the SBOM/AIBOM half of the project.
  Today LLM03 reports a hygiene failure; with advisories it reports risk.

## Notes and honest cautions

**A snapshot is out of date the day after it is taken**, and that is a feature:
it is reproducible, which is what an evaluation needs. The write-up must state
the snapshot date beside any number derived from it, and must not imply the tool
knows about anything published since.

**This is the largest dependency this project would take on.** 256 MB of data,
downloaded out-of-band, that every supply-chain number then rests on. The
manifest and the digest are what keep that honest — without them, "we matched
against OSV" is a claim with no date and no version behind it.

**Do not let the check quietly become a vulnerability scanner.** This is an
LLM-application auditor, and LLM03 is one of five risk classes. Grype and Trivy
do dependency scanning better and are not trying to do anything else. What this
project can say that they cannot is whether a vulnerable component is *reached
by an LLM surface* — the mapping join, not the advisory match. Settle-first
items 1 and 2 are where that stops being a sentiment and becomes a design
decision.

**The comparison to make, and the one to avoid.** Trivy already answers "which
packages have known CVEs" better than this project will, and 311 against 0 is
not a result to argue with -- it is a statement of scope. The defensible claim
is the join: of the vulnerable components in an app that *does* call an LLM, how
many are reached by a surface. Report that, with its denominator, and the
scanner comparison becomes evidence for the project rather than against it.

**The honest risk to the thesis.** Advisory ingestion is the item most likely to
make the tool *look* dramatically better while saying less. Going from 0 to
several hundred findings on `security-agent-testbed` is a screenshot, not a
result — and most of those findings would re-report what `npm audit` prints in
two seconds. The number worth reporting is not how many advisories were found;
it is how many reach an LLM surface, and whether the four LLM-specific classes
are still found at the rate Phase 4 measured. Frame the write-up that way from
the start, because the other framing is much easier to fall into once the
numbers exist.

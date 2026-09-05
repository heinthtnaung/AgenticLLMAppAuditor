# Phase 3 — LangGraph auditor, probes & reporting

**Goal:** answer "is this surface actually exploitable, and what is the
evidence?" — by planning probes over the surfaces Phase 1 found and the
components Phase 2 joined them to, then reporting each conclusion with the
evidence that produced it.

**Input:** `artifacts/<app>/surfaces.json`, `mapping.json`, `aibom.json`,
`sbom.json` from Phases 1 and 2.
**Output:** `artifacts/<app>/findings.json`, plus a human-readable report.

**Scope rule:** Phase 3 is where the local model is finally used. **It does not
execute the audited app.** Probing here is static: the auditor reads code and
artifacts, and never runs someone else's program. The safety boundary in
`.claude/AGENTS.md` is met by not crossing it at all, which is a stronger
position than a weak sandbox and an honest one to defend.

The corpus is what forces that, not caution alone. Every finding in the grading
keys carries `detection` of `static` or `either` -- **not one is `probe`** -- so
a dynamic probe would earn no recall the static path cannot. And the vulnerable
app's `llm-config.yaml` defaults to `gpt-4-1106-preview` through LiteLLM, so
running it would call OpenAI and break the offline guarantee; repointing it at
Ollama would make any observed injection a fact about
`qwen2.5-coder:7b-instruct` rather than about the audited app.

**What Phase 3 is not.** Precision and recall numbers, baselines and the
comparison against them are Phase 4. This phase produces findings; it does not
score them.

## Coding rules

The 20 binding rules in [`CODING_RULES.md`](./CODING_RULES.md) apply unchanged.
Two bite harder here than in earlier phases:

- **Rule 8, fail clearly.** A probe that cannot reach a conclusion must say so.
  "No finding" and "could not test" are different results, and collapsing them
  is how a report claims a clean bill it never earned — the same failure
  `surfaces.json`'s `skipped_files` and `mapping.json`'s `unresolved` reason
  exist to prevent in Phases 1 and 2.
- **Rule 15, do not widen scope.** The model is a *reasoner over evidence this
  project gathered*, not a second detector. If a finding cannot be traced to a
  surface, a component or a probe result, it does not go in `findings.json`.

## Before starting: four things to settle

**1. What the model is allowed to decide.** The auditor is offline and
human-in-the-loop, and its findings are graded against a hand-written key in
Phase 4. So the model may explain, rank and correlate; it may not invent a
finding with no artifact behind it. Every finding carries the surface id,
component or probe result it came from, or it is not written.

**2. Determinism, which the model breaks.** Every artifact so far is
byte-identical across runs, and a language model is not. `findings.json` cannot
inherit that guarantee as-is. Decide before writing it: which fields are
deterministic (the evidence: surface ids, purls, probe outcomes) and which are
model-authored (the prose), and record the model and settings used so a run can
be repeated rather than reproduced byte for byte.

**3. That nothing executes, written down as a non-goal.** The corpus apps are
downloaded third-party code, and their dependencies are deliberately not
installed (`.claude/AGENTS.md` forbids putting them in `.venv`). Running one
would need those packages fetched from PyPI, which is a second breach of the
offline rule on top of the hosted model. So the boundary is: the auditor reads,
it does not run. A test asserts no code path writes inside `corpus/`.

**4. LLM03 has no advisory evidence.** Advisory ingestion is the one unticked
item on Phase 2's exit checklist. `VULN1-06` is graded this phase, so
`findings.json` says so in `coverage.advisory_data`, whose value is
`not_ingested` until that work lands. The absence is stated rather than left to
be read as "nothing known". `VULN1-06` itself needs no advisory: it is evidenced
entirely by `mapping.json`'s `used_but_undeclared`.

## Task 3.1 — Human-in-the-loop, asserted

Ticks `TODO.md`'s "Confirm human-in-the-loop only (no auto-patch, no PR merge)".

**Do:**

- Assert it in a test rather than a docstring: no code path writes to the
  audited repository, commits, or opens a pull request.
- State the non-execution decision where a reader meets it, not only here.

**Done when:** a test fails if any code path writes inside `corpus/`, and the
offline test covers the new modules.

## Task 3.2 — `findings.json`

**Do:**

- `schema-keeper` defines the schema before anything writes it (rule 10).
- Each finding cites its evidence: a surface id, and where relevant a component
  purl. A finding with no evidence is not representable.
- Carry the **negative** evidence too, so Task 3.7 has something to report:
  files the scan skipped, components never checked against advisories, and
  traces static analysis could not follow. A short findings list must not read
  as a clean bill.
- Carry the model identifier, its digest and the decode settings, so a run can
  be repeated.
- **Amend the determinism convention in the same change.** `SCHEMAS.md` states
  byte-identical output as a global rule and `REPORT.md` repeats it to the
  examiner. Model-authored prose breaks it, so both documents must name the
  exception and bound it: evidence fields stay byte-identical and stay under the
  baseline comparison; prose is excluded and pinned by temperature 0 and a fixed
  seed instead.

**Done when:** the corpus app's known findings can be expressed in the schema, a
finding without evidence cannot be constructed, and a test asserts the prose
fields are excluded from the byte-identical comparison.

## Task 3.3 — Probe: static permission checks

The safest probe and the one to build first: it executes nothing.

**Do:**

- Write the over-privilege rule **before** the code, so it is visible rather
  than fitted to one fixture: a tool surface is over-privileged when it holds a
  write mode or a network capability that its own declared purpose does not
  need. `open()`'s mode is already reported by the extractor, and
  `HIGH_PRIVILEGE_TOOLS` already names the shell and file tools.
- Report each one with the surface id that produced it.

**Done when:** the corpus app's high-privilege tool surfaces are reported with
their surface ids, and the rule is written down where a reader meets the code.
Note there is one graded LLM06 finding, so this is demonstrated, not measured.

## Task 3.4 — Probe: taint-style dataflow tracing

**Do:**

- Trace an untrusted source to a prompt or a tool argument, within one file to
  begin with, and say plainly when a trace leaves what static analysis can
  follow.
- This is what makes narrowing `DATA_SOURCE_METHODS` possible on both language
  sides: `load`, `query` and `execute` match any receiver today, and knowing the
  receiver's type is what tells a document loader from an unrelated `.load()`.

Keep "within one file" as a **hard limit**, not a starting point: tracing across
files and then across the package boundary is an unbounded research problem.

**Done when:** a source reaching a prompt is reported with both ends cited, and
an untraceable path is reported as untraceable rather than dropped.

---

## Task 3.4b — Narrow the bare data-source method names

Ticks `TODO.md`'s `load` / `query` / `execute` breadth line, which moved here
from Phase 2 because it needs what 3.4 builds.

**Do:**

- Use the receiver binding from 3.4 to tell a document loader's `.load()` from
  any other object's. The same binding is what would give a JS route surface its
  `module`, where `app` is a local bound to `express()`.

**Done when:** a `.load()` on an unrelated receiver stops being reported, no
corpus surface is lost, and the change is measured on both fixtures rather than
asserted.

## Task 3.5 — ~~Probe: benign injection~~ — deferred, with the reason

**Not built in Phase 3.** Three facts decide it, each checked rather than
assumed:

- **It would be graded by nothing.** Every finding in both grading keys carries
  `detection` of `static` or `either`; not one is `probe`. A dynamic probe earns
  no recall the static path cannot already reach.
- **It cannot run offline.** The vulnerable app's `llm-config.yaml` defaults to
  `gpt-4-1106-preview` through LiteLLM, so running it calls OpenAI.
- **Repointing it would change the subject.** Aimed at Ollama, an observed
  injection is a fact about `qwen2.5-coder:7b-instruct`, not about the audited
  app, so the finding would not be about the corpus at all.

Revisit in Phase 4 if the corpus gains an app with `detection: "probe"` findings
and a locally servable model. Recorded in `TODO.md` under Phase 4.

---

## Task 3.6 — The agentic audit workflow

**Do:**

- **Decide the dependency explicitly.** A planner plus a bounded loop with a
  step cap is about sixty lines of plain Python. `requirements.txt` holds four
  packages and the project's rule is stdlib-first with one standing exception.
  So if LangGraph goes in, it is because the thesis argues the auditor is itself
  an agentic LLM app and should be built like one — not because the loop needs
  a framework. Write whichever reason applies.
- Shared state, a planner node, a bounded loop with a step cap. Moved here from
  Phase 1, where it duplicated this line.
- The planner picks the next probe over that state — and only that. A planner
  that decides *what counts as a finding* is the second detector this plan's
  scope rule forbids.
  (As built, the pick was `remaining[0]` in `act` rather than in the planner at
  all; Phase 7 moved it into `plan`, and task 7.4 lets a model choose which
  surfaces each check examines. The second sentence stands unchanged: the
  planner still decides nothing about *what counts as* a finding, and every
  narrowing is recorded in `coverage.checks_narrowed`.)

**Done when:** the auditor plans and runs probes over one app within its step
cap, and the plan is recorded in the findings so a reader can see why each
probe ran.

## Task 3.7 — Evidence-backed reporting

**Do:**

- `findings.json` plus a human-readable report. Each finding shows its OWASP id,
  the code location, the LLM surface it came from, and its SBOM/AIBOM or probe
  evidence.
- The report states what was *not* tested as prominently as what was: skipped
  files, unchecked components, untraceable paths — all carried in the schema by
  3.2, so the report renders them rather than recomputing them.
- **No scoring.** No precision, recall, percentage, TP/FP/FN or "detected N of
  M" appears in `findings.json` or the report. The report lists findings and
  gaps; Phase 4 scores them. List lengths like `finding_count` are not scoring
  and stay, following `surface_count` and `component_count`. This is the task
  most likely to drift into Phase 4 and this line is the fence.
- The report is a **rendering** of `findings.json` with no contract of its own.
  A second producer of the same facts is what `target.json` was declined for.

**Done when:** a reader can go from a line in the report to the artifact and the
source line that produced it, without asking the tool anything.

## Task 3.8a — Restore corpus fixtures from their pinned manifests

The half of the roadmap line that protects the grading keys: nothing today
checks that a downloaded fixture is still at the commit its manifest names, so
an upstream move silently rots every line number in both keys.

**Do:**

- Verify `git rev-parse HEAD` against `manifest.upstream_commit`, and restore a
  fixture to its pin from the manifest alone.

**Done when:** a fixture checked out at the wrong commit is reported as such
rather than audited quietly.

---

## Task 3.8b — Audit a repository from a URL

Built during Phase 1 and removed to keep it offline and simple. Bringing it back
means bringing back the safety work an untrusted input needs: an https/git@
allow-list, a validated directory name, a size cap, and a refusal to follow
symlinks out of the target. ~~The code is on the `phase3/url-fetcher` tag.~~
**That tag does not exist** -- searched local tags, `origin`, and reachable
history. See `TODO.md`'s corrected entry: this is a rewrite. Planned as Phase 5
Task 5.1.

It serves no Phase 3 finding — it enlarges the corpus, which is a Phase 4 need.
Move it to Phase 4 if the phase runs long.

**Done when:** a URL fetch refuses every input on the allow-list's wrong side,
proved by a test per refusal, before it is wired into the CLI.

## Phase 3 exit checklist

- [x] The auditor never executes the audited app; a test proves no code path
      writes inside `corpus/`.
- [x] No code path commits or merges the audited repository.
- [x] `findings.json` schema defined by `schema-keeper` before its writer.
- [x] Every finding cites the evidence that produced it.
- [x] Probes report "could not test" distinctly from "nothing found".
- [x] The model's contribution is bounded, recorded, and never the sole basis
      for a finding. **Now exercised against a live server**, which it had not
      been: `src/checks/advise.py` asks the local model to advise on every
      finding and records the answer in `remediation.json`, with
      `model_run.status: "used"` naming the model, its digest and the settings
      sent. The bound is structural rather than promised -- the advice lands in
      a file the scorer cannot open, so `findings.json` is byte-identical
      whether the model ran or not and no model word reaches a number. An
      answer that names the app's own identifiers, arrives as a diff or
      re-classifies the finding is refused whole and the refusal recorded.
- [x] Report states what was not tested alongside what was. `src/report.py`
      gives skipped files, unfollowed traces, unresolved components and
      uncovered risk classes the same billing as the findings.
- [x] Tests pass; `project-guard` clean on the finished code. 1037 at the time
      this phase closed; the remediation advice added later took it higher. The guard's
      second pass on the report and the scope fix found a real regression --
      per-scope bindings matched against a module-wide walk, a false-positive
      class the old code did not have -- which is fixed and now has the
      cross-scope test whose absence let it land.
- [x] `TODO.md` ticked in the same change as the work.

**Artifacts produced this phase:** `artifacts/<app>/findings.json` and the
report — consumed by Phase 4's scorer. Field lists go in
[`SCHEMAS.md`](./SCHEMAS.md).

## Notes and honest cautions

- **The corpus grades this phase, and it bounds it.** One deliberately
  vulnerable app with six findings, one clean app with none. That is enough to
  demonstrate evidence-backed reporting and enough to embarrass a false
  positive; it is not enough to justify a probe class no key entry requires.
- **No false-positive claim is available this phase.** The clean fixture is the
  only measurement, and its key is `verified: true` with `verified_by` null, so
  any FP statement about `findings.json` would be unbacked until B3 closes.
- **LLM03 findings have no advisory evidence yet.** Advisory ingestion is the
  one unticked item on Phase 2's exit checklist, so a supply-chain finding this
  phase can cite the SBOM but not what is known to be wrong with a component.
- **Nothing here executes the audited app**, so the phase never needs a sandbox
  to be trusted. That is a deliberate position, recorded in the scope rule, not
  an omission.

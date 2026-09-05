# Phase 7 — an LLM in the planner, and a probe that does not overclaim

Two features the proposal promised and the code does not have: an
`auditor_planner` that uses the local model to decide what the audit does, and
a `probe_injection` stage that tests prompt templates. This plan is written
**before** the code, because `docs/PHASE_4_PLAN.md` records being the one phase
built before its plan and calls that a defect. Not repeating it.

## The sentence that is already false

`docs/FLOW.md:266` publishes:

> **The planner chooses which check runs, and nothing else.**

`src/checks/workflow.py` does not do this. `plan()` is
`{"steps": state["steps"] + 1}` and `act()` takes `remaining[0]`. The order is
fixed by `run_checks._checks_that_examined_something` before the graph starts,
and the graph walks it. **The planner decides nothing today.**

So this phase is not bolting agency onto a working planner.

**A correction, because the first draft of this plan overclaimed here.** I wrote
that task 7.0 "makes a published sentence true for the first time". It does not.
After 7.0 the planner still decides nothing: `choose_next` returns
`remaining[0]`, the order is fixed before the graph starts, and every eligible
check runs regardless. What moved was the *location* of a constant rule, not the
existence of a decision. `project-guard` caught it -- the same class of error as
titling the LLM02 check "model output reaches a database".

And the published sentence itself was wrong in the direction this phase forbids:
"chooses **which check** runs" implies the power to subtract. It now reads
"chooses the **order** the checks run in -- never which ones run". Task 7.0 is
therefore two things: move the pick into the planner node, and correct the two
sentences that described a planner nobody had built. Both are done, and both
were worth doing with no model at all.

## The line this phase must not cross

The same two documents that promise a planner also fence it:

> "What counts as a finding stays with the checks, which read evidence and cite
> it. A planner that decided findings would be a second detector, and Phase 4
> grades the detectors." — `docs/FLOW.md:266`

> "The planner picks the next probe over that state — and only that. A planner
> that decides *what counts as a finding* is the second detector this plan's
> scope rule forbids." — `docs/PHASE_3_PLAN.md:192`

> **OVERTURNED 2026-09-05 for task 7.4, by the project owner, on the proposal's
> authority.** The rejection below governed tasks 7.0-7.3 and is why
> `merge_monotonically` exists; it is annotated rather than deleted because it
> is the reasoning behind code that still ships. The proposal specifies
> "`auditor_planner`: uses a local LLM and deterministic risk heuristics to
> **choose the next surface and probe**", which an order-only planner does not
> do. Reason 1 below was answered rather than waived: `findings.json` gained a
> top-level `checks_narrowed`, so a narrowed check is no longer indistinguishable
> from a complete one and the `checks_run` contract is not quietly widened.
> Reasons 2 and 3 stand and are the price paid. See `docs/TODO.md` task 7.4.

The feature as originally specified said static checks should "only process the
surfaces that the LLM planner explicitly marked for them". **That was rejected
for 7.0-7.3, and overturned for 7.4**, for three reasons, the first of which is
a contract and not an opinion:

1. `docs/SCHEMAS.md`'s `checks_run` row enumerates exactly three causes for a
   check's absence and closes: "The scorer reads that absence as
   `no_check_for_risk_class`, so it is a claim, not a detail."
   `src/evaluation/scorer.py:56` does exactly that. A model declining to mark a
   surface would be a fourth cause the contract does not admit — a recall loss
   wearing coverage vocabulary.
2. It makes Phase 4 unreproducible.
3. It contradicts the feature's own stated goal, "keeping the actual checks
   deterministic".

**The rule this phase adopts instead: the planner may ADD and ORDER, never
SUBTRACT.** Its influence on findings is monotone — it can only cause more work
to happen, never less. That is real agency (it decides where the probe budget
under `MAX_STEPS` goes) with no path to a suppressed finding.

## Where the model call goes, and why it is not a preference

`tests/parsing/test_offline.py:126` asserts `no_network.attempts == []` after
`workflow.audit(...)` under a refusing socket. It counts **attempts, not
successes**, so a model call inside a graph node fails it *even when the model
is absent and the code degrades correctly*.

`workflow.audit` already takes `plan_order: list[str]`. So: the model is
consulted at the edge, in `run_checks.build_findings`, and its answer is passed
in as `plan_order`. The graph stays pure and the offline guarantee is untouched.
Rule 9 (I/O at the edges) says the same thing independently.

## Determinism: segregate, do not qualify

`README.md:44` and `:512` publish that `findings.json` is byte-identical whether
the model ran or not. That claim currently holds **structurally, not by test** —
`run_checks.py:73` hardcodes `model_run(MODEL_DISABLED)`, and
`tests/artifacts/test_determinism.py` compares two model-off runs. Nothing in
the suite compares model-on to model-off.

`findings_document.strip_model_authored` removes two fields
(`model_run.ranking`, each finding's `narrative`). **It cannot strip a record**,
so a model-authored finding would pass through it silently — no refusal, no
trace.

Therefore probe results go in **their own artifact**, not in `findings.json`.
Two precedents: `remediation.json` is a file the scorer cannot open, and
`coverage.advisory_unreached_components` was deliberately kept out of the scored
findings list so `evaluation.json` stayed byte-unchanged.

**The honest cost, stated rather than discovered:** segregated, the probe
reaches no OWASP score. It is descriptive evidence in the report, not a scored
finding. That is the price of not breaking the guarantee, and it is the right
trade — but it means this phase does not improve the published 2-of-6.

## Answering the three reasons this work was parked

`docs/TODO.md` parked the probe with three reasons. Reviving it requires
answering them, not stepping over them (rule 15).

1. *"Every finding in both grading keys carries `detection` of `static` or
   `either` and not one is `probe`, so it would add no recall the static path
   cannot reach."* — **Accepted, not refuted.** The grading keys went with the
   corpus, so this cannot even be re-measured. The probe is therefore built as
   unscored and segregated, which concedes the point rather than arguing it.
2. *"The vulnerable fixture defaults to `gpt-4-1106-preview` through LiteLLM, so
   running it breaks the offline guarantee."* — **No longer applies.** This
   probe never runs the audited app. It reads prompt-template source and asks
   the local model about its structure. The auditor's "never execute the audited
   app" boundary is untouched.
3. *"Aimed at Ollama instead, an observed injection becomes a fact about
   `qwen2.5-coder:7b-instruct` rather than about the audited app."* — **Still
   true, and fatal to the original framing.** It is why this phase does not
   claim to test injection. See below.

## Naming: what the probe may and may not claim

The original specification called for an "Attacker Agent" and a "semantic
sandbox" that decides whether a template "can be hijacked". A sandbox that runs
nothing is not a sandbox, and reason 3 above is exactly why: a model's opinion
about a payload is a fact about that model.

What the check can honestly establish is a property of the **template's
structure**: whether it interpolates untrusted input without delimiters and
without instruction/data separation. That is a real, useful, LLM01 finding.

- rule id: `prompt_template_lacks_delimiters`
- `owasp_id`: `LLM01` — the risk class is right; only the evidence strength must
  not be overstated
- the title asserts structure, never a demonstrated hijack

This is the same correction the LLM02 check took: `output_handling.py` says
"Database query built by string interpolation, not parameterised" rather than
"model output reaches a database".

## Tasks

- [ ] **7.0 — make `plan()` real, with no model.** The planner selects the next
      check from `remaining` rather than the graph walking a fixed list, and the
      decision is recorded. Correct `docs/FLOW.md:266` and
      `docs/PHASE_3_PLAN.md:192` to match what the code does. Standalone value,
      zero risk, no model, no schema change.
- [ ] **7.1 — `src/checks/planner.py`, pure functions only.** Build the prompt,
      parse the reply, validate names against `workflow.KNOWN_CHECKS`, and merge
      monotonically: `model_order ∩ eligible`, then `eligible − model_order`
      appended. **No `model_client` import** — `tests/parsing/test_offline_containment.py`
      gains this module to the set that may not import it, which is the
      structural proof the call stayed at the edge. The model function arrives
      as a parameter, the way `advise.py` takes its `Retriever`.
- [ ] **7.2 — wiring and the `planner_run` block.** `build_findings` calls the
      model at the edge and passes `plan_order` in. `planner_run` mirrors
      `model_run`. **`schema-keeper` before any code.**
- [ ] **7.3 — the prompt-template structure probe**, its own artifact, own
      report section, own schema. Not before 7.0–7.2 land. Rule 18: split its
      judging rules into their own module, the way `artifacts/advice_rules.py`
      was split out of `remediation.py`. Do **not** add to `src/checks/taint.py`
      (214 lines) or `src/artifacts/findings_document.py` (211) — both are
      already over the ~200 cap.

## One defect 7.0 introduced, and what it teaches

The first version of `act` removed the chosen check from `remaining` with a
filter — `[left for left in remaining if left != name]`. That removes **every**
entry with that name, so a plan naming one check twice collapsed to a single
step. `MAX_STEPS` could then never be reached end-to-end, and the step cap's
only end-to-end coverage disappeared silently.

It was not caught by checking a real app, because `run_checks` only ever
produces plans of distinct names — so "behaviour is unchanged" was true of every
plan the production path builds and false of the plans the cap tests build. The
suite caught it; the measurement did not. Worth remembering the next time an
end-to-end check on one real repository looks like sufficient evidence.

The fix keeps by-name removal and drops only the first occurrence.

## A constraint 7.2's wiring must respect

`order_checks` catches `RuntimeError` and nothing else, so **whatever
`build_findings` injects as `ask` must raise `RuntimeError` on a reach failure**.
`model_client.ask` does: `model_client.py:71` converts every `OSError` --
`URLError` and `TimeoutError` included -- into a `RuntimeError` before a caller
sees it. A raw `urllib` or socket call wired in directly would crash the audit
rather than degrade, and `order_checks` is right to let it: that would be this
repo's bug, not the model server being down.

Found by `test-writer`, which discovered two existing fixtures raising
`ConnectionRefusedError` and `TimeoutError` and fixed the *fixtures* rather than
widening the `except` -- correctly, since those shapes cannot reach a caller.

Two more, for the same wiring:
- `ask` must default to `None` in `build_findings`. Ten test files call it
  directly, so a `model_client.ask` default would have the suite attempting
  sockets on a clean checkout, against rule 13.
- `model_client.model_digest()` opens a socket and raises when Ollama is absent,
  so if `planner.json`'s `identifier` is ever a digest rather than
  `model_client.MODEL`, that call belongs inside the same guarded edge.

## Tests this phase is not done without

- **Monotone merge, exhaustively**: for every malformed model reply — unknown
  check name, empty, non-JSON, truncated, subset, superset, duplicates —
  `set(result) == set(eligible)`. This is what makes "never subtract" binding
  rather than a promise.
- `coverage.checks_run` equals the eligible set regardless of what the model said.
- `tests/parsing/test_offline.py` (extended, not a new file): `workflow.audit`
  still records `attempts == []` after the planner ships.
- **Model unreachable → deterministic default order, and `findings.json`
  byte-identical to a model-disabled run.** This is the byte-identity falsifier
  the suite has never had, and it is the most valuable test in the phase.
- Segregation: `findings.json` with the probe on is byte-identical to with it off.
- Probe: no `Finding` from a refuted, inconclusive or model-unavailable result.

## Still open

The proposal itself is **not in `docs/`** — nothing tracked lets an examiner
check what was promised. Transcribe its two relevant sentences here, the way
`docs/REPORT.md` Appendix A transcribed the corpus pins, so the claim this phase
answers is falsifiable.

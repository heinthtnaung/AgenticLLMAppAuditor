# Results

Measured on `damn-vulnerable-llm-agent`, upstream commit `c0cf9a14`. Earlier
long-form discussion is in git before commit `c10daa0`.

## Detection

Scored against `grading_keys/damn-vulnerable-llm-agent.ground_truth.json`, six
entries.

| System | Matched | Missed |
|---|---|---|
| This auditor, static | **4 of 6** | DVLA-01, DVLA-02 |
| This auditor, `--semantic-probe` | **5 of 6** | DVLA-02 |
| Baseline A, grep/AST rules | **5 of 6** | DVLA-07 |
| Baseline B, SBOM-only | **0 of 6** | all |

```
auditor  {DVLA-01, 03, 05, 06, 07}
baseline {DVLA-01, 02, 03, 05, 06}    shared 4, union all six
```

**The sets matter more than the counts.** The auditor alone reaches DVLA-07, the
supply-chain entry — that needs joining an LLM surface to a component, which no
grep rule has. Baseline A alone reaches DVLA-02: a tool taking a bare identifier
with no authorisation check. That is a real gap, not an artefact —
`permissions.py` is silent because the tool grants no shell, interpreter or
network reach, and what makes it a finding is an *absent* comparison rather than
a present capability.

**The probe's contribution is one entry.** DVLA-01 is where the taint trace runs
and stays silent: `argument_names` collects `ast.Name` only, so an f-string
system prompt yields nothing to follow.

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
   the app.
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

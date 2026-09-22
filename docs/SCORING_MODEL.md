# The Organisation Risk Score

Captured from `docs/sources/brainstorming.pdf`. This is the design every agent
works to. Where an agent's instructions and this file disagree, this file wins.

## Two scores, never merged

| Field | Who owns it | What it means |
|---|---|---|
| `nvd_cvss_base_score` | NVD | technical severity, quoted, never recomputed |
| `vendor_cvss_score` | the vendor | the same, from a source that may disagree |
| `organisation_risk_score` | this system | 0–100, this environment's assessment |
| `llm_explanation` | the model | why they differ, with evidence |

A blended number is unattributable. Keep the fields apart.

## The four roles

```
CVE data + vendor advisory
    -> LLM analyst          reads the CVE, extracts exploit prerequisites
    -> question selector    picks templates matching those prerequisites
    -> organisation         answers Yes / No / Unknown / N/A
    -> LLM validator        finds incomplete or contradictory answers
    -> scoring engine       computes the score. deterministic, no model
    -> LLM explainer        writes the rationale
    -> human                approves or overrides
```

## The score

Four categories, each normalised to 0–100, then weighted:

| Category | Weight | Measures |
|---|---|---|
| Technical severity | **30%** | CVSS severity and technical exploitability |
| Exposure and reachability | **25%** | internet exposure, network access, segmentation |
| Business impact | **25%** | asset criticality, data sensitivity, disruption |
| Threat and exploitation | **20%** | active exploitation, public exploit, automation |

**The source document contradicts itself here.** Page 27 writes the formula as
`0.30T + 0.30E + 0.20B + 0.20C`, which does not match its own table. The worked
example settles it: CVSS 8.0 with no exposure and no threat gives
`80×0.30 + 0×0.25 + 80×0.25 + 0×0.20 = 44`, which is the answer the document
prints. **Use 30/25/25/20.**

### Bands

| Score | Rating |
|---|---|
| 0–24 | Low |
| 25–49 | Medium |
| 50–74 | High |
| 75–100 | Critical |

These are the *organisation* bands on a 0-100 scale. **They are not the CVSS
bands**, which run 0.0-10.0 and carry their own response times:

| CVSS | Rating | Response |
|---|---|---|
| 9.0-10.0 | Critical | immediate; exploitation likely gives root or admin |
| 7.0-8.9 | High | within 1 month; significant C/I/A risk |
| 4.0-6.9 | Medium | within 2 months; usually needs local network position |
| 0.1-3.9 | Low | if resources allow |
| 0.0 | Info | if resources allow |

A CVE can be CVSS Critical and organisation Low. That is the point of the
exercise, not an error to reconcile.

### Turning answers into a category score

Each question carries its own weight. Never `Yes = +10` everywhere — define
what Yes means per question.

Exposure, for example:

| Question | Yes |
|---|---|
| Is the affected service internet-facing? | +40 |
| Is it reachable from an untrusted network? | +25 |
| Is the vulnerable port or API exposed? | +20 |
| Is the asset isolated or segmented? | −15 |
| Is the component disabled? | −30 |

**Clamp every category to 0–100 before weighting.** A strong control must not
produce a negative risk.

### Unknown answers

Calculate a provisional score and flag it. Do not silently treat Unknown as No,
and do not refuse to score.

## What the LLM may not do

Binding. Each is a refusal in code, not a line in a prompt.

- determine the final score
- modify scoring weights
- override escalation rules
- approve a risk decision
- patch anything, change a firewall rule, close a finding, or mark a CVE
  accepted

It **may** analyse the CVE, identify exploit prerequisites, select questions
from an approved template library, explain them, detect incomplete or
contradictory answers, and write the rationale. Its output is structured and
**validated by application code** before anything uses it.

## What is kept for audit

Per assessment: the CVE data, the LLM output, the organisation's answers, the
evidence, the score calculation, the **prompt and model version**, and the
approval record.

A score nobody can re-derive is not a score.

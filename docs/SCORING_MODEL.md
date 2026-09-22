# The Organisation Risk Score

Captured from `docs/sources/brainstorming.pdf`. This is the design every agent
works to. Where an agent's instructions and this file disagree, this file wins.

## Published scores, never merged

A finding carries **one published assessment per source**, not one NVD field and
one vendor field.

| Field | Who owns it | What it means |
|---|---|---|
| `scores` | the sources | one entry per source whose published vector was read |
| `unreadable` | the sources | one entry per source whose vector the calculator refused |
| `organisation_risk_score` | this system | 0–100, this environment's assessment |
| `llm_explanation` | the model | why they differ, with evidence |

Each entry in `scores`:

| Field | What it holds |
|---|---|
| `source` | the source's own name — `nvd`, `redhat`, `ghsa`, `bitnami`, `julia` |
| `vector` | the CVSS vector string as published, quoted, never edited |
| `base_score` | the number `src/cvss/` computes from that vector |

An entry in `unreadable` keeps the source, the vector string, and the refusal.

A blended number is unattributable. Keep the entries apart, and keep the source
name on every one of them.

**The vector is quoted; the score is computed.** `src/cvss/score.py` derives the
number from the vector by the published equations, so every score on a row
re-derives from the vector beside it.

**A source that cannot be read is kept, not dropped.** A published v2 or v4.0
vector is a real occurrence and this calculator refuses it, so that source goes
to `unreadable` with the reason. It is never scored 0.0: "nobody scored this"
and "somebody scored this 0.0" are different findings, and one optional number
would let them be told apart only by remembering to check. The two records are
separate types for that reason — `src/findings/assessment.py`.

### Why a list, and not two fields

Two fields assume NVD is always there and that there is one vendor. Two
measurements, on different corpora, say neither holds:

| Corpus | Findings | `nvd` has a vector | The others |
|---|---|---|---|
| 8 out-of-date PyPI packages, local Trivy DB | 124 | 102 (82%) | `redhat` 117, `ghsa` 115, `bitnami` 68, `julia` 3 |
| `github.com/savoirfairelinux/vulnscout` | 18 | 4 (22%) | `ghsa` 18, `redhat` 16 |

On the real repository NVD is absent from 78% of findings, so a field anchored
to NVD is empty on most rows while `ghsa` has every one of them. And "the
vendor" is up to four sources that disagree with each other, not only with NVD:
5 of the 18 vulnscout advisories carry sources that disagree, and on the PyPI
corpus 49 of the 119 findings with at least two of `nvd`, `redhat` and `ghsa` do.
One field cannot hold four answers without choosing one, and choosing one is the
merge this section forbids.

**Which source wins is open.** Nothing here ranks them, and no precedence order
is defined. Settling which reading an advisory supports is the assessor
council's job (`docs/COUNCIL.md`); until it runs, the report shows every entry
side by side and names no winner.

## The four roles

```
CVE data + published advisories
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

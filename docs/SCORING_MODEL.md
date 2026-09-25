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

**Temporal metrics are read and not scored.** A v3 vector may end with `E`,
`RL` or `RC`; `src/cvss/` holds each to its v3 values as strictly as a Base
metric, scores the Base metrics alone, and `vector` keeps the string as
published. On the npm corpus in `measurements/`, `CVE-2020-11023`'s `ghsa`
vector ends `/E:H`, scores 6.9, and is quoted with the `/E:H` still on it.
What that costs: no Temporal score is computed, so a source's `E:H` moves no
number here, and exploitation reaches the score only through the threat
questions the organisation answers.

**A source that cannot be read is kept, not dropped.** A published v2 or v4.0
vector is a real occurrence and this calculator refuses it, as it refuses a v3
vector carrying an Environmental metric — those describe one deployment, which
is what the organisation's answers are for — so that source goes to
`unreadable` with the reason. It is never scored 0.0: "nobody scored this"
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
is defined. The assessor council reads which value an advisory supports
(`docs/COUNCIL.md`), but it does not pick a winner either: the report shows
every entry side by side, and a vector the council settled beside them, never
in the score.

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
| 0.0 | None | if resources allow |

A CVE can be CVSS Critical and organisation Low. That is the point of the
exercise, not an error to reconcile.

**The source document calls 0.0 "Info"; the specification calls it "None".** The
row above is corrected to the published v3.1 qualitative scale, which is what
`src/cvss/score.py` returns.

That is the second place `docs/sources/brainstorming.pdf` departs from the
standard it describes — the category weights are the other, and that one moved
every number the tool produces. One is a transcription slip; two is a pattern.
Check the PDF against the published specification rather than trusting it,
including in the parts nobody has implemented yet.

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

### The library is approved, and approved is structural

Twelve questions across the three answered categories — technical severity is
not asked, because it comes from the published vectors. An operator answers by
**question id**, and the id is resolved inside the library, so a caller never
holds a question and cannot introduce one or change what a Yes is worth. That is
the rule below — the model may not modify scoring weights — made structural
rather than promised: taking a question from a caller would let any weight in,
and taking an id cannot.

**Which weights came from this document, and which did not.** The exposure table
above is quoted into the library weight for weight, both compensating controls
included, and a test holds the library to it. The business and threat weights
are **the library's own**: this document gives exposure "for example" and pins
business impact only through its worked example, where business-critical,
production and sensitive data come to 80. They are a starting point for an
operator to argue with, not a measurement, and the distinction matters to anyone
judging where a number came from.

The worked example runs end to end through the library: CVSS 8.0, nothing
exposed, no threat, and those three business answers give **44.0, Medium** — the
number this document prints.

### Unknown answers

Calculate a provisional score and flag it. Do not silently treat Unknown as No,
and do not refuse to score.

### One score per source, because there is no single severity

Technical severity is 30% of the total and it is the one input this system does
not own. While sources disagree, a finding **has no single technical severity**,
so it is scored once per published source and the report carries the range:
`46.9 to 54.4`, with every source's own figure behind it.

Choosing one source instead would be the precedence this document refuses to
define, arriving as an implementation detail. The range costs a reader nothing
and answers a question no single number can: **does which source you believe
change what this organisation should do?** Usually it does not, and that is the
useful answer — two sources 2.5 apart on the CVSS scale can land in one band
here, which is the argument between them ceasing to matter in this environment.
When it does change the band, the report says so on the heading rather than
leaving a reader to compare rows.

It runs the other way too, and that is the sharper case. Two sources **agreeing**
— 7.0 and 7.5, both High — can come out Low and Medium in an environment that is
internet-facing with the component disabled. Agreement on the published number
is not agreement on what to do about it.

**A vector the council settled does not narrow the range.** Technical severity
is weighed from the published sources alone. The council's vector is shown
beside the range with its own CVSS base score, saying the risk score does not
use it. Measured on the 18 vulnscout findings against a reference built from
published vectors, the council's settled values matched it on Attack Vector 0
times in 11, Privileges Required 0 in 9, User Interaction 0 in 13 and Scope 1 in
13, where answering the commonest value scores 1.00 (`measurements/README.md`,
which says what that cannot show).

It costs the one case where the council's vector was the only severity on
offer. A finding no source scored still weighs technical severity at 0 and
stays provisional, even where a council settled a vector for it.

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

**The approval record exists and nothing stamps it.** Who approved, which
decision it was, when, and why all travel in the answer file, validated as a
real instant so a record cannot carry `"yesterday"`. The time arrives with the
human act rather than being read from a clock, which is also what keeps a run's
JSON byte-identical between two runs over the same inputs. Stamping one would
need an approval command, which does not exist — and it would be the first clock
anywhere in `src/`.

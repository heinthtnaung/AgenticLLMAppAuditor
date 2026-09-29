# The Organisation Risk Score

Captured from the project's design brief, a brainstorming document kept outside
this repository. This is the design the code is built to. Where any other
instruction and this file disagree, this file wins.

## Published scores, never merged

A finding carries **one published assessment per source**, not one NVD field and
one vendor field.

| Field | Who owns it | What it means |
|---|---|---|
| `scores` | the sources | one entry per source whose published vector was read |
| `unreadable` | the sources | one entry per source whose vector the calculator refused |
| `organisation_risk_score` | this system | 0–100, this environment's assessment |
| `llm_explanation` | the model | why they differ, in the model's words beside a quotation from the advisory; the quotation is checked and the words are not |

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

**Two severity floors raise a band the weights leave too low.** A weighted
total averages, and a vulnerability exploited in the wild on an asset nobody
exposes still comes out Medium or Low by the weights alone. The rules are chosen,
not measured (`src/scoring/floors.py`):

| Rule | An explicit Yes to | Band at least | Why |
|---|---|---|---|
| `FLOOR-EXPLOITED-HIGH` | THR-1, exploited in the wild | High | it is being used against somebody now, and no weighting of this environment should put it below High |
| `FLOOR-EXPLOITED-EXPOSED-CRITICAL` | THR-1, EXP-1 internet-facing, and BUS-1 business-critical | Critical | exploited, exposed and critical is the case this score exists to catch |

**Only the band moves.** The number is what the weights give, and the record
keeps both bands: `score_band`, the one the number gives, and `band`, the one
the floors leave. Each floor that raised a band is recorded with its rule, the
answers that met it, and the band before and after; one that raised nothing is
not recorded. They are applied to each source's score after it is banded.

**Only an explicit Yes triggers one.** Unknown already marks a score
provisional, and letting it raise a band too would read a guess as a fact; No
and N/A never do. A floor never lowers a band. The approval rule reads the band
after the floors, so a floored High needs approval as any High does.

What that costs: the band no longer follows from the number alone. Given the
all-No skeleton with THR-1 and THR-2 Yes for `CVE-2021-4279`, its GHSA score is
37.9, Medium on the table above, and its band is High. A reader has to read the
floor to see why, which is why every floor is on the record.

**The source document calls 0.0 "Info"; the specification calls it "None".** The
row above is corrected to the published v3.1 qualitative scale, which is what
`src/cvss/score.py` returns.

That is the second place the source document departs from the standard it
describes — the category weights are the other, and that one moved every number
the tool produces. One is a transcription slip; two is a pattern. Check the
document against the published specification rather than trusting it,
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
published vectors, the settled values of a council of `qwen2.5:7b-instruct`
and `llama3.2:latest`, each metric asked in one order, matched it on Attack
Vector 0 times in 11, Privileges Required 0 in 9, User Interaction 0 in 13 and
Scope 1 in 13. Asked in both orders, as every audit now is, they matched 0 in
3, 0 in 5, 1 in 3 and 0 in 13. Either way, answering the commonest value scores
1.00 (`measurements/README.md`, which says what that cannot show). The score
reads no council's vector, whatever the roster.

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
evidence, the score calculation, the **prompt and model version**, the
**scoring-rule version**, and the approval record.

A score nobody can re-derive is not a score.

**The scoring-rule version names the rules the score was weighed by.** It is
`SCORING_RULES_VERSION` in `src/scoring/version.py`, `ors-1` today, and every
report carries it: the text heading, the page's tools line and
`run.scoring_rules_version` in JSON. It covers the rules that can move a score
or a band, or mark it provisional: the approved questions, their text and Yes
weights, the category weights, the 0–100 clamp and the CVSS scale onto it, the
band thresholds, the severity floors, and what marks a score provisional. **Bump
it whenever any of those changes.**
Two reports under different versions are not comparable score for score, and
`tests/scoring/test_version.py` fails on a rule change the version did not
follow, because it fingerprints the rules and what the engine makes of a fixed
set of answers.

**The approval record exists and nothing stamps it.** Who approved, which
decision it was, when, and why all travel in the answer file, validated as a
real instant so a record cannot carry `"yesterday"`. The time arrives with the
human act rather than being read from a clock, which is also what keeps a run's
JSON byte-identical between two runs over the same inputs. Stamping one would
need an approval command, which does not exist — and it would be the first clock
anywhere in `src/`.

**Which findings need that approval is a rule, not a judgement.** A finding
needs approval when any source's Organisation Risk Score is High or Critical, or
its published sources disagree on a metric (`src/organisation/approval_rule.py`).
Any source's band counts, because a finding is scored once per source and
picking one would be the precedence this model leaves open. Without answers
there is no score to band, so only disagreement can mark a finding, and the
report says that half alone was checked. The approval stays one per audit: it
covers every marked finding, and nothing records a decision on one finding
apart from the rest.

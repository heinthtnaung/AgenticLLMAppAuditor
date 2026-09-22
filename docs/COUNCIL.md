# The assessor council

A product feature, not a development practice. Published sources disagree about
a CVE's severity on two findings in five; a roster of models assesses the
advisory independently and a chairman reconciles them.

Read `docs/SCORING_MODEL.md` first. Everything here sits inside its rule: **the
council never produces a number.**

## Why more than one model

Sources disagree routinely, and the disagreement is already on this machine.
`trivy fs` over a manifest of eight deliberately out-of-date PyPI packages
returns 124 findings, and their CVSS v3 vectors come from five sources at once:

| Source | Findings carrying its vector |
|---|---|
| `redhat` | 117 (94%) |
| `ghsa` | 115 (93%) |
| `nvd` | 102 (82%) |
| `bitnami` | 68 (55%) |
| `julia` | 3 (2%) |

Four sources assess 57 of the findings, three assess 51, two assess 11, one
assesses 2, and 3 carry no vector at all. **87% arrive with three or more
independent assessments**, offline, before anything is fetched.

They contradict each other on two in five. Of the 119 findings carrying at least
two of `nvd`, `redhat` and `ghsa`, 49 disagree — `nvd` against `redhat` on 46,
`ghsa` against `redhat` on 34, `ghsa` against `nvd` on 18.

Often the gap is one metric: `CVE-2025-37164` is 10.0 to the CNA and 9.8 to
Tenable, `S:C` against `S:U`, and both are arithmetically right. Sometimes it is
three.

```
CVE-2026-26007
  nvd     CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:N/A:N
  redhat  CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N
```

Attack Complexity, User Interaction and Integrity, from the same advisory. That
is a reading of text, not a calculation, and a reading is where one opinion is
worth little.

So **reconciling sources is the normal path**, not a special case for contested
CVEs; a design that treated it as an exception would be wrong about two findings
in five. And **there is no reference source**: `nvd` covers fewer findings than
`redhat` or `ghsa`, and `redhat` contradicts it on 46 of the 119. They are three
peers. No member is marked against any one of them — the council decides which
reading the advisory supports.

The competing vectors ship inside the Trivy database, so none of this costs a
fetch and the offline guarantee holds. Where a *member* runs is a separate
question, answered further down: that is who assesses, not where the published
vectors came from.

**One corpus.** Eight PyPI packages, one manifest, one database snapshot. The
exact rate moves with a different corpus; that the disagreement is widespread
does not.

The source notes sketch a ladder: a small local model, then a larger one, then
a cloud one, each asked whether the published scores align. The ladder survives
here as a **policy**, not as the shape of the council. A hosted model is an
ordinary member of the roster; escalation is one way to order members, not the
only way a hosted model takes part.

## What the council decides, and what it does not

```
n council members  ->  a metric value + the sentence that supports it
chairman           ->  one agreed vector + a rationale + a confidence
scoring engine     ->  the number            <- deterministic, no model
human              ->  approve or override
```

**The chairman hands over a vector, never a score.** The engine turns a vector
into a number by the published formula, the same way every time. A model that
emitted 7.4 directly would be unauditable, and `docs/SCORING_MODEL.md` forbids
it. That holds for every member, local or hosted, at every n.

## The roster

The council is **n members, added and removed by the operator**. A member is
one model reached through one provider, and a roster mixes the two kinds
freely.

| Kind | Reached through | What it costs |
|---|---|---|
| local | Ollama on this machine | nothing per call; pinnable; queues on one GPU |
| hosted | OpenRouter or another API | money per call; parallel; not pinnable; the text leaves the machine |

Nothing in the design counts members, so nothing depends on n being three, or
odd, or anything else. The edges are still real:

- **n = 0** is a configuration error. Refuse the run. Do not fall back to the
  published vector and call the result an assessment.
- **n = 1** is not a council. It degrades to a single assessor: the quotation
  check still runs and the chairman still hands over a vector, but with no
  cross-check a metric can only come out agreed or unresolved — `contested`
  can never arise. The record marks the run single-assessor, so no reader
  takes council-grade confidence from one model.
- **Even n** needs no rule, because nothing is counted. Two members on `S:C`
  and two on `S:U` is not a tie; it is four pieces of evidence, and the
  chairman ranks them by whether the quotation verifies. That is the path an
  odd roster takes too.

## Panel, not chain

Each member sees **the advisory text only** — not the other members' answers,
not the published scores, not the CVE id.

- **Not the other members**, or they converge and you get one opinion in n hats.
- **Not the published scores**, or you measure whether a model can copy.
- **Not the CVE id**, or a model that recognises `CVE-2021-44228` recites it
  from training and you measure memorisation.

A chain — each model refining the last — is the tempting alternative and it
cannot be measured. Once the second model sees the first's answer, agreement
between them means nothing. **Independent members can be scored; a chain
cannot.**

Independence comes from the training, not from the provider or the name. Five
OpenRouter models drawn from one family are less diverse than one local model
plus one hosted model of another lineage. Adding a member raises cost with
certainty and raises independence only when the family differs. Record each
member's family, so a reader can judge what a roster's agreement was worth.

## What a member returns

```
metric           which one it is assessing
value            the value it supports
evidence         a verbatim quotation from the advisory
confidence       high / medium / low
member           which member answered, and whether it ran local or hosted
```

**Evidence is a quotation, not a paraphrase.** It must appear in the text it was
given, and application code checks that. A rationale can argue anything; a
quotation can be verified. It is the same check for every member; a hosted
member earns no extra trust by costing money.

A member that cannot find supporting text must say so rather than guess. Some
advisories carry no evidence for some metrics — `CVE-2025-37164`'s record is one
sentence that says nothing about Scope, so *no* reader could settle it. That
absence is a result and must survive to the report.

## What the chairman does

Deterministic where it can be, and its reasoning is recorded either way. It
reads all n answers at once, and the rules do not change with n.

- **Members agree** → that value, confidence from the weakest member.
- **Members disagree** → the one whose evidence is a real quotation wins. If
  more than one qualifies, mark the metric contested and hand it to the
  escalation policy.
- **No member found evidence** → the metric is unresolved. Fall back to a
  published vector, and record both that the fallback happened and which source
  it came from — there is usually more than one, and they often differ.

**Never a majority vote, at any n.** Counting is what makes an even roster look
like a problem and a large one look authoritative. Neither is true, because
members on one base model share its mistakes. Evidence decides.

## Escalation is a policy, not a tier

Order the roster by cost. Ask the cheapest members first, and send only a
metric that came out contested or unresolved to a costlier one — never the
whole CVE. Record which member answered which metric.

Asking every member every time is the other policy: more money, fewer rounds.
Neither changes what a member returns or what the chairman does with it.

## What a hosted member costs

**Reproducibility, first and sharpest.** A local member can be pinned: a fixed
model digest, temperature 0, a seed. A hosted model takes no seed, and the
weights behind a name change without notice. **A council holding one hosted
member is not reproducible run to run**, and every figure downstream inherits
that — the vector can differ, so `organisation_risk_score` can differ, so the
band can differ.

What survives is narrower, and saying which is the point. The engine stays
deterministic — the recorded vector re-derives the recorded number exactly. It
is the *vector* that stops being re-derivable. Only an all-local pinned roster
may claim a reproducible assessment, and a run records which kind it was.

**What leaves the machine.** A hosted member is sent the prompt and the
advisory text — public text, by the panel rule, carrying no CVE id and no
published scores. The organisation's answers never reach any member; the
council reads advisories, not the environment. What leaks is the pattern:
*which* advisories you ask about, and when, describes the software you run.
That is worth more to an observer than any one advisory.

So hosted members are **opt-in per member**, off by default, and the record
names every member that ran, its provider, and whether it was local or hosted.
A record that does not say where the text went is not an audit record.

**Money and time.** Calls scale with n × findings × metrics. Hosted members
bill per call and run in parallel; local members are free and queue on one GPU,
so n buys latency there instead of money. The roster is fixed per run, before
the scan, because it is a budget decision as much as a design one.

## A roster as configuration

**A sketch.** The project has committed to no file format, and this shows what
a reader would be editing rather than a schema to write against. The model
names are examples; check the provider's catalogue for current ids.

```yaml
council:
  members:
    - name: small-local
      provider: ollama
      model: qwen2.5:7b
      family: qwen
      options: {temperature: 0, seed: 11}
    - name: large-local
      provider: ollama
      model: qwen3:8b
      family: qwen
      options: {temperature: 0, seed: 11}
    - name: hosted-other-family
      provider: openrouter
      model: anthropic/claude-sonnet-5
      family: claude
      egress: allow        # absent or false: skipped, and the skip is reported
  chairman: large-local
  policy: escalate         # or: ask-all
  escalate_on: [contested, unresolved]
  escalate_to: hosted-other-family
```

Adding a member is a list entry; removing one is deleting it. `egress` is the
opt-in, and it fails closed: a hosted member without it does not run, and the
report says it did not.

## What is kept

Per assessment: each member's answer and evidence, the model, provider, family
and prompt version behind it, whether that member ran local or hosted, the
roster as configured, the chairman's reasoning, the final vector, and the
computed score. A score nobody can re-derive is not a score, and a roster
nobody can reconstruct is not a council.

## Not built

**None of this exists yet, and neither does the engine underneath it.** There
is no `src/` at all. The members, the roster and its configuration, the
chairman, the escalation policy, the provider clients and the CVSS calculator
they hand a vector to are all design. This file is the intent, not a
description of code.

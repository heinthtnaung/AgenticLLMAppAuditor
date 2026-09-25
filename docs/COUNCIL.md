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
chairman           ->  one agreed vector + a rationale + a confidence  <- code, no model
scoring engine     ->  the number                                      <- code, no model
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
| local | Ollama on this machine | nothing per call; pinnable; shares one Ollama server with the other local members |
| hosted | OpenRouter or another API | money per call; not pinnable; the text leaves the machine; an API could answer calls in parallel, but the runner asks each member in turn |

Nothing in the design counts members towards a ruling, so nothing depends on n
being three, or odd, or anything else. The basis a settled value records is the
one place a member is counted, and it changes what the record admits, never
the ruling. The edges are still real:

- **n = 0** is a configuration error. Refuse the run. Do not fall back to the
  published vector and call the result an assessment.
- **n = 1** is not a council. It degrades to a single assessor: the quotation
  check still runs and the chairman still hands over a vector, but with no
  cross-check a metric can only come out settled, on the `SOLE` basis, or
  unresolved — `contested` can never arise. The record marks the run
  single-assessor, so no reader takes council-grade confidence from one
  model. **The count is of the members a run will ask, not of the roster**:
  three members of whom two are hosted without `egress` cross-check nothing,
  and that run is marked single-assessor exactly as a roster of one is.
- **Even n** needs no rule, because nothing is counted towards a ruling. Two
  members on `S:C` and two on `S:U` is not a tie; it is four pieces of
  evidence, and the chairman ranks them by whether the quotation verifies.
  That is the path an odd roster takes too.

## Panel, not chain

Each member sees **the advisory text only** — not the other members' answers,
not the published scores, not the CVE id.

- **Not the other members**, or they converge and you get one opinion in n hats.
- **Not the published scores**, or you measure whether a model can copy.
- **Not the CVE id**, or a model that recognises `CVE-2021-44228` recites it
  from training and you measure memorisation.

**The rule is applied to the text, not asked for in the prompt.** A sentence in
a prompt cannot unsee an id, and an advisory's own text routinely carries the id
and, in some feeds, a vector. Both are replaced by markers rather than deleted,
so a sentence still reads as a sentence and can still be quoted — and the
redacted text is what the quotation check is given, because checking against the
original would fail every quotation spanning a redaction and report an absence
the advisory never had.

A score written as prose is not caught. That gap is measured rather than
assumed, and the measurement is the reason it stays open. Across **1,187
distinct advisories** — seven offline scans covering PyPI, npm, Go, Rust, Debian
11 and Alpine, plus vulnscout's 18, none of which carries one — exactly one
does. That is on the database built 2026-09-22; on its successor the scans give
1,189, and still exactly one (`measurements/README.md`). Redacted, tornado's
`GHSA-pw6j-qg29-8w7f` reads:

```
Proposed CVSS 3.1: [published score withheld] (5.9, medium); attack complexity
is High because...
```

The marker takes out the vector and the sentence publishes the score beside it.
**There are two leaks there and only one of them is catchable.** `(5.9, medium)`
is a pattern away and would cost nothing. "attack complexity is High" is the
published value of a metric a member may be assessing, three words later, and no
pattern reaches it without eating the advisory's own reasoning — which is the
text the member is there to read. Catching the cheap half would let this system
say the published scores are withheld while the Attack Complexity value stands
in the one advisory that proves otherwise. An open gap a reader knows about is
worth more than a claim that is true 1,186 times. **Half-redaction is worse than
none here**, not merely less complete: a visible `[published score withheld]`
marker tells a reader the text was handled, so taking the number out while
"attack complexity is High" stands three words later makes the leak harder to
notice than leaving both in place.

Two limits on that corpus: an Ubuntu scan returned no findings and was dropped,
and RHSA advisories are untested by occurrence, because RHEL needs an rpm
database that cannot be synthesised offline. The manifests and the synthetic
package databases those scans ran over are in `measurements/`, so the corpus is
something a reader can rebuild rather than take on trust.

A chain — each model refining the last — is the tempting alternative and it
cannot be measured. Once the second model sees the first's answer, agreement
between them means nothing. **Independent members can be scored; a chain
cannot.**

Independence comes from the training, not from the provider or the name. Five
OpenRouter models drawn from one family are less diverse than one local model
plus one hosted model of another lineage. Adding a member raises cost with
certainty and raises independence only when the family differs. Record each
member's family, so a reader can judge what a roster's agreement was worth.

## No retrieval layer

**A member's whole input fits in its context, so there is nothing to retrieve.**
A prompt carries one metric's definitions and one advisory — never all eight
metrics — and a local member pins its window at 8,192 tokens rather than taking
whatever maximum the model offers. Measured against the prompt that runs:

| Input | Size |
|---|---|
| the prompt, with the advisory taken out | 421 tokens |
| advisory, median of the 18 under test | 776 characters, roughly 200 tokens |
| advisory, longest of those 18 | 4,585 characters, roughly 1,150 tokens |
| advisory, longest of the same 1,187 | 17,893 characters, taking the prompt to 4,897 tokens |

The worst case measured is **4,897 against 8,192, a margin of 1.7×** — not the
several times over that an 18-advisory corpus suggested. That margin is guarded
rather than merely large: a prompt the window cannot hold is refused, because
Ollama cuts an overlong one without saying so, and a member would then assess
half an advisory and answer about it with confidence.

The definitions are identical for every query, which makes them a constant
rather than something to look up. **They go in the prompt.** A vector store
would add a failure mode, the wrong passage retrieved or the one that mattered
missed, to a problem that does not exist.

**The gap that looks like a retrieval problem is not one.** `CVE-2025-37164`'s
record is a single sentence that says nothing about Scope, the metric its
sources dispute. No reader could settle it from that text, and retrieval cannot
fetch a document nobody collected. That is missing source data, and the fix is a
corpus question — collect the vendor advisory, or let the metric stand
unresolved.

**What would change the answer.** A body of past human adjudications too large
to hold in context, of which there are none yet; a corpus grown to whole vendor
advisory sites, where which passage matters varies per CVE; or wanting to cite
specification passages in a rationale — and that last is better served by a
small fixed lookup than by a vector store.

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

**Three replies, then, not two.** A member supports a value with a quotation,
reports an absence, or offers a value it cannot quote. The last is the thing the
paragraph above forbids, and it is recorded as its own kind rather than folded
into the absence: **an absence is a fact about the advisory; a guess is a fact
about the member.** One can be counted per member across a corpus, and neither
can once they are mixed. A guess weighs exactly what an absence weighs, which is
nothing — it can neither settle a metric nor make one contested.

**Expect guesses, and expect the fallback.** Asked about a metric its text is
silent on, a model tends to answer regardless: `qwen2.5:7b-instruct` returned
`{"value": "N", "evidence": "", "confidence": "low"}` on two metrics of one
advisory, asked twice each. That is two metrics, one model, one advisory — far
too small to be a property of local models, and enough to say the design should
not expect a polite refusal. Those replies are guesses, they carry nothing, and
the metric comes out unresolved. Which is the evidence rule working: no advisory
contains the sentence "no user interaction is required", so a metric rested on
silence has nothing to verify against.

## What the chairman does

**Deterministic throughout: no model is asked anything here.** Its reasoning is
recorded whichever way it goes. It reads all n answers at once, and the rules do
not change with n. **Every rule below is about the verified answers alone** —
those whose evidence is a real quotation from the advisory. An answer whose
quotation is not in the text supports nothing, however many members give it.

- **The verified answers support one value** → that value, with the confidence
  of the weakest of them, and a record of what it rests on.
- **They support more than one value** → the metric is contested, and goes to
  the escalation policy.
- **There are none** → the metric is unresolved. Fall back to a published
  vector, and record both that the fallback happened and which source it came
  from — there is usually more than one, and they often differ.

**What a settled value rests on is one of three bases**, counted over **every
member that offered a value with a quotation**, verified or not. The record
carries the basis's own words, from `src/council/ruling.py`:

| Basis | When | What the record says |
|---|---|---|
| `SOLE` | one member offered a quotation, and nobody else did | "one member offered a quotation, and no other member offered one" |
| `AGREED` | two or more offered quotations, all for this value | "every member that offered a quotation supported this value" |
| `EVIDENCE` | one of them offered a quotation for another value | "members offering quotations disagreed, and the verified one settled it" |

A guess, a decline and a failed call offer no quotation, so none of them
counts toward a basis. Beside one quotation and nothing else, the record says
the value stood alone, not that members agreed. A second member's quotation
that is not in the advisory still counts: for the same value it makes the
basis `AGREED`, although only one quotation verified. The basis changes what
the record says and not the ruling — the value is the one the verified
evidence supports whichever basis it carries.

**A council that settles only some of the eight still leaves a record.** A
vector needs all eight metrics, so one unresolved metric with no fallback means
no vector — and the run is not discarded with it. What ran, and which metrics it
could not settle, survives into the report: throwing that away told a reader no
council had run at all, which is a different and false thing, and what went
unsettled is the escalation policy's input.

The fallback rule above is unchanged; what has changed is that a caller must now
name the published source to fall back to. The command line names none, because
preferring `nvd` or `ghsa` to fill a gap would set exactly the precedence this
design leaves open, arriving through the back door of an error path. So in
practice today an unresolved metric produces no vector, and the finding keeps
its per-source scores side by side with no winner.

**Values are counted towards a ruling; members never are.** Two members
agreeing and a third dissenting on evidence that does not verify is not a
contested metric — one value has evidence behind it, so it settles. Counting
qualifying members instead would escalate on agreement, and would fire on most
ordinary disagreements, because several members can usually quote an advisory.
The basis is the one place a member is counted: one quotation with no other
beside it reads `SOLE`, and that changes what the record admits, never the
ruling.

**Agreement is not evidence.** n members agreeing with nothing verified settles
nothing: that metric is unresolved and falls back to a published vector. It is
the failure this file already names — members on one base model share its
mistakes, and they share them unanimously.

**Never a majority vote, at any n.** Counting members is what makes an even
roster look like a problem and a large one look authoritative. Counting distinct
values is not a vote: it asks whether the verified evidence points one way or
several. Evidence decides.

## Which findings the council is asked about

**By default, only the ones the published sources do not settle.** The council
reconciles sources, so a finding whose sources already agree is not its work. Of
the 18 findings on the repository this project audits, 5 carry sources that
disagree — a default two-member run makes 80 calls where asking about all 18
makes 288. `--council-all-findings` asks about all 18. That 5 in 18 is one
repository and lower than the two in five measured on the 119-finding corpus
above; how much scoping saves moves with what is being scanned.

**A finding no source scored is asked about, not skipped.** Its sources do not
agree either — there are none — and `disputed_metrics()` is empty for it, so
scoping on disagreement alone would drop exactly the findings where a council
vector is the only severity the finding will ever carry.

**Nor is a finding carrying a source the calculator could not read.** A vector
that failed to parse is an opinion nobody checked, so the readable sources
agreeing says nothing about it — its value may disagree with every one of them.
No finding on the audited repository carries one, so the 5 in 18 stands.

**Scoping costs something real, and that is why it is a flag rather than a
removal.** A council that only ever reads contested findings cannot discover that
two *agreeing* sources are both wrong — and this file says no source is the
reference the others are measured against. An operator who cares more about that
than about the calls turns scoping off.

**Three reasons a finding goes unassessed, and they are three different facts.**
A finding the council was not put to, a finding it assessed and could not settle,
and a run where nobody was named to ask are not the same thing. A scoped run that
recorded nothing for what it passed over would report the first as the third, so
the record keeps them apart and every rendering names the findings under the
reason:

```
COUNCIL (1)
  CVE-2021-4279  settled  ·  CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
  3 findings not asked
    no published source disagrees, so there is nothing to reconcile
      CVE-2026-14257, CVE-2026-53550
    the advisory carries no text for a member to read
      CVE-2026-99999
```

That block is constructed to show both reasons at once. Every advisory in the
audited repository carries text, so a real run there prints only the first — the
second was a silent drop until scoping landed, folded in with "no council ran".

**The heading counts what was assessed and nothing else.** `COUNCIL (1)` on a run
that passed over three, because counting the skips into it would claim the
council did more than it did.

## Escalation is a policy, not a tier

Order the roster by cost. Ask the cheapest members first, and send only a
metric that came out contested or unresolved to a costlier one — never the
whole CVE. Record which member answered which metric.

Asking every member every time is the other policy: more money, fewer rounds.
Neither changes what a member returns or what the chairman does with it.

**It is not built, and what is missing is a precondition rather than the will to
build it.** A metric is contested only when two distinct values *both* verify, so
one cheap member can never make one. Ask a single cheap member first and every
metric it can quote comes back settled by it alone: the `contested` trigger never
fires, the costly member is never reached on the metrics that most need it, and
the round is marked single-assessor. **That buys speed by deleting the
cross-check escalation exists to protect.**

It is not a hypothetical. A two-member run on this machine had Qwen and Gemma
quote the same sentence about `CVE-2021-4279` and give different Attack Vector
values — a contested metric, found because two cheap members read it. A cheap
tier of one would have recorded that as settled. Both Qwen–Gemma runs in
`measurements/council_runs/`, `scoped` and `full`, show it at lines 63–67 of
each report, and the shape is common: 8 of the scoped run's 17 contested
metrics have it, and 20 of the full run's 61.

It belongs to that roster. With `llama3.2:latest` in Gemma's place the same
metric settled, and the recorded report cannot say why: it names no member on
a settled metric and predates the `SOLE` basis, so Llama quoting the same
value, guessing and declining all read alike there. Where the report does
show Llama's answer, on the 39 metrics the full run could not settle, it
guessed 16 times and declined none, and a guess cannot contest anything.
`measurements/README.md` has the counts.

The argument holds for the trigger this section defines, a metric that came
out contested or unresolved, and not for escalation in general. A trigger on the
finding instead — the metrics its published sources dispute — would reach the
costly member even from a one-member cheap tier, because that disagreement
exists before any member answers. It is a different policy from the one
described here.

So, for this trigger, the condition to build against is a **cheap tier of two
or more members that can contest something between themselves**. Below that,
escalation is not a cheaper council; it is a single assessor wearing one.

## What a hosted member costs

**No hosted member can run today**, because no client exists to reach one: it is
reported as skipped for want of a client, whether or not `egress` is set. What
follows is what a hosted member will cost when one can.

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

**Pinning is necessary and, as observed here, not sufficient.** An all-local
pinned roster reproduced its full-run outcome to the metric — 67 settled, 61
contested, 16 unresolved of 144 — across two runs two and a half hours and a
renderer change apart, and two later runs agreed byte for byte on four of the
five findings they shared. The fifth differed in the one run that shared the
Ollama server with another council run. The server answers each model one
request at a time, so the two runs' calls to one model queued rather than
batched; one run's call to Qwen and the other's to Gemma could still compute at
the same moment. So the claim carries a precondition: **reproducible when no
other client is sending requests to the same Ollama server.** That is one
divergence in one contended run, on one corpus and one CPU-only server, not a law.

**The mechanism is untested.** Ollama's own log rules out three: requests
batched together, a model reloaded between runs, and a model placed on a GPU.
The candidate left is the server's reuse of a cached prompt prefix, where the
request that came before decides what is reused, and another client's requests
change that. `measurements/README.md` has the runs in `council_runs/` and the
log evidence beside them.

**What leaves the machine.** A hosted member is sent the prompt and the
advisory text — public text, by the panel rule, carrying no CVE id and no
published scores. The organisation's answers never reach any member; the
council reads advisories, not the environment. What leaks is the pattern:
*which* advisories you ask about, and when, describes the software you run.
That is worth more to an observer than any one advisory.

So hosted members are **opt-in per member**, off by default, and the record
names every member that ran, its provider, and whether it was local or hosted.
A record that does not say where the text went is not an audit record.

**Money and time.** Calls scale with n × the findings the scope leaves × metrics.
The runner asks every member in turn, local or hosted, and waits for each
answer before it makes the next call. Local members are free and share one
Ollama server, so for them n buys latency instead of money. A hosted member
would cost both: money per call, and its turn in the same wait, because a
hosted API could answer calls in parallel but the runner as built does not send
them that way. The roster is fixed per run, before the scan, because it is a
budget decision as much as a design one.

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
  policy: escalate         # or: ask-all
  escalate_on: [contested, unresolved]
  escalate_to: hosted-other-family
```

Adding a member is a list entry; removing one is deleting it. `egress` is the
opt-in, and it fails closed: a hosted member without it does not run, and the
report says it did not.

**There is no `chairman` key, because there is no chairman model.**
`src/council/chairman.py` makes no model call at all: it keeps the answers whose
quotation is in the advisory, then asks whether those point at one value or
several. Every rule this file gives the chairman is mechanical, so code can
apply all of them.

That is a decision and not a gap waiting on a client. A model in the seat would
replace an auditable fact — *these two answers verified and agree* — with a
sentence nobody can re-derive, and asked to reconcile n answers it would reach
for the count of members, which is the one thing this design forbids at any n.
The chairman is also the last step before the engine, so a model there would put
one back inside the path a vector takes to a number.

## What is kept

Per assessment: each member's answer and evidence, the model, provider, family
and prompt version behind it, whether that member ran local or hosted, the
roster as configured, the chairman's reasoning, the final vector, and the
computed score. A score nobody can re-derive is not a score, and a roster
nobody can reconstruct is not a council.

## What is built, and what is not

**The council is `src/council/`, with tests beside every module.** The roster
and its `egress` gate, the redaction, the prompt and the wire contract, the
provider registry and the local Ollama client in it, the HTTP seam under that,
the reply parser, the quotation check, the chairman, and the runner that puts
one advisory to every reachable member, one member at a time: a member answers
all eight metrics before the next is asked. `src/cvss` is the engine it hands a
vector to.

**The scope is built too, and it is not in that package.** `src/cli/council_run.py`
chooses which findings a run is put to, records each one it passes over with the
reason, and counts the calls the scope leaves for the progress stream.

**The provider layer is a seam, not a helper.** Which providers this machine can
reach, and the client that speaks to each, sit apart from the dispatch that puts
a metric to every member — separated by what makes each of them change. A hosted
client and a member's own temperature and seed are provider-layer changes and
touch nothing else; asking every member becoming escalating a contested metric,
and any change to the shape of the run record, are dispatch changes and touch
nothing else. The first two gaps below sit on opposite sides of that line, which
is the useful thing to know before building either.

**A member with no client is reported, never stubbed.** A stub would answer, and
its answer would be fiction recorded as an assessment. So the two reasons a
member goes unasked stay distinguishable in the record: not configured, and
refused by policy.

Five things described above are not built, each deferred rather than forgotten:

- **No hosted provider client.** OpenRouter or another API is a sketch, so a
  hosted member is skipped for want of one — a second reason on top of
  `egress`, and the one that outlasts opting in. Adding one is an adapter and
  an entry in the provider registry; no other module moves.
- **No escalation policy.** The runner asks every member every metric, which is
  the other policy named above. A contested metric is recorded as contested and
  nothing re-asks it on a costlier member. It is deferred on a condition rather
  than on time: the section above gives the measurement and the cheap tier it
  would need.
- **The answering model is not recorded.** A reply says which member was asked,
  not which weights answered. That costs nothing while every member is a pinned
  local one, and becomes the reproducibility hole described above on the day a
  hosted member runs. What *is* pinned now is the other half: a test holds the
  member's own model to the client it is asked through. Before the provider
  layer was separated that line had no test, being the one line that opens a
  socket, and every local member could have run the server's default model with
  nothing to say so — which would have made every recorded member identity a
  claim about a run that did not happen.
- **No per-member options.** A member carries no temperature and no seed, so
  local members run on pinned defaults rather than the per-member `options` the
  sketch above shows.
- **The prose score is not reported.** Removing it will never scale — the
  general form of the leak is a Base metric value written in words, and no
  pattern bounds that without eating the advisory's reasoning. Detecting it
  does: a pattern on the severity word beside the number, the `(5.9, medium)`
  shape, fires once in 1,187 and eats nothing, and could record on the round
  that this advisory states a published score in prose. The text stays whole and
  the guarantee stays honest. A hole that is reported is not the same thing as a
  hole that is hidden.

**`src/cli/` orchestrates all of it**, and that is where to look for the wiring.
`src/cli/council_run.py` chooses the findings and runs the council over them,
`src/cli/council_detail.py` turns a run into the record the report holds, and
`src/cli/organisation_run.py` takes a settled vector into a risk score. The
package itself stays a component: `src/council/` imports `src/cvss` and nothing
else of this project's, and only `src/cli/` imports `src/council/`.

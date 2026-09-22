# Diagrams

The one page to read to understand the system.

**Three stretches of this are built and nothing joins them.** A directory
becomes components, components join advisories, and every source's published
vector is parsed and scored. A council of local models reads an advisory and
agrees a vector. Answers about an environment become an Organisation Risk Score.
What lies between those three and past them — the questions, the hosted client,
the report and any page — the project has decided to build and you cannot run.
Each diagram states its own boundary, and diagram 5 is about nothing else.

`CLAUDE.md` rule 19 binds this file: after any change to how the system works —
a new component, a changed flow, a deleted one — **the diagrams are updated in
the same change**. A stale diagram is worse than none, because it is
confidently wrong. A change that touches no flow says so rather than skipping in
silence.

`docs/SCORING_MODEL.md` is the design and it wins over this page.
`docs/COUNCIL.md` sits inside its rules. This page draws them; it does not amend
them.

| | Diagram | Answers |
|---|---|---|
| 1 | The audit pipeline | how a repository becomes a list of findings |
| 2 | The published scores | how many published scores a finding carries, and why they never merge |
| 3 | The Organisation Risk Score | how answers become a 0–100 score and a band |
| 4 | The assessor council | how a roster of n local and hosted models settles a metric without emitting a number |
| 5 | Build status | what is designed against what exists |

## 1. The audit pipeline

**Built as far as a finding.** Everything inside the scan is source with tests;
the report and the human review are not.

```mermaid
flowchart TD
    subgraph OOB["Out of band, before any scan"]
        fetch["Operator downloads the Trivy vulnerability DB"] --> adb[("Advisory database<br/>on local disk")]
        adb --> age["Its own build date, readable<br/>src/deps/trivy_database"]
    end

    subgraph SCAN["The scan: offline, against the database already on disk"]
        repo["Repository under audit"] --> syft["Syft scans the directory<br/>lockfiles and manifests, one pass"]
        syft --> comp[("Components<br/>name, version, purl, where found")]
        trivy["Trivy reads the database<br/>advisories per purl, and a published<br/>vector for each source that wrote one"]
        comp --> join["Join on the versioned purl"]
        trivy --> join
        join --> asm["Score each source's vector<br/>src/cvss, published equations"]
        asm --> fin["Findings<br/>component, advisory, a score per<br/>readable source, refused vectors kept"]
    end

    adb --> trivy

    fin --> ctx["Organisation context<br/>diagram 3"]
    fin --> rep["Report<br/>one row per finding"]
    ctx --> rep
    rep --> hum["Human reviews"]
```

The database is fetched out of band so that a scan runs offline against the copy
already on disk. That is what a reproducible scan rests on: the same commit and
the same database are meant to produce the same findings.

That choice has a cost, and it is the sharpest edge in this diagram: **an empty
or stale cache produces a clean report rather than an error.** Trivy finds no
advisories, reports nothing, and exits 0. `src/deps/trivy_database` reads the
database's own build date — its own, not the local download time — so a caller
can tell the two apart before the scan. **The reading is built; the refusal is
not.** Nothing yet stops a run against a stale database.

Syft is one box because it is one call: it finds the manifests and catalogues
them in the same pass, so there is no separate discovery component to build. The
calculator sits inside the scan because that is where it runs: every source's
vector is parsed and scored as the finding is assembled, not in a pass over the
findings afterwards.

What this does not show: how findings are stored, how a repeat scan is diffed
against the last one, or what the report is — file, page, or both. None of that
is decided, and none of it is built.

## 2. The published scores

**Half built.** The published vectors, the calculator behind them and the
weighted calculation are real; the LLM roles and the validation that guards them
are not.

```mermaid
flowchart TD
    subgraph QUOTED["Role 1: the published sources. Vectors quoted, never edited"]
        srcs["Sources on one finding<br/>nvd, redhat, ghsa, bitnami, julia<br/>however many published a vector"]
        pv["One published vector per source<br/>they often disagree"]
        srcs --> pv
    end

    subgraph MODEL["Role 2: the LLM. Reads text, produces no number"]
        anl["Analyst: exploit prerequisites"]
        sel["Selector: questions from the approved library"]
        chk["Checker: incomplete or contradictory answers"]
        exl["Explainer: the rationale"]
    end

    subgraph ENGINE["Role 3: the engine. Every number, deterministic"]
        cvs["CVSS calculator<br/>published v3.1 equations<br/>one score per published vector"]
        val["Validate model output<br/>typed structure, refused if it does not fit"]
        cal["Weighted calculation<br/>no model in the path"]
    end

    subgraph HUMAN["Role 4: the human. The decision"]
        dec["Approve or override"]
    end

    pv --> anl
    pv --> cvs
    cvs --> f1["scores<br/>source, vector, base score<br/>one entry per source read"]
    cvs --> f2["unreadable<br/>source, vector, the refusal<br/>never dropped, never scored 0.0"]
    anl --> sel
    sel --> ans["Organisation answers<br/>Yes / No / Unknown / N/A"]
    ans --> chk
    chk --> val
    anl --> val
    val --> cal
    cal --> f3["organisation_risk_score"]
    cal --> exl
    exl --> f4["llm_explanation"]
    f1 --> out["Report: every entry side by side"]
    f2 --> out
    f3 --> out
    f4 --> out
    out --> dec

    f1 x-. "never merged into one number" .-x f3
```

One entry per source, plus the two fields this system owns. The crossed dotted
line is the rule the rest of the design hangs on: **a blended number is
unattributable**, so the published severities and this environment's assessment
stay in separate fields and separate columns. A CVE that is CVSS Critical and
organisation Low is the normal case.

The left column is a list, not a pair. A finding is assessed by however many
sources published a vector for it — three or more on 87% of one measured corpus
— and no source is the reference the others are compared against. On one real
repository NVD had a vector for 4 findings of 18 while GHSA had all 18.
`docs/SCORING_MODEL.md` carries the counts.

Each entry's score is computed from that entry's vector, never quoted. The
vector is what the source published; the number beside it is what the v3.1
equations give, so a reader can re-derive every one of them.

The `validate` box is the boundary, not a formality. Model output reaches the
engine only as a typed structure that application code has already refused or
accepted. A reply that arrives unchecked is the model deciding a number by the
back door.

What this does not show: which source wins when they disagree, because nothing
ranks them — that is the council in diagram 4. The field names are from
`docs/SCORING_MODEL.md`, which this page draws and does not amend.

## 3. The Organisation Risk Score

**Built, apart from the questions.** `src/scoring/` is everything from the
answers rightwards; the template library and the selector that produce them are
not built.

```mermaid
flowchart LR
    cve["CVE and advisory"] --> pre["Exploit prerequisites"]
    pre --> qs["Questions selected<br/>approved template library only"]
    qs --> ans["Answers<br/>Yes / No / Unknown / N/A"]

    ans --> wgt["Per question weight<br/>only Yes moves the total<br/>a compensating control subtracts"]

    wgt --> eraw["Exposure and reachability, raw"]
    wgt --> braw["Business impact, raw"]
    wgt --> hraw["Threat and exploitation, raw"]

    eraw --> eclp["Clamp to 0-100"]
    braw --> bclp["Clamp to 0-100"]
    hraw --> hclp["Clamp to 0-100"]

    subgraph TECH["Technical severity: handed in, never asked"]
        pick["One source's CVSS base score,<br/>chosen by the caller and attributed"] --> tsc["On the 0-100 scale<br/>base score x 10"]
        nosrc["No source scored this finding<br/>kept as its own answer, with a reason"] --> tzero["Contributes 0"]
    end

    tsc --> tw["Multiply by 0.30"]
    tzero --> tw
    eclp --> ew["Multiply by 0.25"]
    bclp --> bw["Multiply by 0.25"]
    hclp --> hw["Multiply by 0.20"]

    tw --> total["Sum, to two decimals<br/>organisation_risk_score, 0-100"]
    ew --> total
    bw --> total
    hw --> total

    total --> bnd["Band by threshold<br/>Low, Medium, High, Critical"]

    ans --> unk{"Any answer Unknown,<br/>or no source scored it?"}
    nosrc --> unk
    unk -->|"yes"| prov["Provisional and flagged,<br/>naming the questions"]
    unk -->|"no"| firm["Settled"]

    bnd --> res["Result"]
    prov --> res
    firm --> res
```

The clamp sits **before** the weighting, and that ordering is the whole reason
the box is drawn separately. A category full of strong controls stops at 0; an
unclamped one would go negative and buy down the other three. A control reduces
risk in its own category and no further.

**Technical severity has no question path**, and the missing arrow is the point.
The other three categories are asked; this one is handed in, as a number with
the source it came from. Choosing which source's CVSS score to use is the
council's job and the council does not exist, so the engine refuses to reach
into a finding and pick one — and it refuses an unattributed number outright,
because that is the merge the design forbids arriving by the back door.

The provisional branch has **two ways in**, not one. An Unknown answer is the
first. A finding nobody scored is the second: it contributes 0 to the weighted
sum, which is arithmetic and not a judgement that the flaw is harmless, and it
flags the whole score the same way an Unknown answer does. Neither is ever read
as No, and neither refuses the calculation.

What this does not show: the weight each individual question carries, and the
band boundaries. Those are tables in `docs/SCORING_MODEL.md`; that file also
records where the source document contradicts itself on the category weights
and why 30/25/25/20 is the one to use.

## 4. The assessor council

**Built, except the hosted client.** `src/council/` is the roster and its gate,
the redaction, the prompt, the local Ollama client, the quotation check, the
chairman and the runner; `src/cvss` is the engine below. Nothing reaches a
hosted member, and no escalation policy re-asks a contested metric.

```mermaid
flowchart TD
    raw["Advisory text, as the database carries it"] --> red["Redaction<br/>CVE and GHSA ids and vector strings<br/>replaced by markers, not deleted"]
    red --> shown["The text a member sees<br/>no id, no published scores,<br/>no other member's answer"]

    subgraph ROSTER["The roster: n members, added and removed by the operator"]
        subgraph LOCALM["Local: Ollama on this machine"]
            m1["Member 1, local"]
            m2["Member 2, local"]
            mdot["... to member n"]
        end
        subgraph HOSTM["Hosted: opt in per member, off by default"]
            h1["Member k, hosted"]
        end
    end

    shown --> m1
    shown --> m2
    shown --> mdot
    h1 --> skip["Skipped, with the reason:<br/>egress not opted in,<br/>or no client exists to reach it"]

    m1 --> rep{"What came back?"}
    m2 --> rep
    mdot --> rep
    rep -->|"a value and a quotation"| qc["Quotation check in application code<br/>against the text the member saw<br/>the same check for every member"]
    rep -->|"no evidence found"| abs["An absence:<br/>a fact about the advisory"]
    rep -->|"a value it cannot quote"| gue["A guess:<br/>a fact about the member"]

    qc --> chr["Chairman reconciles<br/>the verified answers alone<br/>values are counted, members never"]
    abs -. "no weight" .-> chr
    gue -. "no weight" .-> chr

    chr --> st{"What do the verified<br/>answers support?"}
    st -->|"one value"| vec["One agreed vector<br/>plus rationale plus confidence"]
    st -->|"more than one value"| pol["Contested, and recorded as contested<br/>no policy re-asks it yet"]
    st -->|"nothing verified"| fbk["Unresolved: fall back to a published<br/>vector and record which source"]
    fbk --> vec

    subgraph DETERM["Engine: the only place a number appears"]
        eng["Published CVSS equations<br/>deterministic, no model"]
        eng --> num["The score"]
    end

    vec --> eng
    num --> hmn["Human approves or overrides"]

    rec["Record: every member and its provider,<br/>every skip and its reason, every guess,<br/>what the chairman decided from, and the vector"]
    chr -.-> rec
    skip -.-> rec
```

One line crosses from the roster into the engine, and it carries **a vector, not
a number**. That is the boundary made visible: everything above the engine is a
reading of text, everything numeric happens below it, and a model that emitted
7.4 directly would be unauditable. Adding members, or hosting them elsewhere,
does not move that line.

**No edge reaches the hosted box, and that is the state of the code rather than
a rule.** Two independent things stop the text: `egress` is off unless the
operator opts the member in, and no client exists to reach a hosted model even
when they do. The gate is built and tested; what it guards is not. The day an
OpenRouter client lands, one of those two reasons disappears and `egress`
becomes the only thing between an advisory and the network — which is worth
knowing before that day, not after.

Redaction is a step, not a request. The ids and vector strings are taken out of
the text before any member sees it, because a sentence in a prompt cannot make a
model unsee `CVE-2021-44228`. The same redacted text is what the quotation check
reads: checking against the original would fail every quotation spanning a
marker and report an absence the advisory never had.

Three replies, three shapes, and only one of them can decide anything. A value
with a quotation goes to the check; an absence and a guess are recorded and
weigh nothing. They are kept apart because an absence is a fact about the
advisory and a guess is a fact about the member — and a model asked about a
metric its text is silent on tends to guess rather than decline, so the two get
mixed by any design that folds them together.

Members are a panel and not a chain. Each sees the advisory text alone, so the
answers are independent and can be measured. Nothing counts them, so an even
roster raises no tie — four answers are four pieces of evidence. The chairman
keeps the ones whose quotation verifies and asks whether they point at one value
or several; unanimity with nothing verified settles nothing.

The hosted box will cost reproducibility. A local member takes a pinned model; a
hosted one takes no seed, and the weights behind its name change without notice.
A run holding one could not be repeated, so the vector would stop being
re-derivable — while the engine below stays deterministic, and the recorded
vector still re-derives the recorded number.

What this does not show: the shape of the roster file, which is a sketch in
`docs/COUNCIL.md` rather than a committed format; the arithmetic of cost, which
is n × findings × metrics and is settled before a scan; and what puts an advisory
to the council in the first place, because nothing does yet.

## 5. Build status

```mermaid
flowchart LR
    subgraph BUILT["Built: source with tests beside it"]
        b0["src/deps/scanner<br/>run an external tool, read its JSON,<br/>refuse what it cannot identify"]
        b1["src/deps/syft_runner<br/>the components a directory declares"]
        b2["src/deps/trivy_runner<br/>advisories per purl,<br/>one published vector per source"]
        b3["src/deps/trivy_database<br/>the database's own build date"]
        b4["src/cvss<br/>vector parser, metric vocabulary,<br/>Base score equations"]
        b5["src/findings<br/>the join, and every source's<br/>score kept apart from the others"]
        b6["src/scoring<br/>per-question weights, categories<br/>clamped then weighted, and the band"]
        b7["src/council<br/>roster and the egress gate, redaction, prompt,<br/>provider registry holding one local client,<br/>quotation check, chairman, runner"]
        b0 --> b1
        b0 --> b2
        b1 --> b5
        b2 --> b5
        b4 --> b5
        b4 --> b7
    end

    subgraph UNBUILT["Designed, not built: no source file"]
        d1["Question template library"]
        d2["Question selector"]
        d3["Answer validation"]
        d6["Hosted provider client<br/>an adapter, and an entry in<br/>the provider registry"]
        d10["Orchestration<br/>nothing puts an advisory to the council,<br/>and nothing takes back its vector"]
        d11["Escalation policy<br/>nothing re-asks a contested metric"]
        d7["Report"]
        d8["CLI"]
        d9["Web UI"]
    end

    b5 -- "a finding exists,<br/>nothing yet reads or judges it" --> d1
    d1 -- "and the engine waits on<br/>questions nobody has written" --> b6
    b5 --> d10
    d10 --> b7
    b7 --> d11
    d6 --> b7

    subgraph REAL["Real today, but not this project's code"]
        x1["CLAUDE.md, the binding rules"]
        x2["docs/: the scoring model, the council, the README, this page"]
        x3["Six agent definitions in .claude/agents/"]
        x4["Syft, Trivy, Ollama and a downloaded advisory DB"]
    end
```

**Three islands, and nothing between them.** A repository becomes a list of
findings, each carrying every source's published vector, parsed and scored, and
there it stops. The scoring engine is built and idle: it weighs answers to
questions nobody has written. The council is built and idle for a third reason:
nothing selects a finding to put to it, and nothing takes back the vector it
hands over.

The only arrows inside the built column are real imports. `src/cvss` is imported
by `src/findings` and by `src/council`, and that is the whole of it — nothing
else in that column depends on anything else in it. In particular no arrow runs
from `src/findings` to `src/scoring`, or from `src/council` to either: which
source's CVSS score becomes the technical severity is the council's call, and
who puts the council's answer where is a component nobody has written. Drawing
those edges would draw the design rather than the code.

The council is the one box in the built column that is built **except** for a
piece of itself. Its local client works and its `egress` gate is enforced, and
the hosted client that gate exists to guard does not exist — which is why the
hosted provider client has a box of its own on the other side, and an edge back
into the registry it would be registered in. That edge is a seam in the code and
not a wish: the provider layer is separate from the dispatch beside it precisely
because a new client changes one and not the other.

The third column is there so the page is not read as claiming the rest is
absent: the rules, the design documents and the agent definitions are written,
and the third-party tools are installed. None of that is code this project
wrote.

What this does not show: an order of work for the middle column. Nothing here
says which component is built next, and no such plan exists. That column is also
not evenly documented — the escalation policy and the hosted client are
described in `docs/COUNCIL.md`, while `Report`, `CLI` and `Web UI` appear only as
a remit in an agent definition, and no provider has been committed to beyond
Ollama.

## Keeping this page true

The check is rule 19, and it is cheap to run against a change:

| The change | This page |
|---|---|
| a new component, or one deleted | the diagram it appears in, same change |
| a flow that now runs in a different order | the diagram it appears in, same change |
| a component moves from designed to built | diagram 5 moves it, same change |
| prose, tests, or a rename with no flow change | unchanged, and the report says so |

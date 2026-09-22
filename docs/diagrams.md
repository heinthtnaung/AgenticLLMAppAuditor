# Diagrams

The one page to read to understand the system.

**Nothing drawn here is built.** There is no `src/`, no tests, no CLI, no Python
file of any kind. Every box below is a component the project has decided to
build, not a component you can run. Diagram 5 is about nothing else.

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
| 2 | The two scores | who produces which number, and why they stay apart |
| 3 | The Organisation Risk Score | how answers become a 0–100 score and a band |
| 4 | The assessor council | how a roster of n local and hosted models settles a metric without emitting a number |
| 5 | Build status | what is designed against what exists |

## 1. The audit pipeline

**Designed, not built.**

```mermaid
flowchart TD
    subgraph OOB["Out of band, before any scan"]
        fetch["Operator downloads the Trivy vulnerability DB"] --> adb[("Pinned advisory database<br/>on local disk")]
    end

    subgraph SCAN["The scan: offline, against the pinned database"]
        repo["Repository under audit"] --> disc["Manifest discovery<br/>lockfiles and dependency manifests"]
        disc --> syft["Syft builds the SBOM"]
        syft --> sbom[("SBOM<br/>component and version")]
        sbom --> join["Trivy joins components to advisories"]
        join --> fin["Findings<br/>component, version, CVE,<br/>published vectors, often several<br/>from sources that disagree"]
    end

    adb --> join

    fin --> calc["CVSS calculator<br/>published v3.1 equations"]
    fin --> ctx["Organisation context<br/>diagram 3"]
    calc --> rep["Report<br/>one row per finding"]
    ctx --> rep
    rep --> hum["Human reviews"]
```

The database is fetched out of band so that a scan runs offline against a
pinned version. That is what a reproducible scan rests on: the same commit and
the same database are meant to produce the same findings.

That choice has a cost, and it is the sharpest edge in this diagram: **an empty
or stale cache produces a clean report rather than an error.** Trivy finds no
advisories, reports nothing, and exits 0. The check on the database belongs
before the scan, not after reading the report.

What this does not show: how findings are stored, how a repeat scan is diffed
against the last one, or what the report is — file, page, or both. None of that
is decided.

## 2. The two scores

**Designed, not built.**

```mermaid
flowchart TD
    subgraph QUOTED["Role 1: NVD and the vendor. Quoted, never recomputed"]
        nvd["NVD record"]
        ven["Vendor advisory"]
    end

    subgraph MODEL["Role 2: the LLM. Reads text, produces no number"]
        anl["Analyst: exploit prerequisites"]
        sel["Selector: questions from the approved library"]
        chk["Checker: incomplete or contradictory answers"]
        exl["Explainer: the rationale"]
    end

    subgraph ENGINE["Role 3: the engine. Every number, deterministic"]
        val["Validate model output<br/>typed structure, refused if it does not fit"]
        cal["Weighted calculation<br/>no model in the path"]
    end

    subgraph HUMAN["Role 4: the human. The decision"]
        dec["Approve or override"]
    end

    nvd --> anl
    ven --> anl
    anl --> sel
    sel --> ans["Organisation answers<br/>Yes / No / Unknown / N/A"]
    ans --> chk
    chk --> val
    anl --> val
    val --> cal
    cal --> f3["organisation_risk_score"]
    cal --> exl
    exl --> f4["llm_explanation"]
    nvd --> f1["nvd_cvss_base_score"]
    ven --> f2["vendor_cvss_score"]
    f1 --> out["Report: four fields, side by side"]
    f2 --> out
    f3 --> out
    f4 --> out
    out --> dec

    f1 x-. "never merged into one number" .-x f3
```

Four fields, four owners. The crossed dotted line is the rule the rest of the
design hangs on: **a blended number is unattributable**, so the published
severity and this environment's assessment stay in separate fields and separate
columns. A CVE that is CVSS Critical and organisation Low is the normal case.

The `validate` box is the boundary, not a formality. Model output reaches the
engine only as a typed structure that application code has already refused or
accepted. A reply that arrives unchecked is the model deciding a number by the
back door.

What this does not show: the field names are from `docs/SCORING_MODEL.md` and
no schema exists yet, so nothing here has been fixed in code.

## 3. The Organisation Risk Score

**Designed, not built.**

```mermaid
flowchart LR
    cve["CVE and advisory"] --> pre["Exploit prerequisites"]
    pre --> qs["Questions selected<br/>approved template library only"]
    qs --> ans["Answers<br/>Yes / No / Unknown / N/A"]

    ans --> wgt["Per question weight<br/>Yes is worth a different amount per question<br/>a compensating control subtracts"]

    wgt --> traw["Technical severity, raw"]
    wgt --> eraw["Exposure and reachability, raw"]
    wgt --> braw["Business impact, raw"]
    wgt --> hraw["Threat and exploitation, raw"]

    traw --> tclp["Clamp to 0-100"]
    eraw --> eclp["Clamp to 0-100"]
    braw --> bclp["Clamp to 0-100"]
    hraw --> hclp["Clamp to 0-100"]

    tclp --> tw["Multiply by 0.30"]
    eclp --> ew["Multiply by 0.25"]
    bclp --> bw["Multiply by 0.25"]
    hclp --> hw["Multiply by 0.20"]

    tw --> sum["Sum<br/>organisation_risk_score, 0-100"]
    ew --> sum
    bw --> sum
    hw --> sum

    sum --> bnd["Band by threshold<br/>Low, Medium, High, Critical"]

    ans --> unk{"Any answer Unknown?"}
    unk -->|"yes"| prov["Provisional and flagged"]
    unk -->|"no"| firm["Settled"]

    bnd --> res["Result"]
    prov --> res
    firm --> res
```

The clamp sits **before** the weighting, and that ordering is the whole reason
the box is drawn separately. A category full of strong controls stops at 0; an
unclamped one would go negative and buy down the other three. A control reduces
risk in its own category and no further.

The Unknown branch is a second thing the picture insists on. An Unknown answer
produces a score that is calculated and flagged. It is never silently read as
No, and the calculation is never refused.

What this does not show: the weight each individual question carries, and the
band boundaries. Those are tables in `docs/SCORING_MODEL.md`; that file also
records where the source document contradicts itself on the category weights
and why 30/25/25/20 is the one to use.

## 4. The assessor council

**Designed, not built.**

```mermaid
flowchart TD
    adv["Advisory text only<br/>no CVE id, no published scores,<br/>no other member's answer"]

    subgraph ROSTER["The roster: n members, added and removed by the operator"]
        subgraph LOCALM["Local: Ollama on this machine"]
            m1["Member 1, local<br/>pinned digest, temperature 0, seed"]
            m2["Member 2, local"]
            mdot["... to member n"]
        end
        subgraph HOSTM["Hosted: OpenRouter or another API<br/>opt in per member, off by default"]
            h1["Member k, hosted<br/>no seed, weights change without notice"]
        end
    end

    adv --> m1
    adv --> m2
    adv --> mdot
    adv -- "the advisory text leaves this machine" --> h1

    qc["Quotation check in application code<br/>the same check for every member<br/>does the evidence appear in the text given?"]
    m1 --> qc
    m2 --> qc
    mdot --> qc
    h1 --> qc

    qc --> chr["Chairman reconciles<br/>evidence decides, never a count"]
    chr --> st{"Per metric outcome"}
    st -->|"agreed or evidence wins"| vec["One agreed vector<br/>plus rationale plus confidence"]
    st -->|"contested"| pol["Escalation policy<br/>re-ask that metric alone<br/>on a costlier member"]
    st -->|"no member found evidence"| fbk["Unresolved: fall back to a published<br/>vector and record which source"]
    pol --> chr
    fbk --> vec

    subgraph DETERM["Engine: the only place a number appears"]
        eng["Published CVSS equations<br/>deterministic, no model"]
        eng --> num["The score"]
    end

    vec --> eng
    num --> hmn["Human approves or overrides"]

    rec["Record: every member and its provider,<br/>local or hosted, the roster as configured,<br/>and whether the run was reproducible"]
    chr -.-> rec
```

One line crosses from the roster into the engine, and it carries **a vector, not
a number**. That is the boundary made visible: everything above the engine is a
reading of text, everything numeric happens below it, and a model that emitted
7.4 directly would be unauditable. Adding members, or hosting them elsewhere,
does not move that line.

The roster is n members and the operator sets n. Local and hosted members sit
side by side, return the same fields, and meet the same quotation check. What
separates them is a boundary, not a rank: the labelled edge into the hosted box
is the advisory text leaving this machine, and that edge is opt-in per member.

Members are a panel and not a chain. Each sees the advisory text alone, so the
answers are independent and can be measured. Nothing counts them, so an even
roster raises no tie — four answers are four pieces of evidence, and the
chairman ranks them by whether the quotation verifies.

The hosted box costs reproducibility. A local member takes a seed; a hosted one
does not, and the weights behind its name change without notice. A run holding
one cannot be repeated, so the vector stops being re-derivable — while the
engine below stays deterministic, and the recorded vector still re-derives the
recorded number.

What this does not show: the shape of the roster file, which is a sketch in
`docs/COUNCIL.md` rather than a committed format, and the arithmetic of cost,
which is n × findings × metrics and is settled before a scan rather than during
it.

## 5. Build status

```mermaid
flowchart LR
    subgraph DESIGNED["Designed: described on these pages"]
        d1["Manifest discovery"]
        d2["SBOM build"]
        d3["Advisory join"]
        d4["CVSS v3.1 calculator"]
        d5["Question template library"]
        d6["Question selector"]
        d7["Answer validation"]
        d8["Organisation Risk Score engine"]
        d9["Assessor council, roster and chairman"]
        d10["Model provider clients, local and hosted"]
        d11["Report"]
        d12["Web UI"]
    end

    subgraph BUILT["Built: source in this repository"]
        non["Nothing. No source file of any kind"]
    end

    d1 --> non
    d2 --> non
    d3 --> non
    d4 --> non
    d5 --> non
    d6 --> non
    d7 --> non
    d8 --> non
    d9 --> non
    d10 --> non
    d11 --> non
    d12 --> non

    subgraph REAL["Real today, but not this project's code"]
        x1["CLAUDE.md, the binding rules"]
        x2["docs/SCORING_MODEL.md and docs/COUNCIL.md"]
        x3["README.md and this page"]
        x4["Six agent definitions in .claude/agents/"]
        x5["Syft, Trivy, Ollama and a pinned DB on the machine"]
    end
```

Every designed component converges on the same implementation, and that is the
point of the picture: twelve arrows, one destination, and the destination is
empty. The third column is there so the page is not read as claiming the
repository is bare — the rules, the design documents and the agent definitions
are written, and the third-party tools are installed. None of that is code this
project wrote.

What this does not show: an order of work. Nothing here says which component is
built first, and no such plan exists yet. The left column is also not evenly
documented — the pipeline, the scoring engine and the council have design pages
behind them, while `Report` and `Web UI` appear only as a remit in an agent
definition. The provider clients are named in `docs/COUNCIL.md` only as a
configuration sketch, and no provider has been committed to beyond Ollama.

## Keeping this page true

The check is rule 19, and it is cheap to run against a change:

| The change | This page |
|---|---|
| a new component, or one deleted | the diagram it appears in, same change |
| a flow that now runs in a different order | the diagram it appears in, same change |
| the first source file lands | diagram 5 stops saying nothing |
| prose, tests, or a rename with no flow change | unchanged, and the report says so |

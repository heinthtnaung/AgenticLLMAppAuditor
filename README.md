# AgenticLLMAppAuditor

An SBOM-based vulnerability auditor. Build a bill of materials for a
repository, join it to a pinned advisory database, score each finding by the
published CVSS v3.1 equations, and add an **Organisation Risk Score** that
reflects the environment the code is deployed into.

A council of models — local today, hosted once a client for one exists — reads
advisories and agrees one vector, each member quoting the text it relied on. A
deterministic engine turns that vector into every number. The two are never the
same step.

## Status

**Partly built, in three pieces that nothing joins.** A repository becomes a
list of findings, each carrying every source's published vector, parsed and
scored. A council of local models reads an advisory and agrees a vector. Answers
about an environment become an Organisation Risk Score. No component puts a
finding to the council, takes back its vector, asks the organisation anything,
or prints a report.

| Part | State | What it is |
|---|---|---|
| `src/deps/` | built | Syft and Trivy: the components a directory declares, the advisories published against them, and the database's own build date |
| `src/cvss/` | built | a CVSS Base vector parsed and validated, and its score by the published equations |
| `src/findings/` | built | the join — a CVE affecting an installed component, with every source's score kept apart and attributed |
| `src/scoring/` | built | the Organisation Risk Score: per-question weights, categories clamped then weighted, and the band |
| `src/council/` | built | the roster and its `egress` gate, redaction, the prompt, a provider registry holding one local Ollama client, the quotation check, the chairman and the runner |
| hosted provider client | design | the local client works; nothing reaches OpenRouter or another API, so a hosted member is skipped for want of one. An adapter and a registry entry, and no other module moves |
| escalation policy | design | a contested metric is recorded as contested and nothing re-asks it on a costlier member |
| question library, selector | design | there are no approved questions to ask yet |
| report, CLI, web page | design | no entry point exists, so no audit runs end to end |

Diagram 5 of [`docs/diagrams.md`](docs/diagrams.md) draws the same boundary.
The three built pieces import nothing from each other — only `src/cvss`, which
two of them share — so what is missing is not glue but the components between
them.

### Running it

**There is still no command that audits a repository.** Nothing in `src/` has an
entry point — the packages import, and none of them is a front door. This README
gets a usage section when an audit can be run from a command line and its output
pasted here.

What runs today is the suite. `pytest` is the only dependency — the runtime is
standard library:

```bash
pip install -r requirements.txt
python -m pytest -q
```

No count is pasted here: the suite grows with every module that lands, so any
number written down is wrong within the day.

## The design in brief

Four roles, and the boundaries between them are the design:

| Who | What they produce |
|---|---|
| the advisory sources | one published vector each — quoted, attributed, never edited |
| the LLM | contextual analysis: exploit prerequisites, question selection, the rationale |
| the scoring engine | every number, deterministically, with no model in the path — each source's CVSS score and the Organisation Risk Score |
| the human | approval or override |

There is no single published score. Several sources assess the same CVE and
they disagree often; none of them is the reference the others are measured
against, so each keeps its own field. Those and the Organisation Risk Score are
never blended. A CVE can be CVSS Critical and organisation Low — that is the
point of the exercise, not an error to reconcile.

The organisation score weights four categories on a 0–100 scale: technical
severity 30%, exposure and reachability 25%, business impact 25%, threat and
exploitation 20%.

The model may not determine a score, change a weight, override an escalation
rule, or approve a risk decision. Each of those is a refusal in application
code, not a line in a prompt.

Read [`docs/SCORING_MODEL.md`](docs/SCORING_MODEL.md) for the scoring design
and [`docs/COUNCIL.md`](docs/COUNCIL.md) for how several models assess one CVE
without any of them producing a number.

## Prerequisites

What a scan shells out to. Versions are what is installed on the development
machine, not minimums except where stated.

| Tool | Version here | For |
|---|---|---|
| Python | 3.11.11 (3.10+) | the engine and the tests |
| git | 2.43.0 | cloning the repositories under audit |
| Syft | 1.52.0 | building the SBOM |
| Trivy | 0.74.0 | the advisory database and the CVE join |
| Ollama | 0.34.2 | the local analyst model |

### The advisory database is a separate step

```bash
trivy image --download-db-only
```

```
2026-09-22T12:06:33+08:00	INFO	[vulndb] Need to update DB
2026-09-22T12:06:33+08:00	INFO	[vulndb] Downloading vulnerability DB...
2026-09-22T12:06:33+08:00	INFO	[vulndb] Downloading artifact...	repo="mirror.gcr.io/aquasec/trivy-db:2"
2026-09-22T12:06:38+08:00	INFO	[vulndb] Artifact successfully downloaded	repo="mirror.gcr.io/aquasec/trivy-db:2"
```

Progress bar elided. The download is 116 MiB and lands in `~/.cache/trivy`.

It is a separate step because scans will run offline, with
`--skip-db-update`, so that a scan is reproducible and pinned to a known
database. The cost of that choice: **an empty or stale cache produces a clean
report rather than an error.** Trivy finds no advisories, reports no
vulnerabilities, exits 0, and nothing in the output says the database was
missing. Every CVE is missed silently.

So check the database before trusting a scan:

```bash
trivy version
```

```
Version: 0.74.0
Vulnerability DB:
  Version: 2
  UpdatedAt: 2026-09-22 02:00:05.774028462 +0000 UTC
  NextUpdate: 2026-09-23 02:00:05.774027771 +0000 UTC
  DownloadedAt: 2026-09-22 04:06:38.609232067 +0000 UTC
```

## The proxy on this machine

A corporate HTTP proxy is set, and the two cases pull in opposite directions.

| Talking to | Proxy |
|---|---|
| a local service — Ollama, a dev server, anything on loopback | **off** |
| the internet — `git clone`, `trivy image --download-db-only` | **on** |

Before running anything that talks to a local service:

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
```

Without it, `urllib` sends loopback requests to the proxy, which answers 502.
The failure reads as the local service being down, which sends you looking in
the wrong place. `CLAUDE.md` carries the same note.

## Working on it

`CLAUDE.md` is binding. Work that breaks one of its rules is not done. Read it
before writing anything; it is short.

Six agents are defined in `.claude/agents/`:

| Agent | For |
|---|---|
| `python-developer` | the deterministic half — parsers, data models, CLI, the scoring engine |
| `ai-engineer` | prompts, the Ollama client, parsing model replies, measuring whether a model is any good |
| `frontend-developer` | the browser-facing JavaScript — components, state, styling, the build |
| `tester` | writes tests, runs the suite, reproduces bugs |
| `technical-writer` | this README, `docs/*.md`, docstrings, design records |
| `judge` | reviews finished work against `CLAUDE.md`; read-only, and it never edits |

Where an agent's instructions disagree with `docs/SCORING_MODEL.md`, the
design document wins.

## Repository layout

```
.
├── CLAUDE.md                 the binding rules
├── README.md                 this file
├── LICENSE                   MIT
├── .gitignore
├── pytest.ini                src on the path, tests under tests/
├── requirements.txt          pytest; the runtime is standard library
├── .claude/
│   └── agents/               six agent definitions
├── docs/
│   ├── SCORING_MODEL.md      the Organisation Risk Score
│   ├── COUNCIL.md            the assessor council
│   ├── diagrams.md           every flow, as diagrams
│   └── sources/              the two documents the design was read from
├── src/
│   ├── council/              the roster, redaction, the providers, the chairman
│   ├── cvss/                 vector parser, metric vocabulary, Base score
│   ├── deps/                 the Syft and Trivy runners, the database's build date
│   ├── findings/             the join, and every source's score kept apart
│   └── scoring/              the Organisation Risk Score engine
└── tests/                    mirrors src/, a test module per source module
```

`fetched/` and `artifacts/` are ignored: a repository under audit is an argument,
never this project's evidence, and so is what a run writes.

## Licence

MIT. See [`LICENSE`](LICENSE).

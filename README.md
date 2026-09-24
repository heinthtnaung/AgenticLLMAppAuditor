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

**It runs end to end.** A repository on disk becomes a report: components
catalogued, advisories joined, every source's published vector scored and kept
attributed, a council of local models asked if you name one, and every finding
weighed against your environment into an Organisation Risk Score if you answer
the approved questions. The two optional halves are named as absent when you
leave them out — `NOT ASSESSED`, never a zero and never an omission.

| Part | State | What it is |
|---|---|---|
| `src/deps/` | built | Syft and Trivy: the components a directory declares, the advisories published against them, and the database's own build date |
| `src/cvss/` | built | a CVSS Base vector parsed and validated, and its score by the published equations |
| `src/findings/` | built | the join — a CVE affecting an installed component, with every source's score kept apart and attributed |
| `src/scoring/` | built | the approved question library, per-question weights, categories clamped then weighted, and the band |
| `src/council/` | built | the roster and its `egress` gate, redaction, the prompt, a provider registry holding one local Ollama client, the quotation check, the chairman and the runner |
| `src/organisation/` | built | the answer file, the approval record, and one risk score per published source |
| `src/report/` | built | the record every run produces, and its three renderings: a terminal report, the JSON audit artefact, and one self-contained HTML page |
| `src/cli/` | built | the arguments, the preflight refusals, the order the packages run in, which findings the council is put to, the progress it prints to stderr, the three report files in `reports/`, and the exit code |
| question selector | design | every approved question is asked, rather than the few a CVE's prerequisites call for |
| answer validation | design | no model reads the answers back for gaps or contradictions |
| hosted provider client | design | the local client works; nothing reaches OpenRouter or another API, so a hosted member is skipped for want of one. An adapter and a registry entry, and no other module moves |
| escalation policy | design | a contested metric is recorded as contested and nothing re-asks it on a costlier member |
| an approval command | design | an approval is recorded, never stamped: the time arrives with it in the answer file, because there is no clock anywhere in `src/` |

Diagram 5 of [`docs/diagrams.md`](docs/diagrams.md) draws the same boundary from
the import graph. Nothing built is unreachable any more: `src/organisation`
imports the scoring engine, and `src/cli` reaches six packages to close the line
from a directory on disk to a banded score.

## Usage

Install it once into a virtual environment, and it is the `audit` command. The
repository being audited is an argument and already on disk — this tool never
clones one. A run prints the report and saves it in three formats into
`reports/`.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
audit fetched/vulnscout
```

The install fetches a build backend, so it needs the corporate proxy **on**,
like `git clone`. `-e` installs in place, so an edit to `src/` takes effect
without reinstalling. Uninstalled, `PYTHONPATH=src python -m cli.main` runs the
same code and prints the same report.

<!-- readme-check: run (elided) -->
```
Audit of fetched/vulnscout
  syft 1.52.0  ·  trivy 0.74.0  ·  advisory database built 2026-09-22T02:00:05.774028462Z

18 findings across 60 components. 5 carry sources that disagree.

SOURCES DISAGREE (5)
  CVE-2025-13465  lodash-es 4.17.21
    2.9 apart  ·  High and Medium  ·  differ on A
    ghsa 6.5  ·  nvd 5.3  ·  redhat 8.2
  CVE-2021-4279   fast-json-patch 2.2.1
    2.5 apart  ·  Critical and High  ·  differ on C, I, A
    ghsa 7.3  ·  nvd 9.8

SOURCES AGREE (13)
  CVE-2026-14257       brace-expansion 1.1.14          7.5  High      2 sources
  CVE-2026-53550       js-yaml 3.14.2                  5.3  Medium    2 sources

MATCHED NOTHING
  55 components carry no advisory
  0 advisories matched no component

NOT ASSESSED
  Organisation Risk Score
    no organisation answers were supplied, so no environment was weighed
  Approval record
    no answer file was given, so nobody was asked about this environment
  Council ruling
    no council assessed this run, so no source has been chosen between
```

Three of the five disagreements and eleven of the thirteen agreements are elided
above; everything else is verbatim.

### Three formats, one record, three files

Every run saves the report in all three formats into `reports/`, in the
directory the command ran from. Each file is named after the repository's
directory, so the run above, from the project root, leaves:

| File | `--format` | What it is |
|---|---|---|
| `reports/vulnscout.txt` | `text` | the block above, and the default |
| `reports/vulnscout.json` | `json` | the audit artefact, for a pipeline or `jq` |
| `reports/vulnscout.html` | `html` | one page to open in a browser |

To read the page, open `reports/vulnscout.html` in a browser; it needs no second
run. `--format` picks only which of the three is printed on stdout, and the file
of that format is byte for byte what was printed. After the report, one line on
stderr says where the three went:
`reports written to reports/vulnscout.txt, reports/vulnscout.json, reports/vulnscout.html`.

**No time goes in a name**, because `src/` reads no clock. A second run of the
same repository overwrites its three files, so copy out of `reports/` any run you
mean to keep. Two repositories with the same directory name, `a/app` and
`b/app`, write the same three files, and the later run replaces the earlier.

The folder is checked before the scan. A file where `reports/` should be, a
folder this run cannot write into, or a report there it cannot replace, exits
`2` with `audit: <reason>` and nothing is scanned, because a council run is too
long to lose to a folder.

A write that fails after the scan exits `2` too, with the record already on
stdout. The files are written one at a time, `.txt`, `.json`, then `.html`, so
the ones before the file it names hold this run and the ones after it still hold
the last run's, or are missing if there was none, under the same names and with
nothing marking which is stale. The named file itself may be empty or cut short.
Rerun once the fault is fixed.

All three render the same record and none of them works a number out, so a
figure cannot differ between them. The HTML page fetches nothing — the
stylesheet is inlined and there is no script, no font, no image and no link out
— because a scan runs behind the corporate proxy and the report is opened from
disk. A page that fetched its stylesheet would arrive unreadable in the
environment it was made for.

What HTML costs is comparison. Text and JSON both read line by line, so two runs
diff; a styling change rewrites an HTML file the whole way down, which is why
`json` stays the format to keep.

**It is a page, not an application.** Nothing is served and nothing is
interactive; there is no JavaScript and no build step. The browser-facing half
`frontend-developer` exists for is unwritten, and it has no box in diagram 5
because nothing has designed it either.

### Scoring a finding against your environment

A scanner cannot tell whether a vulnerable component is exposed, or whether it
matters. `--answers` supplies that half, as a JSON file answering the **approved
question library** by question id. [`answers.example.json`](answers.example.json)
is a runnable skeleton: every question answered `No`, with the question text
beside each id so you do not have to look them up.

Filled in for an internet-facing, business-critical asset:

<!-- readme-check: answers -->
```json
{
  "answers": {
    "EXP-1": "Yes", "EXP-2": "Yes", "EXP-3": "Yes", "EXP-4": "No", "EXP-5": "No",
    "BUS-1": "Yes", "BUS-2": "Yes", "BUS-3": "Yes", "BUS-4": "Yes",
    "THR-1": "No",  "THR-2": "No",  "THR-3": "No"
  },
  "by_advisory": {
    "CVE-2021-4279": {"THR-1": "Yes", "THR-2": "Yes"}
  },
  "approval": {
    "approver": "Hein",
    "decision": "approved",
    "recorded_at": "2026-09-23T09:15:00Z",
    "note": "reviewed against the staging inventory"
  }
}
```

`answers` applies to every finding and `by_advisory` overrides it for one, which
is what threat needs: whether *this* vulnerability is exploited in the wild is a
fact about the vulnerability, not about your network. An override naming an
advisory the scan did not find is reported under `MATCHED NOTHING` rather than
ignored, because a mistyped id would otherwise drop that finding's band in
silence. **Every approved question
must be answered** — a missing one is refused by name, because scoring it as `No`
would quietly move a band. Every answer is `Yes`, `No`, `Unknown` or `N/A`, and
**Unknown is never read as No**: it is carried through and every score it touches
comes out marked provisional. `approval` is optional, and its timestamp is part
of the human act, so you write it rather than the tool stamping it.

```bash
audit fetched/vulnscout --answers answers.json
```

<!-- readme-check: run --answers -->
```
ORGANISATION RISK (18)  ·  the source changes the band on 1
  weighted Technical severity 0.3, Exposure and reachability 0.25, Business impact 0.25, Threat and exploitation 0.2
  CVE-2026-4800        ghsa 70.5 to nvd 75.7       Critical and High
  CVE-2021-4279        ghsa 84.2 to nvd 91.7       Critical
  CVE-2025-13465       nvd 62.1 to redhat 70.8     High
  CVE-2026-13149       ghsa 62.1 to redhat 68.8    High
  CVE-2026-13676       68.8                        High
  CVE-2026-14257       68.8                        High
```

The second line is the weighting those totals were reached with. It is read off
the record rather than off `docs/SCORING_MODEL.md`, so a reader re-deriving a
score by hand works from the run that produced it and not from a table that
could have moved since.

`CVE-2021-4279` is at the top because it is the one finding the `by_advisory`
block says is being exploited in the wild with public exploit code. Take those
two answers away and it scores like its neighbours.

**Read the range, not the number.** A finding is scored once per published
source, because picking one would decide which source wins and that is left
open. Each end of a range names the source that produced it: `CVE-2026-4800` is
8.1 to GHSA and 9.8 to NVD, which here is `ghsa 70.5 to nvd 75.7` — High by one
reading and Critical by the other, and the heading says the source changes the
band on one finding. Everywhere else it does not: `CVE-2025-13465`'s sources are
2.9 apart on the CVSS scale and both ends land in High, which is their
disagreement ceasing to matter in this environment. That is the question a range
answers and a single number cannot.

A row with one figure and no source, like `CVE-2026-13676` at `68.8`, is a
finding whose sources agree — there is nothing to attribute between, so nothing
is named.

**The environment drives those numbers, not the CVE.** The same file with
`EXP-1` set to `No` and `EXP-4` to `Yes` — the asset segmented rather than
internet-facing, nothing else touched:

<!-- readme-check: run --answers EXP-1=No EXP-4=Yes -->
```
ORGANISATION RISK (18)  ·  the source changes the band on 4
  weighted Technical severity 0.3, Exposure and reachability 0.25, Business impact 0.25, Threat and exploitation 0.2
  CVE-2021-4279        ghsa 70.4 to nvd 77.9       Critical and High
  CVE-2025-13465       nvd 48.4 to redhat 57.1     High and Medium
  CVE-2026-13149       ghsa 48.4 to redhat 55.0    High and Medium
  CVE-2026-2950        nvd 48.4 to redhat 52.0     High and Medium
  CVE-2026-4800        ghsa 56.8 to nvd 61.9       High
  CVE-2026-13676       55.0                        High
```

One answer moved and every score fell. Note what happened to the heading:
**the source now changes the band on four findings rather than one.** Segmenting
the asset pushed a cluster of findings onto a band boundary, and near a boundary
it matters much more which source you believe. Where the argument between NVD
and GHSA lands is a property of the environment, not of the CVE.

Run the skeleton unedited and sixteen of the 18 come out `Low`, the other two
straddling `Medium and Low` — `CVE-2021-4279` among them at `21.9 to 29.4`, a CVE
that is Critical to NVD assessed as Low to Medium for an organisation that
exposes nothing and would lose nothing. `docs/SCORING_MODEL.md` calls that the
point of the exercise.

**The questions are fixed.** Twelve of them, across exposure, business impact
and threat — technical severity is not asked, because it comes from the
published vectors. Answering by id rather than by question is deliberate: the id
is resolved inside the library, so nothing outside it can add a question or
change what a Yes is worth. `docs/SCORING_MODEL.md` lists them, says which
weights are quoted from the design and which the library chose, and works
through the design's own example end to end.

Without `--answers` there is no Organisation Risk Score, and the report says so
under `NOT ASSESSED` rather than printing a zero.

### The exit code says which of three things happened

| Code | Meaning |
|---|---|
| `0` | the audit ran and found nothing |
| `1` | the audit ran and found something |
| `2` | the audit could not run, or could not save its reports |

**`2` is the one that matters.** A missing database, an absent scanner or a path
that is not there would otherwise exit 0 beside a genuinely clean repository, and
a pipeline would go green on a scan that never happened. `2` is also what a bad
command line exits with, so every "could not run" leaves by the same door. A run
whose reports could not be written exits `2` even with the record on stdout,
because it did not do everything it was asked to.

### The council is off unless you ask for it

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
audit fetched/vulnscout \
    --council-member qwen2.5:7b-instruct --council-member llama3.2:latest
```

The `NO_PROXY` line is needed here and not above: a member talks to Ollama on
loopback, and without it those requests go to the corporate proxy, which answers
502. A scan with no council needs nothing exported.

Each `--council-member` names one local Ollama model. With none named there is
no council, which is the honest default: the per-source scores stand side by
side with no winner.

### It is asked only about the findings the sources do not settle

The council reconciles sources, so a finding whose sources already agree is not
its work. Of the 18 findings on this repository, 5 carry sources that disagree,
and a two-member run is asked about those 5 — **80 model calls rather than 288**,
eight metrics for each of 5 findings, twice. A finding **no** source scored is
asked about too: there is no agreement to lean on, and a council vector is the
only severity it will ever carry. So is a finding carrying a source the
calculator could not read, because an unread vector is not agreement; this
repository has none, so the 5 stands.

```bash
audit fetched/vulnscout \
    --council-member qwen2.5:7b-instruct --council-member llama3.2:latest \
    --council-all-findings
```

`--council-all-findings` asks about all 18, at the full 288 calls. **What scoping
costs is the one thing only a council can find:** whether two sources that agree
are both wrong. Nothing here treats any source as the reference, so that is a
real loss and the flag is how you refuse it.

Every finding the council was not put to is named in the report with the reason
— `no published source disagrees, so there is nothing to reconcile`, or `the
advisory carries no text for a member to read`. The `COUNCIL (n)` heading counts
only what was assessed, because counting the skips would claim the council did
more than it did. A finding it was never asked about, one it could not settle,
and a run with no members named are three different facts and read as three.

### A council run says where it has got to

Local members share one Ollama server, and the council waits for each answer
before it makes the next call, so every member named adds its calls to the wall
clock rather than running beside the others. A run that says nothing is
indistinguishable from a hung one. `measurements/README.md` times a full run
at 71 min 39 s on one baseline and 7 min 3 s on the next, which changed
placement, second member, call order and Ollama version at once.
So a run prints one line per call:

```
council 1/80  finding 1/5 CVE-2026-13149  AV  qwen2.5:7b-instruct
council 2/80  finding 1/5 CVE-2026-13149  AC  qwen2.5:7b-instruct
...
council 8/80  finding 1/5 CVE-2026-13149  A  qwen2.5:7b-instruct
council 9/80  finding 1/5 CVE-2026-13149  AV  llama3.2:latest
...
council 16/80  finding 1/5 CVE-2026-13149  A  llama3.2:latest
council 17/80  finding 2/5 CVE-2021-4279  AV  qwen2.5:7b-instruct
```

The denominators are what this run will actually do: 5 findings after scoping,
not 18, and only the members it can reach. A total counting calls nobody makes
is a progress bar that never fills.

One member answers all eight metrics of a finding before the next is asked.
Two members that do not fit in the GPU's memory together are then swapped once
per member per finding rather than on every call.

**Every one of those lines goes to stderr and none to stdout.** So does the one
after the last call, saying where the reports went. The report has the other
stream to itself, so `--format json | jq` receives the artefact alone, byte for
byte the same whether or not anybody was watching. Redirect stdout to a file and
the progress still reaches your terminal.

Counts, and no elapsed time. A line prints *before* the call it names, so a slow
member is a line that sits there and you supply the seconds yourself. That is
what lets `src/` read no clock anywhere, which is what makes two runs of the
same commit and the same database byte-identical. The cost is the scrollback
afterwards: it cannot tell you whether a line sat for ninety seconds or nine
minutes.

### Fetching and scanning pull in opposite directions

The repository is an argument because fetching it needs the corporate proxy
**on** and scanning needs it **off**, so a command doing both would flip that
state mid-run. The advisory database download is out of band for the same
reason. Fetch once with the proxy on; scan what is on disk, offline, as often as
you like. The proxy section below puts both directions in a table.

### Running the tests

`pytest` is the only development dependency — the runtime is standard library —
and the `dev` extra installs it:

```bash
pip install -e '.[dev]'
python -m pytest -q
```

`requirements.txt` pins the same pytest, and `tests/test_pyproject.py` holds the
two to each other.

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
| Python | 3.11.11 (3.10+) | the CLI, the engine and the tests |
| git | 2.43.0 | cloning the repositories under audit |
| Syft | 1.52.0 | building the SBOM |
| Trivy | 0.74.0 | the advisory database and the CVE join |
| Ollama | 0.34.3 | the local analyst model |

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
├── pyproject.toml            the package, and the `audit` command
├── requirements.txt          pytest; the runtime is standard library
├── .claude/
│   └── agents/               six agent definitions
├── measurements/             the corpus and council runs behind cited figures
├── docs/
│   ├── SCORING_MODEL.md      the Organisation Risk Score
│   ├── COUNCIL.md            the assessor council
│   ├── diagrams.md           every flow, as diagrams
│   └── sources/              the two documents the design was read from
├── src/
│   ├── cli/                  arguments, preflight, the audit order, the council scope, the report files, the exit code
│   ├── council/              the roster, redaction, the providers, the chairman
│   ├── cvss/                 vector parser, metric vocabulary, Base score
│   ├── deps/                 the Syft and Trivy runners, the database's build date
│   ├── findings/             the join, and every source's score kept apart
│   ├── organisation/         the answer file, the approval, one score per source
│   ├── report/               the record, and the text, JSON and HTML renderings
│   └── scoring/              the approved questions and the risk score engine
└── tests/                    mirrors what it tests: src/ by module, the README under docs/
```

`fetched/` and `reports/` are ignored: a repository under audit is an argument,
never this project's evidence, and so is what a run writes.

## Licence

MIT. See [`LICENSE`](LICENSE).

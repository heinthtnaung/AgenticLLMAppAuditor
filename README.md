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
leave them out — `NOT ASSESSED`, never a zero and never an omission. So is every
manifest the scan could read no version from, and an inventory in which Syft
catalogued nothing.

| Part | State | What it is |
|---|---|---|
| `src/deps/` | built | Syft and Trivy: the components a directory declares, the advisories published against them, and the database's own build date; and which manifests have no lock file Syft reads |
| `src/cvss/` | built | a CVSS v3 vector parsed and validated, Temporal metrics included, and its Base score by the published equations |
| `src/findings/` | built | the join — a CVE affecting an installed component, with every source's score kept apart and attributed |
| `src/scoring/` | built | the approved question library, per-question weights, categories clamped then weighted, the band, the two severity floors that can raise it, and the version naming those rules |
| `src/council/` | built | the roster and its `egress` gate, redaction, the prompt, a provider registry holding one local Ollama client, the quotation check, the order check, the chairman, the runner, escalation of what the council leaves open to one larger local model, and the explainer that says why a finding's sources differ |
| `src/organisation/` | built | the answer file, the approval record, the rule for which findings need approval, and one risk score per published source |
| `src/report/` | built | the record every run produces, and its three renderings: a terminal report, the JSON audit artefact, and one self-contained HTML page |
| `src/cli/` | built | the arguments, the preflight refusals, the order the packages run in, which findings the council is put to, the progress it prints to stderr, the three report files in `reports/`, and the exit code |
| question selector | design | every approved question is asked, rather than the few a CVE's prerequisites call for |
| answer validation | design | no model reads the answers back for gaps or contradictions |
| hosted provider client | design | the local client works; nothing reaches OpenRouter or another API, so a hosted member is skipped for want of one. An adapter and a registry entry, and no other module moves |
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
  syft 1.52.0  ·  trivy 0.74.0  ·  advisory database built 2026-09-23T20:20:57.734988316Z
  scoring rules ors-1

18 findings across 60 components. 5 carry sources that disagree.
Approval is needed for 5 of 18: sources that disagree. With no organisation answers, none was
checked for a High or Critical Organisation Risk Score. No approval is recorded for this audit.

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

NEEDS APPROVAL (5)
  CVE-2026-13149  sources that disagree
  CVE-2021-4279   sources that disagree
  CVE-2025-13465  sources that disagree
  CVE-2026-2950   sources that disagree
  CVE-2026-4800   sources that disagree

NOT ASSESSED
  Organisation Risk Score
    no organisation answers were supplied, so no environment was weighed
  Approval record
    no answer file was given, so nobody was asked about this environment
  Council ruling
    no council assessed this run, so no council reading stands beside the published scores
  Why the sources differ
    no council was asked for, so no model was asked why the published sources differ
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
stylesheet is inlined and there is no script, no font and no image — because a
scan runs behind the corporate proxy and the report is opened from disk. A page
that fetched its stylesheet would arrive unreadable in the environment it was
made for.

**Each advisory links to its own page, where Trivy names one.** The address is
Trivy's `PrimaryURL`. On the page a finding's advisory id is a link, which a
reader follows or does not; nothing opens it for them. It carries
`rel="noreferrer"`, so a report served from an internal host does not hand its
own address to the advisory's site. The JSON's `advisory` carries it as `url`,
always present and `null` where Trivy names none. On this repository all 18
findings carry one.

The text report prints no link, because a link beside the id runs past the
page's width; `tests/report/test_text_findings.py` asserts that it prints none.
A `PrimaryURL` that is not an `http://` or `https://` address is refused rather
than put on the page as a link a browser would run, and `audit` exits `2`
naming it:
`audit: Advisory 'CVE-2026-4800' carries a PrimaryURL that is not a web link: 'javascript:alert(1)'`.

What HTML costs is comparison. Text and JSON both read line by line, so two runs
diff; a styling change rewrites an HTML file the whole way down, which is why
`json` stays the format to keep.

**It is a page, not an application.** Nothing is served and nothing is
interactive; there is no JavaScript and no build step. The browser-facing half
`frontend-developer` exists for is unwritten, and it has no box in diagram 5
because nothing has designed it either.

### A manifest with no lock file is named, not counted

Syft reads a `package.json`, `composer.json` or `Gemfile` through the lock file
beside it and through nothing else. One with no lock file yields no package at
all, so every dependency it declares goes unchecked, and `0 findings` over it
would read like a clean repository. So before the scan the repository is
walked and each such manifest is named. `.git/` is skipped, and so are
`node_modules/` and `vendor/`, the installed trees a lock file describes;
walking them would name the packages installed there as unread manifests.

| Manifest | Lock files Syft reads it through |
|---|---|
| `package.json` | `package-lock.json`, `yarn.lock` or `pnpm-lock.yaml` |
| `composer.json` | `composer.lock` |
| `Gemfile` | `Gemfile.lock` |

Each is named under `NOT ASSESSED` by its path within the repository, ahead of
everything but an empty inventory, with
`no lock file Syft reads is beside it, so no version it declares was checked`.
The summary gains a pointer, so the counts never stand alone: a second line in
text, and the end of the same summary paragraph on the page. With two such
manifests it reads
`Not in these counts: 2 manifests with no lock file Syft reads, named under not assessed.`
The JSON artefact carries each under `not_assessed`. A run that finds nothing
while one is named exits `3`, not `0`.

**To audit what it declares, write the lock file and audit again.** For npm, in
the manifest's directory, with the proxy **on** because it asks the registry:

```bash
npm install --package-lock-only --ignore-scripts --no-audit --no-fund
```

It writes `package-lock.json` and installs nothing, even where an `.npmrc` sets
`package-lock=false`, and `--ignore-scripts` keeps the manifest's own scripts
from running. On a large project it takes minutes. `--no-audit` stops npm
sending the resolved tree to the registry's audit service and printing its own
vulnerability count; that count and this tool's findings count different
things, so do not set one against the other.

What a written lock costs: it holds the versions npm resolves today within the
manifest's ranges, which need not be the ones deployed, so the audit is of
those.

The table is what Syft 1.52 was measured reading, and the walk over it falls
short four ways:

| Case | Named | Why |
|---|---|---|
| `package.json` beside only `node_modules/` or `npm-shrinkwrap.json` | yes | Syft reads neither in a directory scan |
| `Cargo.toml` or `pyproject.toml` with no lock file | no, although Syft reads nothing from either | a Cargo workspace keeps one lock at its root, and a `pyproject.toml` is often tool configuration; a repository of either can still read clean |
| a workspace member (npm, yarn or pnpm), locked by the root's lock file | yes, wrongly where Syft reads it from the root's lock | only the manifest's own directory is looked in; Syft was measured reading an npm member from the root's lock, and yarn and pnpm were not measured |
| the project's own manifest inside a folder named `node_modules/` or `vendor/` | no | both names are skipped at any depth as installed trees, so nothing inside is looked at |

A directory the walk cannot list stops the run before the scan, with exit `2`
and nothing on stdout, because passing over it would pass over every manifest
inside. The error stream says
`audit: cannot list <path> to look for manifests: Permission denied`.

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

**Every report names the rules that scored it.** The text heading's third line
reads `scoring rules ors-1`, the page's tools line ends with the same words, and
the JSON carries `run.scoring_rules_version`, after `advisory_database`. The
version covers everything that can move a score or a band, or mark it
provisional: the questions, their text and what a Yes is worth, the category
weights, the 0–100 clamp and the CVSS scale onto it, the band thresholds, the
severity floors, and what marks a score provisional. Two reports with different
versions are not comparable score for score.
`tests/scoring/test_version.py` fingerprints those rules, so a change made
without bumping `SCORING_RULES_VERSION` in `src/scoring/version.py` fails the
suite.

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

**A council's vector is never one of these scores.** Every score is weighed
from the published sources. Where a council settled a vector, its own CVSS base
score goes on the line under the finding, beside the range and not in it. For
`CVE-2026-18446` that line reads
`the assessor council CVSS 5.0  ·  the risk score does not use it`. The HTML
page shows it on a CVSS chip, beside the vector and the same words. In the
JSON, each finding's `organisation_risk` carries a `council_figure` beside
`scores`, with `used_in_score: false`, or `null` where no vector was settled.

Measured against published vectors on this repository, the settled values of
`qwen2.5:7b-instruct` and `llama3.2:latest` scored below answering one value
throughout on every metric, asked in either order. So a reader weighs a
council's vector and the score does not, whatever the roster. `measurements/README.md` has the figures, and
what they cannot show.

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

**Two answers can raise a band the weights leave low.** A Yes to THR-1,
exploited in the wild, puts a finding at High at least, and a Yes to THR-1,
EXP-1 and BUS-1 together puts it at Critical: `FLOOR-EXPLOITED-HIGH` and
`FLOOR-EXPLOITED-EXPOSED-CRITICAL`, whose reasons are in `docs/SCORING_MODEL.md`.
Only the band moves, and only an explicit Yes counts; Unknown, No and N/A never
raise one. Neither run above shows a floor, because `CVE-2021-4279`, the one
finding answered exploited, already sits at or above the band each floor it
meets would set.

Given the skeleton with the `by_advisory` block above added, `CVE-2021-4279`
scores `ghsa 37.9 to nvd 45.4`, Medium by the weights, and reads `High`, with a
line under it for each source:
`floored by FLOOR-EXPLOITED-HIGH: ghsa Medium to High`. The page puts
`floored by FLOOR-EXPLOITED-HIGH: Medium to High` beside each score's chip. In
the JSON each of `scores` carries `score_band`, the band its number gives,
beside `band`, the band after the floors, and `floors`, one entry per floor that
raised it, with `rule_id`, `answered_yes`, `band_before` and `band_after`. It is
empty where none did.

**The questions are fixed.** Twelve of them, across exposure, business impact
and threat — technical severity is not asked, because it comes from the
published vectors. Answering by id rather than by question is deliberate: the id
is resolved inside the library, so nothing outside it can add a question or
change what a Yes is worth. `docs/SCORING_MODEL.md` lists them, says which
weights are quoted from the design and which the library chose, and works
through the design's own example end to end.

Without `--answers` there is no Organisation Risk Score, and the report says so
under `NOT ASSESSED` rather than printing a zero. With `--answers` and nothing
found there is none either, and rather than claim nobody answered, it reads
`answers were supplied, but there was no finding to weigh them against`.

### Some findings are marked as needing approval

**A finding needs approval when any source's Organisation Risk Score is High or
Critical, or its published sources disagree.** The first is where a finding
matters in this environment, and what to do about it is a risk decision no model
may make. The second is a conflict nobody has resolved, and nothing in this tool
resolves it. Any source's score counts, not only the lowest, because a High from
one reading is a High somebody has to own. The rule is code, in
`src/organisation/approval_rule.py`, so the same record marks the same findings
every time.

| Where | What it shows |
|---|---|
| the summary | the count and which halves of the rule were checked, as `Approval is needed for 5 of 18: sources that disagree.` |
| text | a `NEEDS APPROVAL (n)` block before `APPROVAL` and `NOT ASSESSED`, one line per finding with the reasons it meets |
| the page | `needs approval: sources that disagree` on the finding's heading, and the summary's approval sentences as a paragraph of their own |
| JSON | `needs_approval` and `approval_reasons` on every finding, and `run.findings_needing_approval` |

**Without `--answers` only disagreement is checked**, because there is no risk
score to band, and the summary says so, as in the run at the top of this page:
`With no organisation answers, none was checked for a High or Critical Organisation Risk Score.`
When a finding needs approval and the answer file records none, the summary
adds `No approval is recorded for this audit.`

**One approval covers the audit.** The answer file's `approval` is recorded once
and stands for every marked finding, so no finding can be approved apart from
the rest. With the answers above, all 18 findings land High or Critical on some
source, so all 18 are marked and the mark tells none of them apart:
`Approval is needed for 18 of 18: a High or Critical Organisation Risk Score, or sources that disagree.`
The exit code does not change, because a marked finding is a finding and the
run exits `1` already.

### The exit code says which of four things happened

| Code | Meaning |
|---|---|
| `0` | the audit ran, catalogued components, found nothing, and read every manifest |
| `1` | the audit ran and found something |
| `2` | the audit could not run, or could not save its reports |
| `3` | the audit ran and found nothing, but could not read a manifest or catalogued no component |

**`2` is the one that matters.** A missing database, an absent scanner or a path
that is not there would otherwise exit 0 beside a genuinely clean repository, and
a pipeline would go green on a scan that never happened. `2` is also what a bad
command line and a directory the manifest walk cannot list exit with, so every
"could not run" leaves by the same door. A run whose reports could not be
written exits `2` even with the record on stdout, because it did not do
everything it was asked to.

**`3` keeps nothing found over something unchecked apart from `0`.** A
`package.json` with no lock file yields no package, so `0` there would put a
green build on dependencies nobody checked; a pipeline that passes only on `0`
stops on `3`. A run with findings exits `1` whether or not it read every
manifest, because the findings already stop the build, so on `1` read the JSON
artefact's `not_assessed` as well: each unread manifest is an entry there,
named by its path, with the lock-file reason as its `because`.

**An inventory of nothing exits `3` too.** Where Syft catalogues no component,
in an empty directory or one whose only manifest has no lock file, nothing was
checked against an advisory, and `0 findings across 0 components` would pass a
pipeline on a scan of nothing. The summary gains
`Not a clean result: Syft catalogued no component, so nothing was checked.`,
and `Component inventory` goes first under `NOT ASSESSED`, with
`Syft catalogued no component, so nothing was checked against an advisory`. The
JSON's `not_assessed` carries the same pair as `what` and `because`. It is `3`
and not `2` because the run did all it was asked and wrote its reports.

### The council is off unless you ask for it

```bash
audit fetched/vulnscout \
    --council-member qwen2.5:7b-instruct --council-member llama3.2:latest
```

No `NO_PROXY` export is needed for a council run. Every call a member makes to
Ollama goes through `src/council/transport.py`, which never uses a proxy, so a
corporate proxy set on the machine cannot answer for the model server. Run on
2026-09-25, before the order check, with the proxy set and `NO_PROXY` unset,
the command above with `qwen2.5:7b-instruct` alone made all 40 of its calls, and
no member failed.

**Any model pulled into the local Ollama can be a member.** The two named here,
`qwen2.5:7b-instruct` and `llama3.2:latest`, are examples: the pair this project
measured, not a requirement. What `measurements/README.md` found of their
readings is about that pair, not the tool, so a model you switch to needs its
own evaluation on the same findings before its readings are trusted, and
`measurements/README.md` says how.

Each `--council-member` names one local Ollama model. With none named, and no
`--council`, there is no council, which is the default: the published scores
stand side by side, and a council, when one runs, adds its own reading beside
them without choosing among them.

**Or name the members once, in `.env`, and ask for them with `--council`.** With
`AUDITOR_COUNCIL_MEMBERS=gemma4:latest,qwen2.5:7b-instruct` in `.env`, this runs
those two, in that order:

```bash
audit fetched/vulnscout --council
```

Switching models is then one line of `.env`. The setting starts nothing on its
own, and its value is checked only on a `--council` run: unset or empty, or with
an empty entry or a name given twice, `--council` is refused, naming the setting
and where it looked, and `audit` exits `2`; there is no default member. A
`--council-member` run does not use the value, though a line with no `=`, or the
key written twice, is refused on any council run, since every `AUDITOR_*` line
is read. The names are not checked against Ollama: a model it does not hold
fails when it is asked, each call recorded as that member's failure with the
server's reason, as a `--council-member` name does. `--council` beside a
`--council-member` is refused too, rather than one of them winning.
`--council-all-findings` works with either.

### The models, server, window and timeout are settings; the sampling is not

Six `AUDITOR_*` keys: one names the members `--council` runs, one the model a
council escalates to, and four set how local models are asked. Each is read
from the environment first, then from `.env` at the project root, then its
default. `.env.example` holds all six, the members and the escalation model left
empty: copy it to `.env`, which git ignores, and change what you need.

| Key | Default | What it sets |
|---|---|---|
| `AUDITOR_COUNCIL_MEMBERS` | unset: no members | the models `audit --council` runs, comma-separated, in the order they are asked. Nothing else uses it, and `--council` with it unset or empty is refused |
| `AUDITOR_ESCALATION_MODEL` | unset: no escalation | one local model, as `ollama list` names it, that a metric the council leaves contested or unresolved is sent to. An empty environment variable turns it off over a `.env` that names one; two names are refused |
| `AUDITOR_SERVER_URL` | `http://127.0.0.1:11434` | the Ollama server. It must be this machine, `127.0.0.1`, `localhost` or `::1`, or it is refused; an address ending `/api/generate`, the older form, is read without it |
| `AUDITOR_TIMEOUT_SECONDS` | `180` | how long one call may wait; a call that waits longer fails as `did not answer within N s` |
| `AUDITOR_CONTEXT_TOKENS` | `8192` | the window every member is pinned to, which the context guard scales with |
| `AUDITOR_MODEL` | `qwen2.5:7b-instruct` | the model a measurement, such as `prompt_tokens.py`, asks when it names none. It is not the audit's model and never starts a council |

**`AUDITOR_MODEL` does not choose the audit's council.** An audit asks the
models `--council-member` names, or the ones `AUDITOR_COUNCIL_MEMBERS` names
when it is given `--council`, and no other. `AUDITOR_MODEL` answers only for a
measurement that names no model.

Temperature 0, seed 11 and `think: false` are not settings. They are what makes
a local member reproducible, and a run whose sampling a file can change is not
comparable with the last one (`docs/COUNCIL.md`). The window and the timeout
can change a result too, so the JSON record's `run.local_models` states the
server, window and timeout a council run used, beside those three,
`"order_check": true`, every metric asked in both orders, and
`escalation_model`, the model named or `null`. It is `null` itself for a run
with no member.

**Only `AUDITOR_*` lines of `.env` are read**, so the file can hold other keys:
every other line is passed over unparsed and never quoted. A misspelt
`AUDITOR_*` key, a key written twice and a bad value are each refused, the value
named with where it came from, and `audit` exits `2` before it scans. It reads
the settings only when `--council` or a `--council-member` asks for a council,
so a run with neither is untouched by `.env`, whatever it names. No test reads
them either: `tests/conftest.py` runs every
test on the defaults.

### Every metric is asked twice, with the options in both orders

**A member's value counts only when it gives the same one both ways.** Each
council member is asked each metric with its values listed in the
specification's order, then reversed. The same value both ways stands as the
in-order reply, its quotation included. Two different values are recorded as
order-sensitive, both named, and like a decline it neither supports a value nor
contests one. A failure in either order is a failure, a reversed one's reason
starting `with the options reversed:`; otherwise a decline in either is a
decline. The chairman rules on those replies as before. **It costs twice the
calls.**

It is on because local models answer by where an option sits in the list.
Measured on this repository's 18 findings, Llama's Attack Vector, Attack
Complexity and User Interaction and Qwen's Privileges Required and User
Interaction changed with the order on 7 to 18 of them (`measurements/README.md`).
The check takes those answers out of the ruling. **Whether a council then
settles more depends on the roster.** Replayed from the same saved replies, of
144 metrics:

| Roster | Asked | Settled | Contested | Unresolved | Vectors |
|---|---|---|---|---|---|
| Qwen + Llama | one order | 105 | 13 | 26 | 4 |
| Qwen + Llama | both orders | 83 | 4 | 57 | 0 |
| Qwen + Gemma | one order | 65 | 69 | 10 | 0 |
| Qwen + Gemma | both orders | 86 | 37 | 21 | 0 |

Qwen + Llama settles fewer and reaches no vector. Qwen + Gemma settles more,
because Qwen's positional answers stop contesting Gemma's stable ones. Neither
roster's agreement with the measurement's reference, the metrics where Red
Hat's and NVD's or GHSA's vectors agree, changed distinguishably at 18
findings; the closest was Qwen + Gemma's Attack Vector.

The models are `qwen2.5:7b-instruct`, `llama3.2:latest` and `gemma4:latest`,
and a roster of others needs its own measurement. The rows are
`pilot-vulnscout/pilot.score.txt`,
`order-checked-vulnscout/qwen-llama.order-checked.txt`,
`gemma4-vulnscout/gemma4.score.txt` and
`order-checked-vulnscout/qwen-gemma4.order-checked.txt`, all under
`measurements/council_eval_runs/`.

In the text and the page an order-sensitive member reads
`order-sensitive: N with the options in order, L reversed`. Its JSON row has
`"said": "order-sensitive"`, `"value": null` and
`"orders": {"in_order": "N", "reversed": "L"}`, and `orders` is `null` on every
other row. Every member row names both prompts it was asked,
`"prompt_version": "member-base-metric-3"` and
`"reversed_prompt_version": "member-base-metric-3+reversed-1"`. An audit always
fills both; the second is `null` only for a member asked in one order, as the
measurement harness replays them.

### A metric the council leaves open can go to one larger local model

**Name one in `AUDITOR_ESCALATION_MODEL`, and every metric the order-checked
council leaves contested or unresolved is put to it**, in both orders like a
member. Nothing else is: not a settled metric, and never the whole advisory.
With it unset, the default, an open metric stays open. It is read only on a
council run, so a `.env` naming one starts nothing on its own.

**It settles a metric only on a reply that would have counted from a member:**
the same value both ways round, with a quotation the advisory contains. On a
contested metric the value must also be one the council's verified quotations
already support, so escalation can side with evidence but never add a reading.
Anything else leaves the metric as the council left it, with what the model said
recorded. A metric it settles carries the basis `ESCALATED`, "the council left
it open, and the escalation model's verified quotation settled it".

**It is local, and it is not a member.** The name is a model on the local
Ollama server, so a hosted escalation cannot be written: hosted escalation is
excluded, not deferred. A model already on the council is refused after the
scan, before any model is asked, and `audit` exits `2` with
`audit: big:27b is on the council, so it cannot also be the model the council's open metrics escalate to`.

In the text and the page, a metric that went to the model says what came of it.
From a run with stand-in models, a contest it settled and an unresolved metric
it could not:
`AC  ·  contested → escalated to big:27b: L (verified)  ·  2 members` and
`UI  ·  unresolved → escalated to big:27b: no settlement, guessed R with nothing quoted  ·  2 members`.
The model is listed under the members as `big:27b (big), escalation model`. In
the JSON, each metric carries `escalation`: `prior_outcome`, what the council left it
as, then the model's row in the shape of a member's, and `null` on a metric
nobody escalated. The metric's own `outcome` is what came of it.

**It costs two calls per open metric**, a number known only once the council has
answered, so the progress stream counts them apart. It runs after each
advisory's council, so a model too large to stay loaded beside the members
is loaded once per advisory; that has not been timed. Nothing escalated reaches
the Organisation Risk Score, as nothing a council settles does.

**It has been tested only with stand-in models.** No escalation model has run
live or been measured on the pilot's findings, so nothing yet says whether one
settles open metrics correctly. The measurement harness replays its passes with
none (`PASS_ESCALATION = None` in `measurements/council_eval/variants.py`).

### Beside a council, one model says why the sources differ

**Each finding whose readable sources disagree gets one more call, asking why.**
It is made only when a council was asked for, and only after the council and any
escalation have finished with every finding, so the one model asked is loaded
once. That model is the escalation model where one is named, otherwise the
council's first local member, and the record names it: the explainer runs on this
machine. A roster with neither is refused once its council has run, with
`audit: no local member to explain with: the explainer runs on this machine, and no escalation model is named`,
and `audit` exits `2`. Every `--council-member` is local, so the command line
cannot build such a roster today. The model is shown each source's value on the
disputed metrics alone, with what those values mean, and the redacted advisory:
never a whole vector, never the CVE id.

**Only the quotation is checked.** Each item the model offers names a disputed
metric, says why in its own words, and quotes the advisory. The first item on
each disputed metric with a `why` that is not empty and a quotation the advisory
contains is kept. Every other item is dropped and counted: a quotation not in
the advisory, an item on a metric the sources agree on, a second item on a
metric, an empty `why`. If nothing is kept, or the call fails, or the reply
cannot be read, the finding is not explained and the record says why. Nothing
checks the `why`, and nothing reads an explanation back: no score, band or
council vector comes from it.

The text puts a `WHY THE SOURCES DIFFER (n)` block after `SOURCES DISAGREE`, and
the page a section after "Sources disagree", each under a lede saying only the
quotation is checked. From a run with stand-in models, one finding reads
`CVE-2021-23337  explained by small:1b  ·  4 items not kept`, then its metric,
`C  ghsa H  ·  nvd L`, the model's words,
`model-written, not checked: It says commands run, not what they can read.`,
and `“A remote attacker can inject commands”  ·  quotation found in the advisory`.

In the JSON, every finding carries `llm_explanation`:
`{"assessed": true, "model", "prompt_version": "sources-differ-1", "items", "dropped"}`,
each item a `metric`, `why`, `evidence`, `evidence_verified` and
`"why_checked": false`, or `{"assessed": false, "because"}`. `evidence_verified`
covers the quotation alone; `why_checked` says so, so a machine reader cannot
take it as covering the prose. Where no finding was explained, `NOT ASSESSED`
names `Why the sources differ` with one of three reasons: no council was asked
for, as in the run at the top of this page, no finding's sources disagree, or
no explanation quoted the advisory.

**It costs one call per disputed finding.** It has been tested only with
stand-in models, and nothing yet measures whether an explanation is right: the
quotation is in the advisory, and that is all that is known of it.

### It is asked only about the findings the sources do not settle

The council reconciles sources, so a finding whose sources already agree is not
its work. Of the 18 findings on this repository, 5 carry sources that disagree,
and a two-member run is asked about those 5 — **160 model calls rather than
576**, eight metrics for each of 5 findings and each of two members, in both
orders. A finding **no** source scored is
asked about too: there is no agreement to lean on, and a council vector is the
only severity it will ever carry. So is a finding carrying a source the
calculator could not read, because an unread vector is not agreement; this
repository has none, so the 5 stands.

```bash
audit fetched/vulnscout \
    --council-member qwen2.5:7b-instruct --council-member llama3.2:latest \
    --council-all-findings
```

`--council-all-findings` asks about all 18, at the full 576 calls, and
`audit fetched/vulnscout --council --council-all-findings` does the same with
the members `.env` names. **What scoping costs is the one thing only a council
can find:** whether two sources that agree are both wrong. Nothing here treats
any source as the reference, so that is a real loss and the flag is how you
refuse it.

Every finding the council was not put to is named in the report with the reason
— `no published source disagrees, so there is nothing to reconcile`, or `the
advisory carries no text for a member to read`. The `COUNCIL (n)` heading counts
only what was assessed, because counting the skips would claim the council did
more than it did. A finding it was never asked about, one it could not settle,
and a run with no members named are three different facts and read as three. A
run that named members and found nothing is a fourth, and reads `council members
were named, but there was no finding to put to them`.

**The section opens by saying whether anything could be escalated.** The first
line under the `COUNCIL (n)` heading in text, and the first after the section's
lede on the page, is
`escalation model big:27b: asked each metric the council left open`, naming the
model, or `no escalation model named: a metric the council left open stays open`.
It is left out only for a record that says nothing of how local models were
asked, so every council run carries one or the other.

**A finding the council settled shows what its vector scores, answers or no.**
Its heading line reads `settled`, the vector, and that vector's own CVSS base
score and band, as `settled  ·  CVSS:3.1/…  ·  CVSS 9.8 Critical`. The page puts
a CVSS chip on the same line, and the JSON's `council` entry carries the figure
as `base_score` beside `vector`, `null` where no vector was settled. It is on
the CVSS scale and never the risk score.

### A council run says where it has got to

Local members share one Ollama server, and the council waits for each answer
before it makes the next call, so every member named adds its calls to the wall
clock rather than running beside the others. A run that says nothing is
indistinguishable from a hung one. `measurements/README.md` times a full run
at 71 min 39 s on one baseline and 7 min 3 s on the next, which changed
placement, second member, call order and Ollama version at once; both asked
each metric once, and a run today asks it twice.
So a run prints one line per call. The recorded `gpu-scoped` run in
`measurements/council_runs/` was the scoped two-member command, given the answer
skeleton as well:

```bash
audit fetched/vulnscout --answers answers.example.json \
    --council-member qwen2.5:7b-instruct --council-member llama3.2:latest
```

Its stderr, from `gpu-scoped.progress.txt`:

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

That run predates the order check, so it asked each metric once. The same
command now makes 160 calls. Each in-order line keeps the shape above, and the
reversed call's line follows it, marked after the metric; for one member over
one finding, the second line is
`council 2/16  finding 1/1 CVE-2021-23337  AV (options reversed)  small:1b`.

The denominators are what this run will actually do: 5 findings after scoping,
not 18, and only the members it can reach. A total counting calls nobody makes
is a progress bar that never fills. An escalation call is counted apart, as
`escalation 1  finding 1/1 CVE-2021-23337  AC  big:27b`, with no total, because
how many a run makes is known only once each council has answered. The
explanations come last, one line each, counted against the disputed findings:
`explanation 1/1  finding CVE-2021-23337  small:1b`.

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

No total is pasted here: the suite grows with every module that lands, so a
total written down is wrong within the day. The table below is held instead:
`tests/docs/test_readme_gated.py` runs each file it names with no flag set, and
checks that the file skips as many tests as the Tests column says, each for a
reason naming its flag. Nothing checks the Runs or Needs columns.

**Three files skip unless asked for**, because each needs something the
ordinary suite may not depend on. A plain run counts their tests as skipped, the
sum of the Tests column below, and each skip's reason names its flag:

| Flag | Runs | Tests | Needs |
|---|---|---|---|
| `COUNCIL_LIVE_OLLAMA=1` | `tests/council/test_ollama_live.py`: asks a model for real, the default `qwen2.5:7b-instruct` unless `COUNCIL_LIVE_MODEL` names another, so the recordings the council tests use are checked against it and a new model is checked the same way: it answers in the council's shape, quotes the advisory, and gives the same reply from two cold starts | 3 | `ollama serve` with `qwen2.5:7b-instruct` pulled, or the model `COUNCIL_LIVE_MODEL` names (for example `COUNCIL_LIVE_MODEL=gemma4:latest`); it skips, naming the model, when that model is not pulled |
| `README_LIVE_SCAN=1` | `tests/docs/test_readme_live.py`: reruns this page's marked audits and fails on any printed line that drifted | 1 | `fetched/vulnscout`, Syft, Trivy and the advisory database |
| `SYFT_LIVE_SCAN=1` | `tests/deps/test_manifests_live.py`: measures the lock-file table above against the real Syft again | 13 | Syft on the path |

All three at once, as one line:

```bash
COUNCIL_LIVE_OLLAMA=1 README_LIVE_SCAN=1 SYFT_LIVE_SCAN=1 python -m pytest -q
```

The prefix sets the variables for that command alone, so nothing stays
exported. With every flag on and everything each needs in place, nothing
skips. A skip that remains names its cause: Syft is not installed; the README
check's corpus, a scanner or the database is missing; or the model declined
the one metric a test asks about, which is a result and not a failure. Run as
root, the tests that provoke a permission refusal skip too.

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

Progress bar elided. The download is 116 MiB and lands in Trivy's cache:
`$TRIVY_CACHE_DIR` if that is set, else `$XDG_CACHE_HOME/trivy`, else
`~/.cache/trivy`.

**`audit` finds the cache the same way and hands it to the scan.** It reads the
same two variables in the same order, a relative `TRIVY_CACHE_DIR` taken from
where you run it, dates the database it finds there, and passes that directory
to Trivy as `--cache-dir`, so the database dated is the database scanned. Set
either variable for `audit` and set it for the download and for `trivy version`
too, or they read different caches. A relative `XDG_CACHE_HOME`, or no `HOME`
with neither variable set, is refused with `audit: …` and exit `2` rather than
followed into a temporary directory.

**A `cache.dir` in a `trivy.yaml` is never read.** The download follows one in
the directory it runs from, and `audit`'s `--cache-dir` overrides it, so a
cache moved that way is downloaded to and never scanned. Move it with a
variable.

It is a separate step because scans run offline, with `--skip-db-update`, so
that a scan is reproducible and pinned to a known database. Running `trivy`
yourself without that flag can update the cache as a side effect, and every
audit after it reads the newer database; to update it on purpose, run the
download above with the proxy on.

The cost of that choice: **Trivy alone, given an empty cache, produces a clean
report rather than an error.** It finds no advisories, exits 0, and nothing in
its output says the database was missing. So `audit` reads the database's own
build date, `UpdatedAt` in `db/metadata.json` inside that cache, before anything
is scanned, and exits `2` with nothing on stdout when that file is missing,
unreadable or carries no build date. A build date with no database beside it
gets past that check, and then Trivy refuses the offline scan, so `audit`
exits `2` with Trivy's own error.

**A stale database is not refused.** It is there and it has a date, so the run
goes ahead and every report carries that date: `advisory database built` in
the text header, `run.advisory_database.built_at` in JSON, and on the HTML page.
Nothing compares it with today, because `src/` reads no clock, so whether it is
too old is yours to judge. `trivy version` shows it beside the date Trivy calls
it due for an update:

```bash
trivy version
```

```
Version: 0.74.0
Vulnerability DB:
  Version: 2
  UpdatedAt: 2026-09-23 20:20:57.734988316 +0000 UTC
  NextUpdate: 2026-09-24 20:20:57.734987855 +0000 UTC
  DownloadedAt: 2026-09-24 06:03:45.881932713 +0000 UTC
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

**This project and Ollama's own command line need none of it.** `audit`, the
live test and the measurement scripts reach Ollama through
`src/council/transport.py`, which opens every request with no proxy. With the
proxy set and `NO_PROXY` unset, a council run made all 40 of its calls and
`ollama ps` answered normally, so the `ollama` command does not send 127.0.0.1
to the proxy either. Other tools pointed at a local service, such as `curl` or
Python's `urllib` outside this project's transport, may still need the export.

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
│   ├── deps/                 the Syft and Trivy runners, the database's build date, unread manifests
│   ├── findings/             the join, and every source's score kept apart
│   ├── organisation/         the answer file, the approval and what needs it, one score per source
│   ├── report/               the record, and the text, JSON and HTML renderings
│   └── scoring/              the approved questions and the risk score engine
└── tests/                    mirrors what it tests: src/ by module, the README under docs/
```

`fetched/` and `reports/` are ignored: a repository under audit is an argument,
never this project's evidence, and so is what a run writes.

## Licence

MIT. See [`LICENSE`](LICENSE).

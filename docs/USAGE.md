# The full guide

Everything `audit` does, flag by flag, in more detail than
[the README](../README.md), which is the short version. What to install, and
the advisory database, are [SETUP.md](SETUP.md); the tests and the layout are
[DEVELOPMENT.md](DEVELOPMENT.md).

An SBOM-based vulnerability auditor. Build a bill of materials for a
repository, join it to a pinned advisory database, score each finding by the
published CVSS v3.1 equations, and add an **Organisation Risk Score** that
reflects the environment the code is deployed into.

A council of models — local today, hosted once a client for one exists — reads
advisories and agrees one vector, each member quoting the text it relied on. A
deterministic engine turns that vector into every number. The two are never the
same step.

## Running a scan

Install it once into a virtual environment ([SETUP.md](SETUP.md), "Installing"),
and it is the `audit` command. The repository being audited is an argument and
already on disk — this tool never clones one. A run prints the report and saves
it in three formats into `reports/`. The README shows what a plain run prints,
under "Scan a repository". Its `MATCHED NOTHING` block counts what the join
left unpaired: on this repository `55 components carry no advisory` and
`0 advisories matched no component`.

## Three formats, one record, three files

Every run saves the report in all three formats into `reports/`, in the
directory the command ran from. Each file is named after the repository's
directory, so `audit fetched/vulnscout`, run from the project root, leaves:

| File | `--format` | What it is |
|---|---|---|
| `reports/vulnscout.txt` | `text` | the text report, and the default |
| `reports/vulnscout.json` | `json` | the audit artefact, for a pipeline or `jq` |
| `reports/vulnscout.html` | `html` | one page to open in a browser |

To read the page, open `reports/vulnscout.html` in a browser; it needs no second
run. `--format` picks only which of the three is printed on stdout, and the file
of that format is byte for byte what was printed. After the report, one line on
stderr says where the three went:
`reports written to reports/vulnscout.txt, reports/vulnscout.json, reports/vulnscout.html`.

**The page is tabbed: Overview, Disagreements, Agreements, Org risk, Council,
Secrets and Inventory.** Overview opens with summary tiles, a callout naming the
two scores apart, cards for the approval and what was not assessed, and an "All
findings" table filtered by All, Needs approval, Disagree, Agree or Council
settled, with a search box. Each disagreement card carries why the sources
differ; refused and unscored findings are their own groups under Agreements, and
the components that matched nothing and the unidentified artifacts (a GitHub
action, say) are under Inventory. With scripts off the page still reads whole —
every tab stacks and shows, and the filter bar does not appear. With the script,
printing opens every collapsed section.

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
stylesheet and the script are both inlined, and there is no font and no image —
because a scan runs behind the corporate proxy and the report is opened from
disk. A page that fetched its stylesheet would arrive unreadable in the
environment it was made for.

**Each advisory links to its own page, where Trivy names one.** The address is
Trivy's `PrimaryURL`. On the page a finding's advisory id is a link, which a
reader follows or does not; nothing opens it for them. It opens in a new tab,
marked with a small inline SVG icon, and carries `rel="noreferrer"`, so a report
served from an internal host does not hand its own address to the advisory's
site. The JSON's `advisory` carries it as `url`,
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

**It is one page, not an application.** Nothing is served and nothing is
fetched. There is one inline script and no build step — no framework and no
bundler — and the page reads with scripts off. A served, browser-facing
application is unwritten, and it has no box in diagram 5 because nothing has
designed it either.

## A manifest with no lock file is named, not counted

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

## A secret is reported by where it is, never by what it is

**The same Trivy run that finds the advisories finds secrets.** Trivy's
built-in secret rules match text shaped like a credential, a token or a private
key; they read no database, so they run offline beside the vulnerability scan.
Only Trivy's built-in rules are used ([SETUP.md](SETUP.md) says how). Each match
is reported by the file, the line or lines, the rule that matched, its title,
its category and its severity. The summary counts them, on this repository as
`0 secrets matched the secret rules built into Trivy.`, and the text report
lists them under `SECRETS (n)`. From a scratch tree holding a made-up GitHub
token, the entry is `settings.py:4`, then
`CRITICAL  ·  GitHub Personal Access Token  ·  GitHub  ·  rule github-pat`.

With none, the block still appears, and says
`Trivy's built-in secret rules matched nothing in this tree.` It names the
rules because they are all that looked: no match is not the same as no secret.
The page has a Secrets tab in the same terms, under a lede saying the
secret is not on the page and not in the record behind it.

**The secret itself is never read.** Trivy masks it in the match and in the
lines of code it quotes, but a mask is Trivy's promise and not this tool's, and
the rest of a quoted line can hold a second secret no rule matched. So neither
field is read, the record has nowhere to carry a secret, and nothing downstream
can print one by accident. In the JSON, `secrets` is a list of `file`,
`start_line`, `end_line`, `rule_id`, `category`, `severity` and `title`, and
`run.secret_count` counts them. A secret is not a finding: it has no CVSS, so it
is never scored, weighed or put to the council.

## Scoring a finding against your environment

A scanner cannot tell whether a vulnerable component is exposed, or whether it
matters. `--answers` supplies that half, as a JSON file answering the **approved
question library** by question id. [`answers.example.json`](../answers.example.json)
is a runnable skeleton: every question answered `No`, with the question text
beside each id so you do not have to look them up.

Filled in for an internet-facing, business-critical asset:

<!-- doc-check: answers -->
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

That run prints an `ORGANISATION RISK` block, shown in full in the README under
"Score it against your environment".

The block's second line is the weighting those totals were reached with. It is
read off the record rather than off `docs/SCORING_MODEL.md`, so a reader
re-deriving a score by hand works from the run that produced it and not from a
table that could have moved since.

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

`CVE-2021-4279` scores highest because it is the one finding the `by_advisory`
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
council's vector and the score does not, whatever the roster.
`measurements/README.md` has the figures, and what they cannot show.

**The environment drives those numbers, not the CVE.** The same file with
`EXP-1` set to `No` and `EXP-4` to `Yes` — the asset segmented rather than
internet-facing, nothing else touched:

<!-- doc-check: run --answers EXP-1=No EXP-4=Yes -->
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

## Some findings are marked as needing approval

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
score to band, and the summary says so, as in the README's sample run:
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

## The exit code says which of four things happened

| Code | Meaning |
|---|---|
| `0` | the audit ran, catalogued components, found nothing, and read every manifest |
| `1` | the audit ran and found something: a vulnerability or a secret |
| `2` | the audit could not run, or could not save its reports |
| `3` | the audit ran and found nothing, but could not read a manifest or catalogued no component |

**`2` is the one that matters.** A missing database, an absent scanner or a path
that is not there would otherwise exit 0 beside a genuinely clean repository, and
a pipeline would go green on a scan that never happened. `2` is also what a bad
command line and a directory the manifest walk cannot list exit with, so every
"could not run" leaves by the same door. A run whose reports could not be
written exits `2` even with the record on stdout, because it did not do
everything it was asked to.

**A secret is something found.** It carries no CVSS and is never scored, but a
credential in the tree stops a build as surely as a CVE does, so a run that
found one exits `1` whatever else it found or could not read, an empty
inventory included.

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

## The council

A council is off unless you ask for it. Each section below is one part of a
council run; `docs/COUNCIL.md` is the design behind them.

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

**It also names the server, and the weights it held under each tag when the run
began.** A tag such as `gemma4:latest` names whatever weights the server holds
under it, and pulling again changes them without changing a word of the record.
So a council run reads the server twice before any model is asked, `/api/tags`
and `/api/version`, through the same no-proxy client every call uses, at the
settings' server, which `council.settings` holds to loopback. Each read waits
`READ_TIMEOUT_SECONDS`, 30 s, not the generation timeout, since both come before
the scan. It records `ollama_version` once and, under `models`, each model it
asks with its `role`, `member` or `escalation`, and its `digest`. The explainer
is always one of those. What the server does not say is recorded as not said:
`"known": false` and the `reason`, never a guessed value, and the audit carries
on.

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
the JSON, each metric carries `escalation`: `prior_outcome`, what the council
left it as, then the model's row in the shape of a member's, and `null` on a
metric nobody escalated. The metric's own `outcome` is what came of it.

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
contains is kept. Every other item is dropped, and the record keeps it with the
first reason that applies, in this order: `not a disputed metric`, `empty why`,
`unverified quotation`, `repeat`. The text and the page show only how many were
dropped, never a dropped item's words or quotation. If nothing is kept, or the
call fails, or the reply cannot be read, the finding is not explained and the
record says why. Nothing
checks the `why`, and nothing reads an explanation back: no score, band or
council vector comes from it.

The text puts a `WHY THE SOURCES DIFFER (n)` block after `SOURCES DISAGREE`; on
the page the same explanation is a block inside each disagreement card, under a
"Why the sources differ" heading, with the lede that only the quotation is
checked shown once above the cards. In the terminal, from a run with stand-in
models, one finding reads
`CVE-2021-23337  explained by small:1b  ·  4 items not kept`, then its metric,
`C  ghsa H  ·  nvd L`, the model's words,
`model-written, not checked: It says commands run, not what they can read.`,
and `“A remote attacker can inject commands”  ·  quotation found in the advisory`.
The page carries the same, without the `·` separators or the colon.

In the JSON, every finding carries `llm_explanation`:
`{"assessed": true, "model", "prompt_version": "sources-differ-1", "items", "dropped"}`,
each item a `metric`, `why`, `evidence`, `evidence_verified` and
`"why_checked": false`, or `{"assessed": false, "because"}`. `evidence_verified`
covers the quotation alone; `why_checked` says so, so a machine reader cannot
take it as covering the prose.

Every `llm_explanation` also carries `dropped_items`, each a `metric`, `why`,
`evidence`, `evidence_verified`, `"why_checked": false` and its `reason`, and
`dropped` is how many there are. On a dropped item `evidence_verified` is the
quotation check's own answer: a repeat quotes the advisory as surely as the item
kept. `dropped_items` is empty where nothing was offered, and where nothing was
kept it holds what was, beside a `because` such as
`small:1b: the model offered 1 item, and none was kept (unverified quotation 1)`.
Where no finding was explained, `NOT ASSESSED` names `Why the sources differ`
with one of three reasons: no council was asked for, as in the README's sample
run; no finding's sources disagree; or
`a model was asked why the sources differ, and no explanation was kept`.

**It costs one call per disputed finding.** It has been tested only with
stand-in models, and nothing yet measures whether an explanation is right: the
quotation is in the advisory, and that is all that is known of it.

### It is asked only about the findings the sources do not settle

The council reconciles sources, so a finding whose sources already agree is not
its work. Of the 18 findings on this repository, 5 carry sources that disagree,
and a two-member run is asked about those 5 — **160 council calls rather than
576**, eight metrics for each of 5 findings and each of two members, in both
orders. A finding **no** source scored is
asked about too: there is no agreement to lean on, and a council vector is the
only severity it will ever carry. So is a finding carrying a source the
calculator could not read, because an unread vector is not agreement; this
repository has none, so the 5 stands.

**The council's calls are not the whole count.** Whichever the scope, the run
then makes one explanation call per finding whose sources disagree, 5 here, and
an escalation model adds 2 for each metric the council leaves open: at most 80
on the 5 findings, 288 on all 18. Counted with stand-in models on this
repository, a two-member run makes 165 calls in all, 245 with an escalation
model sent every metric, and 581 under `--council-all-findings`.

```bash
audit fetched/vulnscout \
    --council-member qwen2.5:7b-instruct --council-member llama3.2:latest \
    --council-all-findings
```

`--council-all-findings` asks about all 18, at the full 576 council calls, and
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
line under the `COUNCIL (n)` heading in text, and the first line after the lede
and the toolbar in the Council tab, is
`escalation model big:27b: asked each metric the council left open`, naming the
model, or `no escalation model named: a metric the council left open stays open`.
It is left out only for a record that says nothing of how local models were
asked, so every council run carries one or the other.

Every model the run asks is named too, with the first 12 characters of its
digest and the server's version. In the text report this is the line after the
escalation one, under the `COUNCIL` heading; on the page it is in the masthead,
under the tool and database lines, not in the Council tab. From a run with
stand-in models and a stand-in server listing the two members and not the
escalation model:
`models: qwen2.5:7b-instruct 845dbda0ea48, llama3.2:latest a80c4f17acd5, qwen2.5:14b (escalation) digest unknown; Ollama 0.34.3`.
Where the server gives no digest or no version, it reads `digest unknown` or
`Ollama version unknown`, and the reason it gave none is in the JSON record
alone, under `run.local_models`. The record keeps each digest whole.

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
command now makes 160 council calls and then 5 explanation calls. Each in-order
line keeps the shape above, and the
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

Read [`docs/SCORING_MODEL.md`](SCORING_MODEL.md) for the scoring design
and [`docs/COUNCIL.md`](COUNCIL.md) for how several models assess one CVE
without any of them producing a number.

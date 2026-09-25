# Measurements

The corpus behind the numbers in `src/council/redaction.py`,
`src/council/ollama.py`, `src/council/definitions.py` and `docs/COUNCIL.md`,
and the council runs behind the counts in `src/cli/`, `src/council/runner.py`,
`README.md`, `docs/COUNCIL.md` and `docs/diagrams.md`, and behind the one
timing the code gives, in `src/cli/progress.py`.

A measurement nobody can re-run is an assertion. Everything here exists so a
reader can disagree with a number by producing a different one.

## What is here

| Path | What it is |
|---|---|
| `corpus/pypi`, `corpus/npm`, `corpus/golang`, `corpus/rust` | four handwritten manifests pinning deliberately out-of-date packages |
| `rootfs/debian`, `rootfs/alpine` | two synthetic root filesystems: an `os-release`, a version marker and a package database listing old packages |
| `advisories.py` | runs the seven scans and reads them into one set of advisory texts |
| `redaction_gaps.py` | what `council.redaction` catches, lets past, and would cost to widen |
| `prompt_tokens.py` | what a member's prompt costs the pinned model, counted by the model |
| `record_council_run.py` | runs one council audit and keeps what it printed and wrote beside what produced it |
| `run_provenance.py` | what a recorded run was launched from and how it ended: git and `ollama ps` at launch, the clock and `ollama ps` at the end |
| `run_directory.py` | where a recorded audit runs, so the project's `reports/` is never written, and the copying out of its three renderings |
| `council_runs/` | audits of `fetched/vulnscout` with a two-member council: what each run printed or wrote, and when |
| `thinking_and_load/` | a probe of the `think` field and of load state on three models: the script, its 22 envelopes, and what they do and do not show |

The manifests and package databases are written by hand, not captured from a
real system. They are chosen to reach different advisory feeds — GHSA, OSV,
RustSec, the Debian and Alpine security trackers — not to describe a plausible
deployment. Editing one changes every number below, so re-run both scripts and
update the docstrings that cite them.

The seventh scan is not here: it is `fetched/vulnscout`, the repository this
project audits.

## Running it

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
python measurements/redaction_gaps.py
python measurements/prompt_tokens.py
```

`redaction_gaps.py` needs Trivy and the database snapshot in the cache Trivy
finds for itself, since these scripts pass it no `--cache-dir`: by Trivy 0.74's
own order, `TRIVY_CACHE_DIR`, a `cache.dir` in a `trivy.yaml` where it runs,
`$XDG_CACHE_HOME/trivy`, then `~/.cache/trivy`. It touches no network and no
model. `prompt_tokens.py` additionally needs `ollama serve` up with
`qwen2.5:7b-instruct` pulled; it talks to loopback only.
The `NO_PROXY` export is this machine's corporate proxy, which otherwise answers
502 for a loopback request.

## The numbers, and what they support

**The corpus: 1,187 distinct advisories on the database built
2026-09-22T02:00:05Z**, across seven scans — 254 PyPI, 163 npm, 74 Go, 29 Rust,
608 Debian 11, 109 Alpine 3.14, 18 vulnscout. That is 1,255 across the scans,
and 1,187 once an advisory two scans reach counts once. Every number in the
table was measured on that database.

| Number | What it decided |
|---|---|
| **0** advisories redacted differently after bare vectors were added | adding the pattern costs nothing on real text, which is why it went in although it fires on nothing new |
| **0** vector-shaped strings surviving redaction | the panel rule holds on this corpus |
| **1** advisory carrying a prose score, `GHSA-pw6j-qg29-8w7f` | the prose gap stays open: the same sentence publishes an AC value in words that no pattern reaches |
| **878** advisories carrying some `x.y` number | what a general prose-score pattern would eat — three in four, all versions |
| **1** identifier in another namespace, `SNYK-JS-ANGULAR-570058`, in a URL | not worth a namespace list against prefixes like `DSA` that are live words |
| **0** advisories containing their own id | every identifier in advisory text is a cross-reference |
| **421** tokens for a prompt with no advisory in it | one metric's definitions, instructions and reply schema — not the 2,700 of the whole table |
| **4,897** tokens for the worst advisory's prompt | against 8,192 pinned: a 1.7× margin, not the "several times" an 18-advisory corpus suggested |
| **39** tokens of error on the guard's estimate | 0.8%, which is what makes four-characters-to-the-token acceptable in `refuse_overlong_prompt` |

**On its successor, built 2026-09-23T20:20:57Z, the count is 1,189.** That
database replaced the pinned one on this machine on 2026-09-24. Debian 11 rises
from 608 to 610 and every other scan is unchanged. The only two advisories in
the Debian scan published between the builds are `CVE-2026-86805` and
`CVE-2026-95818`, both against `glibc` 2.31-13, published on 2026-09-22 at
16:18 and 17:17 UTC, which accounts for the rise. The pinned database's list
was not kept, so they are identified by date, not by comparing the lists, and
5 of the 610 carry no publication date.

`redaction_gaps.py` on the successor gives 880 advisories carrying an `x.y`
number where the table says 878, and every other redaction count the same. The
longest advisory is still `GHSA-pw6j-qg29-8w7f` at 17,893 characters.
`prompt_tokens.py` has not been run on it, so its three token counts are the
pinned database's alone.

The corpus supersedes an earlier 153-advisory measurement — 18 vulnscout
advisories and 135 from a PyPI manifest that was never committed. That manifest
is why this folder exists.

## Two limits, stated

**The Ubuntu rootfs was dropped.** A `rootfs/ubuntu` built the same way as the
Debian one returned 0 findings: Trivy keys Ubuntu advisories on Ubuntu package
versions, and the Debian version strings it was given match nothing. Fixing it
means sourcing real Ubuntu versions, which nobody has needed yet.

**RHSA is untested by occurrence.** Red Hat advisories need an rpm database,
which is a binary format this folder cannot synthesise offline. So the claim
that `RHSA-` identifiers do not appear in advisory text rests on their absence
from seven scans that do not index them — it is an untested namespace, not a
measured zero. The same holds for any feed reached only through an OS this
corpus does not cover.

## Council runs

Four audits of `fetched/vulnscout` in two baselines, each written straight into
`council_runs/` as it ran, never copied there afterwards. **The two baselines
must not be diffed against each other:** placement, second member, call order
and Ollama version all changed between them. Each of the four left the first
three files below; a run recorded now leaves all five:

| File | What it is |
|---|---|
| `*.report.txt` | the text report. For a run recorded now, the text rendering copied byte for byte from the audit's `reports/`, whatever `--format` said; for the four here, their stdout, which was the text rendering |
| `*.progress.txt` | stderr, the whole stream: one line per model call, printed before the call. A run recorded now ends with one line more, naming the reports it wrote in a working directory that is gone by the time the run is kept; the four here predate that line |
| `*.provenance.txt` | the command, the commit, the uncommitted `src/` files at launch, start, end and exit code; for the GPU runs, `ollama ps` at launch and at the end as well |
| `*.report.json` | the audit record, copied byte for byte: every member's answer on every metric, a settled one included; none of the four has one |
| `*.report.html` | the page, copied byte for byte; none of the four has one |

Progress is `.txt` and not `.log` because `.gitignore` ignores `*.log`, and a
log saved that way would be left out of a commit without a word.
`git check-ignore measurements/council_runs/*` prints nothing: every file here
is committable.

`record_council_run.py` wrote the GPU runs; an earlier wrapper, which recorded
no `ollama ps`, wrote the CPU runs. Both GPU provenance files carry the same
sections in the same order, and `78a0390` holds the recorder as it stood after
the GPU runs, at its 19:56:50 write.

The recorder changed around the GPU runs. **These times were read before the
work was committed and cannot be read again**: committing rewrote every file's
modification time, the recorder's included.

| When | What | Whose record |
|---|---|---|
| 19:47:51 | the last edit to the recorder's docstrings, during `gpu-scoped` (launched 19:46:18) and before `gpu-full` launched at 19:48:13 | `python-developer`'s own report of the edit |
| 19:56:50 | the recorder's last write, after `gpu-full` ended at 19:55:16 | its modification time, read by the judge before the commits |
| — | that write changed the usage example from `gemma4:latest` to `llama3.2:latest`, held back until the recording was done | the session's record, not a file time |

**The tool did not time any run:** `src/` reads no clock. The start and end are
the wrapper's, taken outside the process, and cover the whole command, the
Syft and Trivy scan as well as the council.

| | `scoped` | `full` | `gpu-scoped` | `gpu-full` |
|---|---|---|---|---|
| second member | `gemma4:latest` | `gemma4:latest` | `llama3.2:latest` | `llama3.2:latest` |
| where the models ran | CPU | CPU | GPU | GPU |
| call order | metric by metric | metric by metric | member by member within a finding | member by member within a finding |
| Ollama | 0.34.2, one server started 2026-09-21 10:26:14 | the same server | 0.34.3, one server started 19:30:20 | the same server |
| code | `4111b95`, `src/` unmodified | `4111b95`; three `src/` docstrings edited, no code | launched at `4111b95` with 14 uncommitted `src/` files; the code of `061361f` | launched at `4111b95` with 17; the code of `061361f` |
| findings put to the council | 5 of 18 | 18 of 18 | 5 of 18 | 18 of 18 |
| model calls | 80 = 5 × 8 metrics × 2 members | 288 = 18 × 8 × 2 | 80 | 288 |
| started | 17:25:39 | 17:46:36 | 19:46:18 | 19:48:13 |
| ended | 17:46:36 | 18:58:15 | 19:48:12 | 19:55:16 |
| wall clock | 20 min 57 s, **shared Ollama with another run** | 71 min 39 s, **shared the CPU with test runs** | 1 min 54 s | 7 min 3 s |
| exit code | 1 | 1 | 1 | 1 |
| vectors reached | 0 of 5 | 0 of 18 | 1 of 5 | 4 of 18 |
| metrics settled, contested, unresolved | 18, 17, 5 of 40 | 67, 61, 16 of 144 | 29, 4, 7 of 40 | 105, 13, 26 of 144 |

All on 2026-09-23, UTC+8. Ollama lists `qwen2.5:7b-instruct` as `845dbda0ea48`
and `gemma4:latest` as `c6eb396dbd59`, both pulled before any run here, and
`llama3.2:latest` as `a80c4f17acd5`, pulled between the baselines. The CPU full
run's `src/` edits are the docstring corrections that point here; parsed with
docstrings removed, all three files match `4111b95`.

**The GPU runs' code is `061361f`.** Both were launched at `4111b95` with
uncommitted `src/` files, which the provenance names and does not hold.

What can be checked today is a compare of the parsed code with docstrings
removed. At `061361f`, `src/council/redaction.py`, `src/report/record.py`,
`src/report/text_report.py`, `src/deps/syft_report.py` and
`src/organisation/approval.py` differ from `4111b95` in docstrings alone. The
first three are the files `gpu-full` launched with beyond `gpu-scoped`'s, so
`gpu-scoped` ran them as `4111b95` holds them; neither provenance file names
the last two, so both runs did. In each case that is `061361f`'s code.

Everything else depends on the judge's reading of modification times before
the commits, which cannot be repeated: every `src/` file changed after the 19:46:18
launch matched `061361f` once docstrings were removed, and every other modified
file was last written before the launch.

**The GPU baseline is faster, and no single change is why.** A full run took
7 min 3 s against 71 min 39 s, and a scoped one 1 min 54 s against 20 min 57 s,
or against 13 min 56 s for the lost earlier scoped run below. Placement, the
second member, the call order and the Ollama version changed together, and the
CPU full run shared its CPU with test runs. The speed-up is measured; how much
of it each change bought is not.

## The GPU baseline

### Llama 3.2 guesses rather than declines

**Wherever the report shows its answer, `llama3.2:latest` never declined.** The
report names each member's answer only on the metrics that did not settle, and
on those the second member answered like this:

| Second member, full run | verified quotation | quotation not in the advisory | guessed, nothing quoted | declined |
|---|---|---|---|---|
| `gemma4:latest`, 77 unsettled metrics | 61 | 0 | 7 | 9 |
| `llama3.2:latest`, 39 unsettled metrics | 13 | 10 | 16 | 0 |

`gpu-scoped`'s 11 unsettled metrics are among the 39, answered identically. The
prompt says "Declining is a correct answer. Guessing is not."
(`src/council/prompt.py`), and `docs/COUNCIL.md` says a member that cannot find
supporting text must say so rather than guess.

**More settled is less cross-checked, not better read.** A guess weighs nothing
and a quotation that is not in the advisory supports nothing
(`src/council/chairman.py`). So where Qwen's quotation verifies and Llama
guesses or quotes what is not there, Qwen settles the metric alone, and nothing
can contest it. 105 settled against 67, and 13 contested against 61, is
therefore no evidence of better reading. On a metric settled that way the
council is one assessor, and these reports do not say so: `single_assessor`
counts the members reached, and both were. How many of the 105 rest on Qwen
alone is not in these files, because the report names no member on a settled
metric.

**In these reports, the basis wording reads as agreement.** 99 of the 105 carry
"every member that offered a quotation supported this value". The chairman
that rendered them used that wording when only Qwen quoted, and it reads as two
members agreeing. With a second member that guessed on 16 of the 39 metrics
where its answer is shown, that was not a rare case.

**The code now tells the case apart; the recorded reports do not.** A value
one member quoted, beside members that guessed, declined or failed, now carries
the `SOLE` basis, "one member offered a quotation, and no other member offered
one" (`src/council/ruling.py`), and `AGREED` needs two or more members
offering quotations for the value. These reports were rendered before that
change and keep the old wording, so how many of the 99 would now read `SOLE`
is not in them. A second member's quotation that is not in the advisory still
counts toward `AGREED` (`docs/COUNCIL.md`, "What the chairman does").

**The code now also marks a vector that rests that way whole.** One all eight
of whose metrics read `SOLE` is marked `every metric on one member's quotation,
nothing cross-checked`, and the JSON carries `nothing_cross_checked`. The four
vectors `gpu-full` reached predate the mark and the `SOLE` basis both, so
whether any would carry it is not in these reports; a run recorded now carries
the mark, and its kept JSON names every member on every metric.

### What the baseline does not show

**The headline disagreement belongs to Qwen and Gemma.** `CVE-2021-4279`'s
Attack Vector, `A` from Qwen and `N` from Gemma on the same verified sentence,
is contested at lines 63–67 of `scoped.report.txt` and `full.report.txt`. In
both GPU runs that metric settled: it is missing from the finding's
could-not-settle list, and the report does not say who quoted. What
`docs/COUNCIL.md` builds on it rests on the CPU baseline alone.

**The four vectors it reached do not score as the published ones do.** Council
scores are `src/cvss/score.py` run on the vectors in `gpu-full.report.txt`:

| Finding | Published | Council vector | Council score |
|---|---|---|---|
| `CVE-2026-4800` | ghsa 8.1, nvd 9.8, redhat 8.1 | `AV:L/AC:H/PR:H/UI:R/S:C/C:H/I:H/A:H` | 7.2 |
| `CVE-2026-16221` | 7.5, two sources agreeing | `AV:L/AC:H/PR:H/UI:R/S:C/C:H/I:H/A:L` | 7.2 |
| `CVE-2026-18446` | 7.5, two sources agreeing | `AV:L/AC:H/PR:L/UI:R/S:C/C:L/I:L/A:L` | 5.0 |
| `CVE-2026-53550` | 5.3, two sources agreeing | `AV:L/AC:H/PR:H/UI:R/S:C/C:H/I:H/A:H` | 7.2 |

All four read `AV:L`, `AC:H`, `UI:R` and `S:C`. Three are findings whose
published sources already agreed. `gpu-scoped` did not ask about them, and in
`gpu-full` the council's vector moved their organisation risk:
`CVE-2026-53550` from 15.9 to 21.6, `CVE-2026-18446` from 22.5 to 15.0,
`CVE-2026-16221` from 22.5 to 21.6. All three stay Low.

**Within the baseline, the two runs agree.** `gpu-scoped` and `gpu-full` agree
byte for byte on all five findings they share, with no other client on the
server. Each member's turn on a finding began on a freshly loaded model, so no
cached prompt prefix carried over from an earlier finding. That fits the CPU
baseline's precondition without testing it.

It is likely also what their agreement rests on. A probe since found Qwen
answering one prompt `confidence: medium` on a freshly loaded model and `high`
straight after it, each state repeating byte for byte (`docs/COUNCIL.md`). So
on a card that holds both members at once, where Qwen's turns start warm, these
two runs would not be reproduced — inferred, not measured. The probe and its
envelopes are in `thinking_and_load/`.

### Both models ran on the GPU

| Evidence | What it shows |
|---|---|
| `ollama ps` in both `gpu-*.provenance.txt` | `llama3.2:latest` at `100% GPU` at the end of `gpu-scoped` and at both ends of `gpu-full`; `qwen2.5:7b-instruct` is in neither, because it was not loaded at those moments |
| Ollama's journal, each model load | 10 loads during `gpu-scoped` and 36 during `gpu-full`, one per member per finding, every one `offloaded 29/29 layers to GPU` into a `CUDA0` buffer: 4,168 MiB for Qwen, 1,918 MiB for Llama |
| the journal, each request | 80 and 288 generate requests, exactly the runs' own: no other client |
| the journal, the server | one process, 0.34.3, started 19:30:20 with `library=CUDA` on the RTX 3070 and not restarted during either run |

So Qwen's placement is evidenced by the journal alone, the same as both models
in the CPU baseline.

## The CPU baseline

### Both models ran on the CPU

**No file here records where the CPU runs' models ran.** Their provenance files
hold no placement, so the evidence lives outside this folder:

| Evidence | What it shows |
|---|---|
| Ollama's journal, `journalctl -u ollama`, the `inference compute` line at each server start | `library=cpu` at every start up to 19:24:33 on 2026-09-23; the server behind both runs started 2026-09-21 at 10:26:14 and was next restarted at 19:11:49, after the full run ended |
| the same journal, at each model load | host memory only, and no mention of CUDA or a GPU, for all six loads from 15:00 to 19:00 that day |
| `ollama ps`, read during the full run | both models at `100% CPU`; seen, not saved |

The machine's RTX 3070 has 8 GB and sat idle through these runs, about 2.7 GB of
it held by the display server. `gemma4:latest` is 9.6 GB, more than the whole
card, and the two members together are 14.3 GB by `ollama list`.

That explains the timings. It also limits what the runs can be compared with,
because **where a model runs is itself a way its output can move at
temperature 0**.

**Ollama was switched to the GPU after these runs.** Its first start reporting
`library=CUDA` on the `NVIDIA GeForce RTX 3070` is 19:30:04 on 2026-09-23,
after the full run ended at 18:58:15. The server had already moved from 0.34.2
to 0.34.3, at 19:16:17.

**The CPU runs asked Gemma with no `think` field.** On Ollama 0.34.3
`gemma4:latest` answers the one prompt probed, sent with no `think` field,
exactly as with `think: true`: 554 prompt tokens against 552 with
`think: false`, a byte-identical reply, and no `thinking` field in the envelope
(`thinking_and_load/`). That the two tokens are a thinking-mode marker is
inferred, since the built-in renderer Ollama uses for Gemma was not read. That
0.34.2 did the same is inferred too and cannot be checked: that server is gone,
and the CPU reports keep no envelopes or token counts. The code now sends
`think: false`, so a Gemma run today is a different instrument, not a repeat of
`scoped` or `full`.

### Neither CPU time is a benchmark

**Each for a named reason.** Ollama's log counts the requests each run shared
the server with: 136 generate requests completed during the scoped run — its
80, and 56 from a second scoped run started from 17:25:39 to 17:42:12 to check
the command, whose output was lost — and 288 during the full run, exactly its
own. Between 17:15 and 19:00 the server completed 448, which is the three runs
and nothing else. The full run had the server to itself but not the CPU: from
about 17:58, a code review and a developer ran the test suite and mutation
tests beside it, and CPU inference slows directly under that. At 18:17, 30.5
minutes in, it had made 167 of its 288 calls; the other 121 took 41 minutes.

### Two earlier runs, whose files were lost

The same command ran twice before, over all 18 findings at `a522b39` and over 5
on the tree later committed as `f0b19e8` and `b3fd84f`. Their files were in a
session scratch directory, and were deleted there at about 17:23 before they
were copied here. What survives is what was measured from those files before
the deletion:

| | Earlier full | Earlier scoped |
|---|---|---|
| started, the report file's creation | 15:17:31.9 | 16:36:43.1 |
| ended, its last write | 16:15:36.4 | 16:50:38.9 |
| wall clock | 58 min 4 s | 13 min 56 s |
| report | 315 lines, 21,969 bytes | 217 lines, 13,368 bytes |
| progress | 288 lines, 19,188 bytes | 80 lines, 5,023 bytes |
| metrics settled, contested, unresolved | 67, 61, 16 of 144 | — |

The times came from `stat`, and the earlier full run shared the machine with the
test suite and a headless browser. They are measurements whose artefacts are
gone, superseded by the runs above. Figures of 6.0 s a call for Qwen and 25.8 s
for Gemma are from none of these runs: they came from one probe of one metric.

The earlier full page was rendered by `src/report/text_council.py` as it stood
at `a522b39`. It cut quotations at 60 characters and marked each one `quoted` or
`not in the advisory`, and `quoted` reads as "offered a quotation" where it
meant "verified". The counts above do not depend on the rendering.

The earlier scoped run's code can only partly be checked against `4111b95`.
`git diff f0b19e8 b3fd84f -- src/council/runner.py` is a docstring and nothing
else; every other file's modification time was rewritten when the work was
split into two commits.

### The full run reproduced; the scoped re-run did not

**The full run matches the earlier full run exactly.** Both come to 67 metrics
settled, 61 contested and 16 unresolved of 144, and 0 of 18 vectors — two and
a half hours, three commits and a renderer change apart. The earlier run overlapped two
single probe calls to both members and still came out the same. That is the
strongest reproducibility evidence here: a real file against figures counted
from the lost one before it was deleted.

**The scoped re-run does not match the earlier scoped run.** It is 230 lines
and 14,255 bytes against 217 and 13,368: 13 lines and 887 bytes longer. The
progress logs are the same size as the lost ones, 80 lines and 5,023 bytes, and
288 and 19,188, because a progress line carries no answer.

**Where the scoped reports differ is not independently verifiable.** The first
28 council lines — all of `CVE-2021-4279` and the opening of `CVE-2025-13465` —
reproduce byte for byte, checked against verbatim tool output from the earlier
run that this repository does not hold. Nothing else of the earlier report
survives verbatim. A transcription of it, taken from an agent's reading before
the deletion, puts the whole difference in `CVE-2026-2950`: Attack Vector
settled then and unresolved now, Scope settled then and contested now.

Two real files corroborate that account without verifying it. In the re-run
those two metric blocks are lines 150–155 and 163–169, 880 bytes, and naming
them in the heading adds `AV, ` and `S, `, 7 more: exactly 887 bytes and 13
lines. And the two re-runs agree byte for byte on four of the five findings they
share, and differ on `CVE-2026-2950`:

| | `CVE-2026-2950` |
|---|---|
| scoped re-run, `scoped.report.txt` line 146 | 3 settled · could not settle AV, PR, S, C, A |
| full re-run, `full.report.txt` line 359 | 5 settled · could not settle PR, C, A |

The full run settles Attack Vector and Scope, the two metrics the transcription
says the earlier scoped run settled.

### What that makes likely, and what it cannot show

Both members were pinned as the code then did it: temperature 0 and a fixed
seed, and no `think` field, which `src/council/ollama.py` has since added. The
outlier is the one run made while another council run shared the Ollama
server, on exactly the metrics that moved. Brief concurrency, two
probe calls, changed nothing detectable; a concurrent 80-call run changed one
finding of five.

**That makes contention the likely cause. It does not test it**, because more
than contention differs between the two re-runs:

| | Scoped re-run | Full re-run |
|---|---|---|
| another client's requests during the run | 56 | 0 |
| calls before `CVE-2026-2950` was asked | 48 | 256 |
| where the models ran | CPU | CPU |
| model server processes | loaded 17:20:45 and 17:21:12 | the same two, never reloaded |
| requests served at once per model | 1, `OLLAMA_NUM_PARALLEL:1` | 1 |

Call order is the difference that is not ruled out. Requests are never batched
together, placement is the same, and the processes are the same. The candidate
mechanism is the server's reuse of a cached prompt prefix: the request that came
before decides what is reused, and both call order and another client's
requests change that. It is a candidate, not a finding. The runner has since
changed to ask member by member, the GPU baseline's order, so repeating this
one needs the runner at `4111b95`.

### A quotation from the prompt, caught

In the scoped re-run, `scoped.report.txt` lines 150–155, Qwen answered `AV:L` on
`CVE-2026-2950` and gave as its evidence *"The attacker works through read,
write or execute capabilities on the machine…"*. That sentence is not in the
advisory. It is the prompt's own definition of `AV:L`, word for word, from
`src/council/definitions.py`, and the reply schema in `src/council/prompt.py`
asks for a quotation "from the advisory above, never from the metric
definition".

The quotation check refused it, `quotation not found in the advisory`, so the
answer carried no weight and the metric came out unresolved rather than settled
on a definition. That is the evidence rule doing what it exists for, on a real
run, against the failure the prompt names.

## What the runs support

| Claim | Where it is made | Evidence |
|---|---|---|
| Qwen and Gemma quoted the same sentence about `CVE-2021-4279` and gave different Attack Vector values, both verified | `docs/COUNCIL.md` | lines 63–67 of `scoped.report.txt` and `full.report.txt`: `A` and `N`, both on `'The attack can be initiated remotely.'`; in the GPU baseline that metric settled |
| the same on `CVE-2025-13465` Privileges Required | — | `scoped.report.txt` lines 80–86: `L` and `N`; Confidentiality and Integrity on the same sentence follow at 87–100 |
| that shape is common, not one case | `docs/COUNCIL.md` | 8 of `scoped`'s 17 contested metrics, and 20 of `full`'s 61, have both members quoting identical text; in the GPU baseline, 2 of 4 and 4 of 13 |
| 61 of 144 metrics came out contested with two members | `src/council/runner.py`, `docs/COUNCIL.md` | `full.report.txt`, Qwen and Gemma; the GPU baseline contests 13 |
| reproducible when no other client shares the Ollama server, and each model meets each request in the same load state | `docs/COUNCIL.md` | the CPU baseline's subsections above, the GPU runs agreeing on the five findings they share, and Qwen cold and warm in `thinking_and_load/probe_state.jsonl` |
| 288 calls over 18 findings, 80 after scoping | `README.md`, `docs/COUNCIL.md`, `docs/diagrams.md`, `src/cli/council_run.py`, `src/cli/progress.py`, comments in `tests/cli/test_council_run.py`, `tests/cli/test_progress.py` and `tests/council/test_runner_order.py` | the last `council` line of each progress file |
| 13 of 18 findings undisputed, so 5 put to the council | `README.md`, `docs/COUNCIL.md`, `docs/diagrams.md`, `src/cli/council_run.py`, `tests/cli/test_council_run.py` | `scoped.report.txt` lines 218–222 |
| 208 of the 288 calls went to those 13 | `src/cli/council_run.py`, `tests/cli/test_council_run.py` | the lines of `full.progress.txt` and of `gpu-full.progress.txt` naming them |
| one member answers every metric of a finding before the next member is asked | `src/council/runner.py`, `README.md`, `docs/COUNCIL.md` | `gpu-*.progress.txt`: 10 and 36 runs of 8 calls to one member; `scoped` and `full` change member on every call |
| the CPU baseline ran on the CPU | `docs/COUNCIL.md`, `src/cli/progress.py` | Ollama's journal and `ollama ps`, above: nothing in this folder records it |
| the recorded full run took about an hour with the models on the CPU | `src/cli/progress.py` | `full.provenance.txt`, 71 min 39 s, and the lost earlier full run, 58 min 4 s: both whole commands on a shared CPU, so neither is a benchmark |
| `llama3.2:latest` guesses rather than declines | `docs/COUNCIL.md` | 0 declines and 16 guesses on the 39 unsettled metrics of `gpu-full.report.txt`, the only ones where a report shows its answer |
| no Qwen–Gemma run reached a vector | `docs/diagrams.md` | 0 of 5 and 0 of 18: every council heading in `scoped` and `full` says `no vector`; the GPU baseline reached 1 of 5 and 4 of 18 |

## Regenerating them

**One run at a time, with nothing else asking the same Ollama server.** Every
run needs Ollama with its members pulled, Syft, Trivy, and the advisory database
built 2026-09-22T02:00:05Z; a newer database can find different advisories,
and every count above can move with it. The recorder runs the command after
`--` and writes five files into `council_runs/`, refusing a name if any of the
five already exists:

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
python measurements/record_council_run.py gpu-scoped-again -- \
    audit fetched/vulnscout --answers answers.example.json \
    --council-member qwen2.5:7b-instruct --council-member llama3.2:latest
```

The full run adds `--council-all-findings`. `audit` is the entry point of the
editable install in `README.md`, so the venv must be active; the recorder
refuses to start without it on the path.

The audit does not run in the project root. It runs in a temporary directory
named `council-run-…`, which holds a link to every top-level entry of the
project but `reports/`, so relative paths in the command resolve as written,
the report still reads `Audit of fetched/vulnscout`, and the project's own
`reports/` is never written. All three renderings are copied out byte for byte
before that directory is removed, whatever `--format` the command gave.

Stdout is not kept. When the audit ran it is one of the three; when it could
not run it is nothing, and the reason is on stderr, which the progress file
keeps. **One edge loses a rendering:** an audit whose scan ran and whose report
write then failed exits 2, and its stdout, which held the only full rendering,
is not kept.

The recorder exits with the audit's code. An audit that exits 0, 1 or 3 without
leaving all three renderings makes it exit 2 instead, after copying those it
did write. An audit that exits 2 is recorded with whichever it wrote, which is
none unless a report failed to write after the scan.

Repeating the GPU baseline needs `061361f` and Ollama 0.34.3 with both models
on the GPU, on a card that cannot hold them together, so that every member's
turn starts cold as it did then. `061361f` sends no `think` field, which for
Qwen and Llama made no difference on the one prompt measured. Repeating the CPU
baseline needs `gemma4:latest`, the runner and client at `4111b95`, which send
no `think` field, and Ollama 0.34.2 on the CPU; this machine's Ollama has
started on CUDA since 19:30 on 2026-09-23.

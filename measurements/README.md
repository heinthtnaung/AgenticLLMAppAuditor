# Measurements

The corpus behind the numbers in `src/council/redaction.py`,
`src/council/ollama.py`, `src/council/definitions.py` and `docs/COUNCIL.md`,
and the council runs behind the counts in `src/cli/`, `src/council/runner.py`,
`README.md`, `docs/COUNCIL.md` and `docs/diagrams.md`, and behind the one
timing the code gives, in `src/cli/progress.py`. It also holds a harness that
scores the council against published vectors, and what its first run found.

A measurement nobody can re-run is an assertion. Everything here exists so a
reader can disagree with a number by producing a different one.

## What is here

| Path | What it is |
|---|---|
| `corpus/pypi`, `corpus/npm`, `corpus/golang`, `corpus/rust` | four handwritten manifests pinning deliberately out-of-date packages |
| `rootfs/debian`, `rootfs/alpine` | two synthetic root filesystems: an `os-release`, a version marker and a package database listing old packages |
| `advisories.py` | runs the seven scans and reads them into one set of advisory texts |
| `redaction_gaps.py` | what `council.redaction` catches, lets past, and would cost to widen |
| `prompt_tokens.py` | what a member's prompt costs a model, counted by that model: the pinned one, or each one named |
| `prompt_tokens.2026-09-25.txt` | that count on 2026-09-25 for `qwen2.5:7b-instruct`, `llama3.2:latest`, `gemma4:latest` and `qwen2.5-coder:7b-instruct` |
| `record_council_run.py` | runs one council audit and keeps what it printed and wrote beside what produced it |
| `run_provenance.py` | what a recorded run was launched from and how it ended: git and `ollama ps` at launch, the clock and `ollama ps` at the end |
| `run_directory.py` | where a recorded audit runs, so the project's `reports/` is never written, and the copying out of its three renderings |
| `council_runs/` | audits of `fetched/vulnscout` with a two-member council: what each run printed or wrote, and when |
| `thinking_and_load/` | a probe of the `think` field and of load state on three models: the script, its 22 envelopes, and what they do and do not show |
| `council_eval/` | the evaluation harness, `python measurements/council_eval <step>`: the steps `dataset`, `collect`, `gate` and `score`, and the checks `compare`, `quoting`, `values`, `server-log` and `turns` |
| `council_eval_runs/` | one folder per evaluation: what it ran, every call it saved, an excerpt of the server's journal for each run window, and what each step printed |
| `council_eval_runs/library-vulnscout/`, `reversed-vulnscout/`, `library-reversed-vulnscout/` | the 2 × 2's three variant cells, one pass per model each; `council_eval_runs/README.md` holds the design, fixed before any variant pass, and the results |

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
model. `prompt_tokens.py` additionally needs `ollama serve` up with each model
it names pulled, `qwen2.5:7b-instruct` when it names none
(`python measurements/prompt_tokens.py [MODEL ...]`); it talks to loopback only.
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
| **39** tokens of error on the guard's estimate | 0.8% on Qwen's tokenizer, which is what made four-characters-to-the-token acceptable in `refuse_overlong_prompt`; how much of the window the guard allows is now set by four tokenizers, below |

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
Run on 2026-09-25 over four models, `prompt_tokens.py` gives Qwen the same
421, 4,897 and 39 (`prompt_tokens.2026-09-25.txt`). The file does not name the
database it read; by date it was the successor. On the worst prompt, estimated
at 4,936 tokens, `llama3.2:latest` counts 4,791 (−2.9%), `gemma4:latest` 5,689
(+15.3%), and `qwen2.5-coder:7b-instruct` the same as Qwen. That spread is why
`refuse_overlong_prompt` now allows 75% of the window, where it allowed 90%: at
15% over, a prompt at the limit still leaves an eighth of the window for the
reply.

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
counts the members reached, and both were. How many of the 105 rest on one
member is not in these files, because the report names no member on a settled
metric. The pilot's replay counts 36: 27 on Qwen's quotation alone and 9 on
Llama's ("The pilot", below).

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

None scores inside the range its sources published, and each departs on four
to eight metrics from R1, the published reference the pilot scores against
("The pilot", below).

All four read `AV:L`, `AC:H`, `UI:R` and `S:C`. Three are findings whose
published sources already agreed. `gpu-scoped` did not ask about them, and in
`gpu-full` the council's vector moved their organisation risk:
`CVE-2026-53550` from 15.9 to 21.6, `CVE-2026-18446` from 22.5 to 15.0,
`CVE-2026-16221` from 22.5 to 21.6. All three stay Low.

**That is how the code scored then, and it no longer does.** At `061361f` a
settled vector was weighed in place of every published score, `CVE-2026-4800`'s
included: `gpu-full` printed it as 21.6, Low, and counted one band change in its
heading. The code now weighs the published sources alone and prints the
vector's CVSS base score under the finding, saying the risk score does not use
it. So the four score as a run with no council scores them. With the committed
`answers.example.json`, that run gives 15.9, 22.5 and 22.5 for the three,
`ghsa 24.3 to nvd 29.4`, Medium and Low, for `CVE-2026-4800`, and two band
changes in the heading.

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

The cold case has since been repeated. The pilot below took three passes of
each member with every turn starting from a fresh load, and its clean passes
gave 288 of 288 replies byte for byte the same.

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
it held by the display server. `ollama list` gives `gemma4:latest` as 9.6 GB and
the two members as 14.3 GB together, but those are sizes on disk. Loaded under
Ollama 0.34.3 on 2026-09-24, `gemma4:latest` read 3.2 GB at `100% GPU` in
`ollama ps`, seen and not saved, and the journal put all 43 of its layers on
the card, 2,829.67 MiB in `CUDA0`, while mapping 525.00 and 5,376.00 MiB of its
weights in host memory; what those are was not checked. What kept these runs
off the GPU was the server's `library=cpu`, not Gemma's size.

The CPU placement explains the timings. It also limits what the runs can be
compared with, because **where a model runs is itself a way its output can move
at temperature 0**.

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
| with every turn starting from a fresh load, a member's replies repeat byte for byte | `docs/COUNCIL.md` | `council_eval_runs/pilot-vulnscout/compare.txt`: 288 of 288 across the clean passes, 144 per model |
| 288 calls over 18 findings, 80 after scoping | `README.md`, `docs/COUNCIL.md`, `docs/diagrams.md`, `src/cli/council_run.py`, `src/cli/progress.py`, comments in `tests/cli/test_council_run.py`, `tests/cli/test_progress.py` and `tests/council/test_runner_order.py` | the last `council` line of each progress file |
| 13 of 18 findings undisputed, so 5 put to the council | `README.md`, `docs/COUNCIL.md`, `docs/diagrams.md`, `src/cli/council_run.py`, `tests/cli/test_council_run.py` | `scoped.report.txt` lines 218–222 |
| 208 of the 288 calls went to those 13 | `src/cli/council_run.py`, `tests/cli/test_council_run.py` | the lines of `full.progress.txt` and of `gpu-full.progress.txt` naming them |
| one member answers every metric of a finding before the next member is asked | `src/council/runner.py`, `README.md`, `docs/COUNCIL.md` | `gpu-*.progress.txt`: 10 and 36 runs of 8 calls to one member; `scoped` and `full` change member on every call |
| the CPU baseline ran on the CPU | `docs/COUNCIL.md`, `src/cli/progress.py` | Ollama's journal and `ollama ps`, above: nothing in this folder records it |
| the recorded full run took about an hour with the models on the CPU | `src/cli/progress.py` | `full.provenance.txt`, 71 min 39 s, and the lost earlier full run, 58 min 4 s: both whole commands on a shared CPU, so neither is a benchmark |
| `llama3.2:latest` guesses rather than declines | `docs/COUNCIL.md` | 0 declines and 16 guesses on the 39 unsettled metrics of `gpu-full.report.txt`, the only ones where a report shows its answer; over all 144 in the pilot's passes, 0 declines and 43 guesses |
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

## Evaluating the council

**`council_eval/` scores a roster's readings without asking a model twice.**
`collect` puts every item of a frozen dataset to one model and saves every
call. `gate`, `score` and the checks rebuild any roster from those passes,
through the audit's own runner and chairman, with no model and no scan. One
pass per model buys every roster the models can form.

That rests on two things. The first is the panel rule: a member sees nothing
of another's answer, so what a roster decides is fixed by what each member said
alone (`council_eval/compose.py`). The second is a member's reply not
depending on what was loaded or asked before it. For Qwen it does
(`thinking_and_load/`), so `collect` unloads the model before each item and
every turn starts from a fresh load, as in `gpu-full`. **The cost: the harness
replays rosters whose turns start cold.** A roster run warm, on a card that
holds both members, is not what it measures, and every item costs a model load.

The replay answers only the request that was recorded. It rebuilds each request
with the product's code and refuses one whose fingerprint differs — a prompt
reworded, a redaction widened, a pinning moved — so a pass is never scored
against a question it was not asked (`council_eval/replies.py`).

| Step | What it does | What it needs |
|---|---|---|
| `dataset` | freezes a repository's findings in the audit's own join and order, with the Syft and Trivy versions and when the database was built | Syft, Trivy, and the database in the cache `audit` finds (`README.md`) |
| `collect` | one pass: every item put to one model, the model unloaded before each item, every call saved an item at a time; `--variant` asks in a variant's words (`council_eval/variants.py`) | Ollama with the model pulled |
| `gate` | replays the passes' models as one roster and compares it with a recorded text report; exits 1 on any difference | the files |
| `score` | every roster the passes can build, each model alone up to all together: each metric against R1 and the baseline, each vector beside R1 and the published scores | the files |
| `compare` | two passes of one model, call by call: the same request, a byte-identical reply, a reload part way through an item | the files |
| `quoting` | whose quotation each value settled on one quotation rests on, and which unverified quotations are the prompt's own | the files |
| `values` | each model's replies on each metric: every value it named, its declines and failures, and how many named the option the prompt lists last | the files |
| `server-log` | cuts a journal to its request and load lines | the output of `journalctl -u ollama -o short-iso` |
| `turns` | counts an excerpt's requests and loads, and names every turn not of eight calls | an excerpt |

`dataset`, `collect` and `server-log` refuse to write over a file.

**R1 is the reference: a metric's value where Red Hat's vector and NVD's or
GHSA's read it alike** (`council_eval/reference.py`). Where they do not, R1 has
no value, and a settled answer there is counted beside the rate, not in it. R1
is a measuring stick, not the truth: `docs/COUNCIL.md` names no source the
others are measured against, and two sources agreeing can both be wrong.

**The baseline answers every scored item with R1's commonest value among those
same items**, and lift is the roster's rate minus the baseline's
(`council_eval/measures.py`). It is scored on the items the roster settled, so
a roster that settles few is set against a constant on those same few, not on
all. Picked with R1 in hand, it is the best constant in hindsight.
Intervals are Wilson's, at 95%.

### Taking a pass

**One pass at a time, with nothing else asking the same Ollama server.** The
server's journal is the only witness to another client, so keep an excerpt of
each run window and count its turns. `collect` asks a model; nothing else here
does.

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
R=measurements/council_eval_runs/next-run && mkdir $R
python measurements/council_eval dataset --repository fetched/vulnscout \
    --out $R/vulnscout.dataset.json
START=$(date '+%F %T')
python measurements/council_eval collect --dataset $R/vulnscout.dataset.json \
    --model qwen2.5:7b-instruct --out $R/qwen2.5-7b-instruct.run1.replies.jsonl
python measurements/council_eval collect --dataset $R/vulnscout.dataset.json \
    --model llama3.2:latest --out $R/llama3.2-latest.run1.replies.jsonl
journalctl -u ollama -o short-iso --since "$START" |
    python measurements/council_eval server-log --journal /dev/stdin \
    --out $R/ollama-journal.run1.tsv
python measurements/council_eval turns --excerpt $R/ollama-journal.run1.tsv
```

`dataset` prints `18 items frozen to …`. Run again on 2026-09-25, on the same
database and with the code of the time, it wrote the pilot's dataset byte for
byte. It now writes the Trivy cache relative to the home directory, so a
re-freeze today differs from the pilot's file on line 7 alone: the pilot's
names the cache by its absolute path, and the re-freeze writes
`"trivy_cache": "~/.cache/trivy"`. The 18 findings, their order, the scanner
versions and the database's build time all match; the re-freeze's SHA-256 is
`acaf92c7…`, and the pilot's file keeps `2575a983…`. `server-log` over run 3's
window wrote its excerpt byte for byte. On a window holding both passes and
nothing else, `turns` reads `turns: 36; not of 8 calls: none`.

### The pilot

**`qwen2.5:7b-instruct` and `llama3.2:latest`, three passes each, over the 18
findings of `fetched/vulnscout`**, pinned at temperature 0, seed 11 and
`think: false`, on the database built 2026-09-23T20:20:57Z. The pair is
`gpu-full`'s roster. `council_eval_runs/pilot-vulnscout/README.md` is the
record: what ran and when, the two windows another client shared the server,
and the commands that re-derive every figure below from its files.

**Against R1, the pair scores below the baseline on every metric, and none of
its four vectors lands inside the range its sources published.** What the pilot
cannot show bounds that, so it comes first.

| Limit | Why |
|---|---|
| one repository | 18 advisories, every one npm, from `fetched/vulnscout` |
| one roster | `qwen2.5:7b-instruct` and `llama3.2:latest`: every figure below is theirs, not the tool's, and a model you switch to needs its own evaluation ("Evaluating a model you want to use", below) before its readings are trusted |
| the baseline is perfect by construction on four metrics | on AV, PR, UI and S, R1 gives a single value wherever it has one — `N`, `N`, `N` and `U`, on 16, 15, 16 and 16 findings — so the baseline scores 1.00 there and lift can at best reach 0 |
| a wrong reading and another convention look alike | where the pair departs from R1, the pilot cannot tell a misreading from a different scoring convention for libraries; only labels made by hand from the advisory text can |
| anchoring is untested | Llama's constant values are each the last the prompt lists, below; reading cannot be told from list-order anchoring without a control that reverses the order |

The 2 × 2 below has since put the last two to a control, one wording of the
convention and one pass per cell.

**The harness reproduces a run the product recorded.** The pair rebuilt
offline prints what `gpu-full` printed: 105 settled, 13 contested and 26
unresolved of 144, the same four vectors, and every unsettled line
(`gate.txt`). The dataset is not on `gpu-full`'s database, and the gate is the
check that this did not matter. It sees a settled metric only through its
finding's basis counts and the four vectors, since `gpu-full` names no member
there.

**With every turn starting cold, the replies repeat.** The clean passes —
Qwen's first and third, Llama's second and third, on 2026-09-24 and 2026-09-25
— gave 288 of 288 replies byte for byte the same (`compare.txt`). The two
passes another client shared match too, Llama's four calls reloaded part way
through `CVE-2026-13676` included: all 144 of each model agree across all three
runs.

**The pair against R1, from `pilot.score.txt`.** Scored counts the settled
values R1 has a value for. Each model alone scores below the baseline on every
metric as well.

| Metric | Scored | Agreed with R1 | Rate [95% CI] | Baseline value | Baseline rate | Lift |
|---|---|---|---|---|---|---|
| AV | 11 | 0 | 0.00 [0.00, 0.26] | `N` | 1.00 | -1.00 |
| AC | 14 | 2 | 0.14 [0.04, 0.40] | `L` | 0.93 | -0.79 |
| PR | 9 | 0 | 0.00 [0.00, 0.30] | `N` | 1.00 | -1.00 |
| UI | 13 | 0 | 0.00 [0.00, 0.23] | `N` | 1.00 | -1.00 |
| S | 13 | 1 | 0.08 [0.01, 0.33] | `U` | 1.00 | -0.92 |
| C | 13 | 1 | 0.08 [0.01, 0.33] | `N` | 0.92 | -0.85 |
| I | 12 | 5 | 0.42 [0.19, 0.68] | `H` | 0.58 | -0.17 |
| A | 12 | 2 | 0.17 [0.05, 0.45] | `N` | 0.58 | -0.42 |

Of the 13 contested metrics, R1 has a value for 12. On 6 of them R1's value was
among the verified answers, so the contest kept a value R1 disagrees with out
of a vector. On the other 6, no verified answer matched R1.

**Llama never declines.** Over all 144 metrics it declined 0 times, guessed 43,
and offered 30 quotations that are not in the advisory, 14 of them the prompt's
own definitions (`quoting.txt`). It gave one value throughout on AC (`H`), UI
(`R`) and S (`C`), each the last the prompt lists for its metric.

**In the replay, 36 of the 105 settled values rest on one member's
quotation**, 27 on Qwen's and 9 on Llama's. On those the council was one
assessor, which `gpu-full`'s report could not say.

**Every vector departs from R1, and none scores inside its published range:**

| Finding | Council score | R1 band | Departs from R1 on | Published |
|---|---|---|---|---|
| `CVE-2026-16221` | 7.2, High | High | AV, AC, PR, UI, S, C, A | ghsa 7.5, redhat 7.5 |
| `CVE-2026-18446` | 5.0, Medium | High | all eight | ghsa 7.5, redhat 7.5 |
| `CVE-2026-53550` | 7.2, High | Medium | all eight | ghsa 5.3, redhat 5.3 |
| `CVE-2026-4800` | 7.2, High | High | AV, PR, UI, S | ghsa 8.1, nvd 9.8, redhat 8.1 |

R1 has a value on all eight metrics of all four findings, so each has an R1
band.

**What the tool did with it: a council's vector no longer feeds the
Organisation Risk Score.** Every finding is weighed from its published sources,
and a settled vector is shown beside them with its own CVSS base score, saying
the risk score does not use it (`src/report/council_beside.py`). The council
still runs, and its record is kept whole. That decision rests on this pilot,
with the limits above. What it costs is a finding no source scored: it weighs
technical severity at 0 and stays provisional, even where a council settled a
vector for it.

### The 2 × 2: library guidance and reversed options

**Two controls on the pilot's open questions, crossed.** One adds to the prompt
the first paragraph of the CVSS v3.1 User Guide's §3.7, on scoring libraries,
less its last sentence; the other lists every metric's options in reverse.
Each cell is one pass per model on the pilot's 18 findings, with the pilot's
pinning. `council_eval_runs/README.md` holds the design, fixed before the first
variant pass and held to its digest by a test, and the results. Each cell's
folder holds its passes, journal and what each step printed.

**Option order drives Llama's User Interaction and Attack Complexity, and
Qwen's User Interaction without the paragraph.** With it, Qwen's reversed UI is
mixed, N 10 and R 8. So the pilot's UI:R and Llama's AC:H were the list's
order, not readings. Scope, and Qwen's AC, do not follow the order. Of 18
replies, those naming each value:

| Model | Metric | baseline | reversed | library | library + reversed | Reading |
|---|---|---|---|---|---|---|
| Llama | AC | H 18 | L 12, H 6 | H 18 | L 14, H 4 | order-driven in both pairs |
| Llama | UI | R 18 | N 18 | R 13, N 5 | N 18 | order-driven in both pairs |
| Llama | S | C 18 | C 17, U 1 | C 18 | C 12, U 6 | order-independent in both pairs |
| Qwen | AC | H 16, L 1 | H 16, L 1 | H 17, L 1 | H 16, L 1 | order-independent in both pairs |
| Qwen | UI | R 12, N 2 | N 16, R 2 | R 14, N 1 | N 10, R 8 | order-driven without the paragraph, mixed with it |
| Qwen | S | C 12, U 4 | C 12, U 4 | C 16, U 1 | C 13, U 5 | order-independent in both pairs |

All 18 of Llama's reversed UI answers are guesses with no quotation, in both
reversed cells. Two readings sit exactly on the threshold of 12: Llama's AC
reversed, and Llama's S in library + reversed.

**The library paragraph moved neither model toward the convention.** Read as the
design reads it, the worst case for a library is N on AV, PR and UI and L on
AC. No count toward it rose by the 6 of 18 fixed as a shift, in either order.
The nearest are Llama's UI at +5 in the product's order and Qwen's AV at +4
reversed, and the one change of 6 is Qwen's UI reversed, away from it. Neither
model quoted the paragraph.

What it did change was declining. Qwen declined 12 times of 144 with it,
against 21 without, and 9 against 24 reversed. Llama guessed 51 times against
43, and 74 against 64. That the paragraph's "requires assumptions to be made"
licenses answering where the text is silent is inferred, not tested.

**Against R1, the large rises are in the reversed cells, on AV, PR and UI,**
from 0 agreed to between 3 and 13. Those are three of the five metrics where the
reversal lists R1's value last, so by the rule fixed beforehand the gain is not
credited. Elsewhere the counts move by an item or two either way. Agreed of
scored:

| Metric | baseline | reversed | library | library + reversed |
|---|---|---|---|---|
| AV | 0/11 | 3/8 | 0/13 | 5/10 |
| PR | 0/9 | 6/12 | 0/10 | 9/14 |
| UI | 0/13 | 13/15 | 0/15 | 8/16 |

Every lift in every cell is negative but one: the library cell's on Integrity,
+0.10, on 6 of 10. Of the nine vectors the cells reached, none scores inside
its published range.

**The rule fixed beforehand misfired twice on the other five metrics.** There
it labelled three readings order-driven: Llama's C in both pairs, and Qwen's PR
and I in the library pair, both of Qwen's at exactly 12. Llama's C and Qwen's I
meet the order-independent condition as well, since the value each held, H, is
the option the reversal lists last: the rule gives neither label precedence, so
both apply, and neither means anything there.

- **Qwen's PR did move**, from L 8 in the library cell to N 12, the option the
  reversed order lists last, so that label is sound.
- **Llama's C and Qwen's I did not move.** Llama named H 12 times in the pilot,
  then 13 and 15; Qwen named H 15 times in the library cell, then 12. H is
  listed first in one order and last in the other, and each model named it
  about as often either way. Those two labels are the misfires, and neither is
  evidence of anchoring.
- **Why:** on AC, UI and S the pilot's value was the one listed last, so naming
  the new last option means the value flipped. On the other five that does not
  follow.
- **One reading there is order-independent and nothing else,** Llama's A in
  the baseline pair, at exactly 12: L 14, then L 12. The rest are mixed.

The other moves on those five: Qwen's PR from L 8 to N 11 in the baseline
pair, below the threshold; Llama's AV from L 15 to A 10 and 8, the option
listed third; and Qwen's AV to declining, 12 times, reversed.

**What it cannot show.** Each cell is one pass: the variants were not rerun, so
their passes are taken to reproduce as the pilot's did, not shown to. The
reversal moves every metric's order at once. And the design's limits stand: 18
npm findings, one roster, one seed, one wording of the convention, and R1
constant on four metrics, so lift can at best reach 0 there in any cell.

### Evaluating a model you want to use

**Every finding above is about `qwen2.5:7b-instruct` and `llama3.2:latest`, not
about the tool.** A model you want as a member is a new instrument, and its
readings are not to be trusted until it has been through the pilot's findings
the same way. From the project root, with nothing else using Ollama:

```bash
source .venv/bin/activate
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
M=qwen3:8b                        # the name exactly as `ollama list` prints it, tag included
F=$(echo "$M" | tr ':/' '--')     # qwen3-8b, for file names
# 1. It answers in the council's shape, quotes the advisory, and repeats itself from a cold start
COUNCIL_LIVE_OLLAMA=1 COUNCIL_LIVE_MODEL="$M" python -m pytest -q tests/council/test_ollama_live.py
# 2. The context guard's estimate holds for its tokenizer
python measurements/prompt_tokens.py "$M"
# 3. One pass over the pilot's 18 findings
P=measurements/council_eval_runs/pilot-vulnscout; D=$P/vulnscout.dataset.json
R=measurements/council_eval_runs/$F-vulnscout && mkdir "$R"
START=$(date '+%F %T')
python measurements/council_eval collect --dataset $D --model "$M" --out $R/$F.run1.replies.jsonl
journalctl -u ollama -o short-iso --since "$START" --no-pager |
    python measurements/council_eval server-log --journal /dev/stdin --out $R/ollama-journal.run1.tsv
python measurements/council_eval turns --excerpt $R/ollama-journal.run1.tsv
# 4. Score it alone, beside each model of the recorded pair, and as a council with them
python measurements/council_eval score --dataset $D --replies $P/qwen2.5-7b-instruct.run1.replies.jsonl \
    $P/llama3.2-latest.run2.replies.jsonl $R/$F.run1.replies.jsonl > $R/score.txt
python measurements/council_eval values --dataset $D --replies $R/$F.run1.replies.jsonl > $R/values.txt
python measurements/council_eval quoting --dataset $D --replies $R/$F.run1.replies.jsonl > $R/quoting.txt
```

| Step | What it should show |
|---|---|
| 1, the live test | `3 passed`, or a skip naming the model as not pulled |
| 2, the context guard | `a prompt at the guard's limit: about N of the 8192 pinned`, with N below 8,192; on record, Qwen 6,095, Llama 5,964 and Gemma 7,081 |
| 3, one pass | `turns: 18; not of 8 calls: none`. A model too slow for the 180 s timeout, or refused by the server, shows as failed calls in the `failed` column of `score.txt`'s member table |
| 4, the scores | seven rosters: each model alone, each pair, and all three. Read the new model's rate beside the baseline, its lift, and the values it named; one value throughout is a constant, not a reading |

`collect` refuses a name without its tag, `the server holds no llama3.2`. A
second pass (`run2`) and then `compare --first … --second …` checks that the
model repeats itself. None of it lifts the pilot's limits: on AV, PR, UI and S
lift can at best reach 0, because R1 gives one value there, and 18 npm findings
are one repository.

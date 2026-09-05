# Phase 5 — Audit any repository, and export what it found

**Goal:** take a git URL instead of a local path, and hand a reader something
they can open — HTML and PDF, for both the audit report and the remediation
advice.

**Input:** a repository URL. **Output:** everything Phases 1–4 already write,
plus `report.html` / `report.pdf` and `remediation.html` / `remediation.pdf`.

**Scope rule:** this phase changes what goes *in* and what comes *out*. It does
not change what the tool detects. A detector touched here would move Phase 4's
numbers, and a measurement re-taken because the measurer changed is not a
measurement.

## The flow this plans, and what already exists

```
git URL → pull → surfaces → SBOM → findings → [VEX] → report + remediation → HTML/PDF
   └── 5.1 ──┘   └────── already built ──────┘   5.3    └── built ──┘   └── 5.2 ──┘
```

Three of the five stages exist. `main.py` scans surfaces, runs Syft and writes
`findings.json`; `outputs.py:write_all` renders `report.md` and
`remediation.md` -- `main.py` is at its documented size limit and does not do
the rendering. What this phase adds is a front end, a back end, and one stage
that cannot run yet.

**Composed into one command, after the fact.** `src/pipeline.py` runs the whole
chain for a link -- fetch (or reuse a prior fetch of the same URL, refusing a
same-named other repo by pin comparison), audit, VEX, export -- so
`python src/main.py <https-link>` does end to end what the five stages do
separately. A **local path argument runs the audit alone**, unchanged, which is
the path every no-network test holds; the pipeline launches nothing of its own
and imports no socket, so both process-wide invariants survive it.

## Before starting: four things to settle

**1. The URL front end is a rewrite, not a restore.** `TODO.md` claimed the
implementation and its 78 offline tests were kept on a `phase3/url-fetcher`
tag. That tag does not exist — not locally, not on `origin`, and no reachable
commit holds the code. Plan for writing it, not for checking it out.

**2. This is the first untrusted input the tool has ever taken.** Every path so
far is a local directory the operator chose. A URL is supplied, and `git` will
act on it. These properties are not a checklist to tick at the end -- they are
the task:

- **`https://` only.** `git@` buys SSH's whole surface -- agent, `known_hosts`,
  askpass -- for repositories that are public by definition. Refuse `file://`
  and `ext::` explicitly rather than by omission.
- **A scrubbed environment, because a URL allow-list alone does not hold.**
  `url.<base>.insteadOf` in `~/.gitconfig` or `/etc/gitconfig` rewrites a URL
  that already passed the check, and git reads both regardless of argv;
  `GIT_SSH_COMMAND` and `GIT_PROXY_COMMAND` are inherited. So set
  `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` to `os.devnull` and
  `GIT_TERMINAL_PROMPT=0`, and pass an explicit `env` the way
  `deps/syft_runner.py` already does. "Non-interactive git" as prose does not
  name a mechanism.
- **A timeout**, as `syft_runner.TIMEOUT_SECONDS` has, so a hung fetch is a
  failure rather than a stall.
- **A size cap**, as a named constant. `repo_loader.MAX_FILE_BYTES` bounds one
  file and nothing bounds a clone. When it trips the partial tree is
  **removed**, not scanned.
- **A named download root, and a destination that must not already exist.** A
  validated directory name stops `..`; it does not stop a fetch landing on
  `corpus/vuln-app-1-support-agent` and replacing a pinned fixture, which would
  rot every line number in its grading key.

**Inherited, not new work:** symlinks are already skipped at
`parsing/repo_loader.py:46`, and `.git` is already in `SKIP_DIRS` at any depth,
so a nested one is not a scanning problem. Deleting the top-level `.git` buys
less than it appears -- and `rev-parse HEAD` must run **before** the delete,
since the recorded commit is then the only surviving evidence of what was
fetched.

**3. The offline guarantee changes shape, and three tracked claims must move
with it.** `tests/parsing/test_offline.py` proves a full audit runs under a
socket that refuses to connect. Fetching is a network call. The honest framing
is that *auditing* stays offline and *acquiring* does not -- `.claude/AGENTS.md`
already scopes the guarantee as "at runtime", so the wording exists. Naming the
lines, because "the write-up must say so" is unfalsifiable:

- `README.md`'s "The auditor makes **no network calls**".
- `README.md`'s prerequisites row for **git**, whose "What for" is cloning this
  repository. It becomes a runtime dependency -- and unlike Syft and Ollama it
  does not degrade, it fails.
- `docs/FLOW.md`'s diagram, which already draws an HTML report that does not
  exist.

And make the exemption **structural rather than a naming convention**: add to
`test_offline.py` a named-module socket guard mirroring `test_no_write_commands`
(since moved to `test_offline_containment.py` when the file was split),
so "only the fetcher may reach the network" is asserted rather than arranged.

**4. `schema-keeper` defines the commit record before anything writes it**
(rule 10). The resolved commit goes in an artifact, so which artifact, and the
`SCHEMAS.md` amendment, are settled first. A commit is byte-stable; a fetch
timestamp is not, and must not be recorded.

## Task 5.1 — Audit a repository from a URL

**Do:**

- Write `src/fetch_repo.py`, a command of its own rather than a flag, so the
  audit path stays network-free and testable as such.
- Every safety property above, each proved by a **planted attempt** rather than
  asserted: a `file://` and an `ext::` URL refused, a `..` in the derived name
  refused, a destination that already exists refused, a submodule not fetched,
  a timeout and a non-zero exit each leaving no partial tree behind.
- **Settle the guard collision before writing the code.**
  `tests/test_no_write_commands.py` asserts by set equality that `syft_runner`
  is the only module launching a process, *and* bans the literal `git checkout`
  through `MUTATING_COMMANDS`. Both bite. Name which git subcommands the
  fetcher runs -- `init`, `fetch --depth 1`, `rev-parse` and a checkout of
  `FETCH_HEAD` -- and decide whether `MUTATING_COMMANDS` changes or the fetcher
  avoids the banned spelling. A widened set is **not** sufficient on its own:
  copy the stronger guard that already exists, where
  `test_the_generator_module_launches_syft_and_nothing_else` pins `argv[0]` to
  a constant. Assert the same for the fetcher, that the URL is never `argv[0]`,
  and that the env passed to `subprocess.run` is the scrubbed one.

  **Settled:** the fetcher avoids the banned spelling -- a shallow `clone` does
  the same job as `init` + `fetch` + a checkout in one call, so
  `MUTATING_COMMANDS` was left alone. The process set is now
  `{syft_runner, fetch_repo}`, and the fetcher's own guards live in
  `tests/test_fetch_launch.py`: `argv[0]` is the constant `PROGRAM_NAME`, and
  `_environment()` is asserted by value, not just at its call site.
- Pin what was fetched. A URL names a moving branch; an audit of "whatever was
  on main that day" cannot be repeated. Record the resolved commit in the
  artifacts, the way `corpus/evidence/<app>.manifest.json` pins a fixture.
- Fetch shallow, and delete `.git` afterwards, so the audited tree cannot be
  mistaken for a repository the tool might write to.

**Done when:** a URL produces the same artifacts a local path does, the resolved
commit is recorded, every refusal has a test that plants the attempt, and
`test_offline.py` still passes unqualified for the audit path.

## Task 5.2 — Export the reports as HTML and PDF

**Do:**

- Render from the Markdown the tool already writes, never from the artifacts a
  second time. A second producer of the same prose is a second place for it to
  disagree — the argument that declined `target.json`.
- Name the module. The existing owner is `src/outputs.py:write_all`, already at
  100 lines, so decide before writing: extend it, or split a renderer out
  beside `report.py` and `remediation_report.py`.
- HTML first. Say whether it is a **deliberate subset converter** -- and what it
  refuses, since `report.py` emits headings, tables and fenced blocks -- or a
  dependency. "Needs no renderer worth the name" is not a decision.
- PDF second, and treat the dependency as a real decision: a renderer is a
  third-party package under a stdlib-first rule whose one standing exception is
  the JavaScript parser. Say in `requirements.txt` why it is the second.
- **Generate on demand and gitignore the output.** `docs/report.docx` was the
  cautionary tale in this repository: a tracked binary whose Markdown source
  was gitignored — stale, undiffable, contradicting the code beside it *(since
  dropped by Task 4.9, which tracked the Markdown instead)*. Four more binaries
  on that pattern would have been four more.

**PDF breaks byte-identity, and that must be written down rather than
discovered.** Every PDF writer embeds a `/CreationDate`, so a PDF cannot obey
the convention `SCHEMAS.md` sets. Either pin it from a fixed instant the way a
project-authored VEX document would, or record the exemption with its reason,
as `findings.json` did for model prose.

**This task is downstream of an undecided Phase 4 item.** The `report.docx`
lesson is not "a binary was committed" -- it is "a binary was committed while
its source was gitignored". An examiner reading a clean clone is a real
requirement, and the fix is Task 4.9 deciding to track the Markdown. Settle 4.9
first, or 5.2 re-litigates it. *(Since settled: 4.9 tracked the Markdown and
dropped the binary, and `.gitignore`'s comment now records that decision.)*

**Done when:** both reports render to both formats, the output is gitignored,
and a test asserts the HTML contains what the Markdown asserts — in particular
that the "what was not examined" section survives the conversion, since a
findings list without it reads as a clean bill.

## Task 5.3 — ~~The VEX stage~~ — split: emission shipped, the filter is out of scope

Placed correctly in the flow; the position is settled and stays recorded. The
consuming half was ultimately declared out of scope rather than left blocked.

**Why it could not run as planned** — the measurements are in `TODO.md`'s VEX
entries and are
not restated here, because two copies is how two copies start disagreeing. In
short: `vexctl filter` joins only on advisory-scheme rule ids, four of the five
risk classes are not vulnerabilities at all so only LLM03 is VEX-shaped, and no
upstream VEX document exists for any dependency of any fixture.

**The emitting half shipped; this task is now only the filter.** `emit_vex.py`
and `artifacts/vex.py` author `findings.openvex.json` from the audit's advisory
findings -- one `affected` statement per (advisory, component), the app as the
product and the reaching surface as the evidence. That was the Phase 2 item
"emit VEX rather than consume it", and it needed no upstream publisher. What
follows is about **consuming**, since **declared out of scope**: the two
remaining blockers below are properties of the world, not of missing code, and
a task that cannot close honestly is recorded as closed-won't-do (TODO 5.3
names the revival conditions).

**Two of the three blockers stand, and one new constraint was measured.**
Advisory ingestion felled the rule-id blocker: a `known_advisory` finding's
SARIF `ruleId` is now its CVE/GHSA id, and `vexctl create` emits a
byte-identical document under `SOURCE_DATE_EPOCH`, so the mechanics work end to
end. What remains:

- No upstream VEX document exists for any dependency of any fixture, so there
  is still nothing to *consume*.
- `vexctl filter` ignores the product, so a statement about one component would
  suppress a finding about another.
- **New, and it bounds what may ever be emitted:** this tool may emit
  `affected` but **not** `not_affected`. `mapping.json` holds one entry per LLM
  *surface*, so "no surface reaches this component" is not "the vulnerable code
  is not in the execute path" -- measured on the TypeScript fixture,
  `@langchain/core/messages` is imported by the app's own source while no
  surface reaches it. Emitting `vulnerable_code_not_in_execute_path` from
  surface reachability alone would suppress a real vulnerability in code the
  app runs, which is the worst failure a security tool has. An `affected`
  statement with the reaching surface as its action statement is the honest
  half, and it is the half worth having.

**This task does not gate phase exit.** It appears in no checklist item below,
deliberately — a stage blocked on Phase 2 cannot be a condition of finishing
Phase 5.

**And one ordering decision, which is settled now even though the stage is
not.** VEX belongs before *both* the report and the remediation advice. The
model currently advises from `findings.json` directly, so a finding VEX
suppressed would still be advised on, and the two documents would disagree
about what the app's problems are.

## Phase 5 exit checklist

- [x] A URL produces the artifacts a local path does, and records the commit it
      resolved to, read by `rev-parse` **before** `.git` is deleted.
- [x] Every refusal is proved by a planted attempt: `file://`, `ext::`, `..` in
      the derived name, an existing destination, a timeout, a non-zero exit.
      **One residual gap, stated rather than glossed:** "a submodule is not
      fetched" is asserted structurally — no `--recurse-submodules` in the
      composed argv — because no test in this suite may clone. That proves the
      flag is not passed, not that git will not recurse; the latter rests on
      git's default, which no test here pins.
- [x] `tests/test_no_write_commands.py`'s process-launching set is exactly
      `{syft_runner, fetch_repo}`, the fetcher's `argv[0]` is a constant, and
      the env passed to `subprocess.run` is asserted to be the scrubbed one.
- [x] `tests/parsing/test_offline.py` still passes for the audit path, and
      carries a named-module socket guard so only the fetcher may reach the
      network.
- [x] `schema-keeper` defined where the resolved commit is recorded, and
      `SCHEMAS.md` was amended in the same change.
- [x] The three claims named in item 3 above are corrected in `README.md` and
      `docs/FLOW.md`.
- [x] A test asserts the "What was not examined" heading and `NOTHING_FOUND`
      survive into both HTML and PDF.
- [x] PDF's `/CreationDate` is either pinned or recorded as a written
      exemption with its reason.
- [x] Generated documents are gitignored, and no binary is committed.
- [x] No detector changed: `git diff --stat src/detectors src/checks` is empty
      over the range, and re-running `src/evaluate.py` reproduces the stored
      `evaluation.json`.
- [x] Tests pass; `project-guard` clean on the finished code.
- [x] `TODO.md` ticked in the same change as the work.

## Notes and honest cautions

**The URL front end is the highest-value item in this plan, and not because of
the feature.** Every number Phase 4 reports is bounded by a three-application
corpus — `small_sample` fires on all three, and both systems compared were
authored with those apps visible. Fetching by URL is what makes a larger corpus
cheap, and a larger corpus is the only thing that turns a demonstration into a
measurement. Rank it first for that reason, not for convenience.

**But no Phase 5 task actually grows the corpus, and the handoff must be
written down rather than assumed.** 5.1 makes fetching cheap; adopting a fixture
is separate work — a pinned manifest, a hand-written grading key, a human
verification. `PHASE_4_PLAN.md` also says the corpus grows *before* the next
measurement, never after seeing a result, so the order is: finish Phase 4's
write-up, then adopt fixtures, then re-measure. Phase 5 delivers the capability
and hands it over; it does not deliver the corpus.

**Exports are presentation, and presentation is where overstatement hides.**
`report.md` gives what was *not* examined the same billing as what was found;
that is a deliberate design property, not formatting. If the HTML or the PDF
puts the findings on page one and the gaps on page four, the conversion has
quietly undone the thing the report exists to do. Test the property, not the
file size.

**A tracked binary goes stale and nobody notices.** This project had one —
`docs/report.docx`, built from a gitignored source, contradicting the code in
the same repository until Task 4.9 dropped it for the tracked Markdown. That is
the whole argument for generating exports rather than committing them.

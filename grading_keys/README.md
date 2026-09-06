# Grading keys

A grading key is this project's own hand-written record of what is really in an
audited application — the answer `src/evaluate.py` scores a run against.

**This folder holds no key, and that is a valid state.** The auditor takes any
repository by path or URL, so there is no fixed set of apps to grade. Discovery
answers an empty folder with nothing rather than raising; `src/evaluate.py`
then refuses the run with `no grading key found, so there is nothing to score`
and exit code 1 — a refusal with a reason, not a crash, and not a score of zero.
Until 2026-09-04 this project carried a pinned corpus of three apps; it was
removed because a fixed corpus no longer reflects how the tool is used.

**One key shipped between 2026-09-05 and 2026-09-06** —
`damn-vulnerable-llm-agent`, AI-drafted and `verified: false` — and it was
removed deliberately. It is still in git, and recovering it is one command:

```sh
git show f9bd9ff:grading_keys/damn-vulnerable-llm-agent.ground_truth.json
```

That matters because the figures in [`../docs/REPORT.md`](../docs/REPORT.md)
were measured against it. Read them as the record of a run that happened, not
as one a clean checkout can reproduce; Appendix A there holds the pins each
number was measured against.

## Adding one

Audit the app first, so `artifacts/<system>/<name>/` exists. Then write two
files here — three if you want the regression snapshot — named after **that
same directory**, which is the only join key:

| File | What it is |
|---|---|
| `<name>.ground_truth.json` | the known findings and expected surfaces, by hand |
| `<name>.manifest.json` | the upstream URL and the exact commit taken |
| `<name>.baseline.json` | optional: a snapshot of what the extractor finds today; nothing reads it |

The key and the manifest are specified in [`../docs/SCHEMAS.md`](../docs/SCHEMAS.md).
Then:

```sh
python src/evaluate.py --system agentic_auditor
```

`--draft-key` writes a first attempt into `drafts/`, which git ignores and
discovery never looks in. `python src/promote_key.py <app>` moves a corrected
one up into this folder, and refuses the ones that are not ready yet — reading
its refusals is the shortest description of what a key here must satisfy.

**A key with no manifest is refused rather than scored.** Every line number in
a key is valid only against one commit, so a key that does not say which commit
cannot be reproduced — and a number nobody can reproduce is worse than no
number.

**A key is only as good as the human who checked it.** Each records `source`,
`verified`, `verified_by` and `verified_date`, and a score computed from an
unverified key is qualified in `evaluation.json` rather than reported plain.
Drafting a key with a tool and verifying it are two different facts, and this
project keeps them apart on purpose.

## One rule nothing enforces any more

**At least one entry should sit at a line no extracted surface covers.**

This is not a schema rule and `promote_key.py` does not check it. It came from a
review of the key that used to ship here: every entry in its first draft landed
exactly on a surface the extractor emits, so recall was being measured over a
denominator drawn from the tool's own inventory -- the key could not falsify the
thing it was grading. Three entries were re-anchored or added to fix that.

A test held the property while that key shipped. It could not survive the key's
removal: asserted over a key a test builds, it would only assert the test's own
construction. So if you write a key, this is on you, and nothing will fail if
you skip it.

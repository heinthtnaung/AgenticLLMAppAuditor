# Grading keys

A grading key is this project's own hand-written record of what is really in an
audited application — the answer `src/evaluate.py` scores a run against.

**One key ships, added 2026-09-05: `damn-vulnerable-llm-agent`.** It is
`source: "ai_drafted"` and `verified: false`, so every score it produces carries
`key_ai_drafted` and `key_unverified` — indicative, not thesis-grade, and the
scorer says so on every line. A human reading its five entries against upstream
commit `c0cf9a14` is what removes those two qualifications, at which point
`verified`, `verified_by` and `verified_date` get filled in.

The folder was empty before that, and empty is still a valid state.

The auditor takes any repository by path or URL, so there is no fixed set of
apps to grade. Until 2026-09-04 this project carried a pinned corpus of three;
it was removed because a fixed corpus no longer reflects how the tool is used.
The pins and keys those published figures were measured against are recorded in
[`../docs/REPORT.md`](../docs/REPORT.md) Appendix A, so the numbers still name
their inputs.

## Adding one

Audit the app first, so `artifacts/<system>/<name>/` exists. Then write two
files here — three if you want the regression snapshot — named after **that
same directory**, which is the only join key:

| File | What it is |
|---|---|
| `<name>.ground_truth.json` | the known findings and expected surfaces, by hand |
| `<name>.manifest.json` | the upstream URL and the exact commit taken |
| `<name>.baseline.json` | optional: a snapshot of what the extractor finds today |

All three shapes are in [`../docs/SCHEMAS.md`](../docs/SCHEMAS.md). Then:

```sh
python src/evaluate.py --system agentic_auditor
```

**A key with no manifest is refused rather than scored.** Every line number in
a key is valid only against one commit, so a key that does not say which commit
cannot be reproduced — and a number nobody can reproduce is worse than no
number.

**A key is only as good as the human who checked it.** Each records `source`,
`verified`, `verified_by` and `verified_date`, and a score computed from an
unverified key is qualified in `evaluation.json` rather than reported plain.
Drafting a key with a tool and verifying it are two different facts, and this
project keeps them apart on purpose.

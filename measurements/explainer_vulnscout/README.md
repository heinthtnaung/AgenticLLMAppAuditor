# The explainer on vulnscout's disputed findings

The explainer alone, live, on the 5 vulnscout findings whose published sources disagree:
two models, each under two seeds. The run was made to settle why an earlier live check
kept no explanation for the three findings that disagree on one metric, while it kept
every item on the two that disagree on three.

**The finding:** on a one-metric finding `gemma4:latest` wrote the metric's name, not its
code, and every such item was dropped as "not a disputed metric". Every quotation it gave
was verbatim. `glm-4.7-flash` wrote the code every time and was kept.

## What was run

Prompt `sources-differ-1`, unchanged, was put through the product's own
`council.explanation.explain` about each disputed finding of
`../council_eval_runs/pilot-vulnscout/vulnscout.dataset.json` (sha256
`2575a98327867c3bbc98860cb6d57bdb972a10f26eeaf7ba0b2e74e91bbe0d66`). There was no council
and no scan. The request is the one `council.ollama.build_request` builds, with only the
seed varied: 5 findings × 2 models × 2 seeds, 20 calls, each model's ten made one after
another.

| Finding | Disputed |
|---|---|
| `CVE-2026-13149` | A |
| `CVE-2025-13465` | A |
| `CVE-2026-4800` | AC |
| `CVE-2021-4279` | C, I, A |
| `CVE-2026-2950` | PR, I, A |

- **When:** 2026-09-30, 07:43:55 to 07:47:13 UTC.
- **Code:** HEAD was `a793f68` at the start, and `910778f` was committed part way
  through. Neither changed `src/` or `measurements/` from `848ee82`, and the run imported
  its code once, at the start. The working tree's state at the time was not recorded.
- **Server:** Ollama 0.34.3 on the RTX 3070 (8 GB), with no other model loaded.
  `glm-4.7-flash` held 5.9 of its 18.3 GiB in VRAM, so it ran mostly on the CPU.
- **Pinning:** temperature 0, seeds 11 and 12, `think` false, `num_ctx` 8192, and a
  180 s timeout. No call took more than 37.3 s.

| Model | Digest |
|---|---|
| `gemma4:latest` | `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb` |
| `glm-4.7-flash:latest` | `4475827791a269b02c8ec49b1c3bc1abb5846bacf3fae015b75d33986322d8f6` |

## Files

| File | What it is |
|---|---|
| `replies.jsonl` | the run: a header, then each call's finding, model, seed, prompt version, request, Ollama's envelope without `context`, and the outcome `explain` recorded at the time |
| `summary.txt` | what the explainer's current reading makes of the saved replies, from `summary.py` |
| `probe.py` | the calls, for a re-run |
| `summary.py` | the scoring, from the saved replies alone; `--write` puts it in `summary.txt` and the scored block below |

## What the replies show

These are facts of the file, and no change to the code moves them.
`tests/measurements/explainer_vulnscout/test_explainer_records.py` holds each to it.

- **Gemma named the one disputed metric in words.** It wrote `Availability` three times,
  `Availability (A)` once and `AC (Attack Complexity)` twice. None of the six copied the
  schema's `one of A`. On a multi-metric finding it wrote the bare code every time.
- **Every quotation Gemma gave on a one-metric finding verifies**, as recorded at the
  time: each of the 6 dropped items has `quotation_found` true.
- **Glm wrote the bare code every time.** On `CVE-2026-4800` it offered a second AC
  item under each seed, and that one was dropped as a repeat.
- **As recorded at the time, no item was dropped for its quotation.**
- **The seed changed the reply** on 9 of the 10 model and finding pairs. Only glm on
  `CVE-2026-13149` gave the same reply under both seeds.

## How the replies score

`summary.txt` replays every saved reply through `explain` and counts what is kept. Its
first line names the reading it was scored under: the git blob ids of the two files that
read a reply and sort its items, and of the metric table the reading looks a name up in,
which `git log --find-object=ID` resolves to the commits holding them. The records test
re-derives `summary.txt` byte for byte, and `test_explainer_readme.py` holds this block to
it.

**The ids below name the reading that scored this block.** Any edit to one of those files
changes its id, a docstring's included, so they need not be the ids of any one commit's
change to the reading. The last change to how a reply is read was the commit "Read an
explainer metric written as its name". From it the parser reads a metric written as its
name, alone or in brackets beside its code, so each of the six gemma calls recorded as
dropping its one item keeps it. Under `910778f`'s reading, before that commit, gemma's
one-metric row was 0 of 6 calls explained and 0 of 6 items kept, with all 6 dropped as not
a disputed metric; the other three rows were as they are below.

<!-- scored: begin -->
```text
scored by src/council/explanation_reply.py 52202351be92d76cbcaad2ec6cc885a9898bc526, src/council/explanation.py 83dbbe3200a2c346a93c681d963903d770a4a323, src/cvss/metrics.py 4f2c0035bc23cc66ed589efef2f04cb118a642e9
calls 20; scored otherwise than recorded at the time: 6
gemma4:latest seed 11 CVE-2026-13149
gemma4:latest seed 11 CVE-2025-13465
gemma4:latest seed 11 CVE-2026-4800
gemma4:latest seed 12 CVE-2026-13149
gemma4:latest seed 12 CVE-2025-13465
gemma4:latest seed 12 CVE-2026-4800

gemma4:latest  one-metric   calls 6  explained 6  kept 6 of 6  drops {}
gemma4:latest  multi-metric calls 4  explained 4  kept 12 of 12  drops {}
glm-4.7-flash  one-metric   calls 6  explained 6  kept 6 of 6  drops {'repeat': 2}
glm-4.7-flash  multi-metric calls 4  explained 4  kept 12 of 12  drops {}
```
<!-- scored: end -->

**Re-scoring is one command**, `summary.py --write` below. It rewrites `summary.txt` and
this block together, from the summary's first and last sections, and leaves the rest of
this file as it is. An edit to a file named on the first line changes the block even where
no figure moves. A change to how a reply is read can move the figures as well, and then
the paragraph above should name its commit. The outcomes recorded at the time stay in
`replies.jsonl`, and the second line counts the calls now scored otherwise.

## The decision this settled

Two outcomes were planned before the run. If the drops were "not a disputed metric" with
`ONE OF …` copied from the schema, a placeholder-free schema would be measured. If they
were "unverified quotation", the quotations would be classified and no code changed.
**Neither held as written.** The reason was the first outcome's, but the metric was
written as its name, and no item was dropped for its quotation. What was decided instead
is that the explainer's parser reads a metric named in words, which it does from the commit
"Read an explainer metric written as its name".

## What is inferred, not measured

- **The size.** Three one-metric findings, two seeds, and one digest per model.
- **Why one metric draws a name.** The one-metric prompt differs from the others in its
  single disagreement heading, `A (Availability): …`, and its lone `one of A`. Which of
  the two draws the name was not isolated.
- **The earlier live check.** On 2026-09-28 Gemma kept 0 of the 3 one-metric findings,
  in a run that recorded no reason and no digest. The same pattern here makes this cause
  likely. It does not prove it.
- **Load state.** Each model's first call, seed 11 on `CVE-2026-13149`, loaded it:
  Ollama's `load_duration` is 12.7 s for Gemma and 23.4 s for glm, and no other call's
  is over 0.01 s. On that one finding, seed and load state are confounded.
- **Whether an explanation is right.** The `why` is never checked, and this does not
  check it either.

## How these were produced, and how to re-run

The file was written by a scratch draft of `probe.py` that made the same requests in the
same order. The operator's `.env` was refused by the settings reader at the time, so the
draft passed every setting explicitly: `http://127.0.0.1:11434`, 8192 tokens, 180 s.
Those are the defaults `probe.py` reads through `council.settings`. The draft's header
therefore lacks `server`, `dataset_sha256`, `commit`, `changes` and `started`, which are
stated above; the server was this machine, so a `probe.py` header would carry no
`remote_host` either. It also asked for glm untagged, as `glm-4.7-flash`. `probe.py`
refuses an untagged name, so a re-run names `glm-4.7-flash:latest`.

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
# Re-score the saved replies, no model called: rewrites summary.txt and the block above.
python measurements/explainer_vulnscout/summary.py --write
# Or check the saved summary against a fresh scoring, writing nothing.
python measurements/explainer_vulnscout/summary.py \
    measurements/explainer_vulnscout/replies.jsonl \
    | cmp - measurements/explainer_vulnscout/summary.txt
# Re-run the 20 calls into a new file.
python measurements/explainer_vulnscout/probe.py gemma4:latest glm-4.7-flash:latest \
    --out /tmp/explain.jsonl
```

`probe.py` refuses to write over an existing file. Run it with no other client using the
server. A re-run on other hardware, another Ollama or other weights may rightly differ.
Replacing `replies.jsonl` with one would fail the records test, and the docs citing this
file would need changing with it.

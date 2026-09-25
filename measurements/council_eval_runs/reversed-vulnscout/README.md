# Reversed: the product's prompt with every metric's options listed the other way round

`qwen2.5:7b-instruct` and `llama3.2:latest`, one pass each over the pilot's 18
vulnscout findings, asked in the words of the `reversed` variant. This is one
cell of the 2 × 2. `../README.md` holds the design, the readings fixed before
any variant pass, and the comparison across the four cells. Every figure below
is re-derived from the files here and the pilot's dataset, and none needs a
model.

## What was run

- **Variant:** `reversed`, prompt version `member-base-metric-3+reversed-1`.
  It is the product's prompt with each metric's values listed in the opposite
  order, in the definition lines and in the reply schema's "one of …". Nothing
  else changes, and no paragraph is added.
- **Dataset:** the pilot's, `../pilot-vulnscout/vulnscout.dataset.json`, named
  in each header by its SHA-256, `2575a983…0d66`.
- **Passes:** `python measurements/council_eval collect --variant reversed`,
  Qwen then Llama. The model is unloaded before each item, so every turn
  starts cold.
- **Pinning:** temperature 0, seed 11, `num_ctx` 8192, `think` false, on
  Ollama 0.34.3. Qwen's digest is `845dbda0…` and Llama's `a80c4f17…`.
- **Code:** as for `../library-vulnscout/`: commit `a4e5365`, plus the 37
  uncommitted paths each header lists.

| Pass | Started | Ended |
|---|---|---|
| Qwen | 2026-09-25 10:27:48 +08:00 | 10:31:05 |
| Llama | 10:31:05 | 10:33:11 |

## The journal

`ollama-journal.run1.tsv` covers 10:27:48 to 10:33:12. `turns.txt` counts it:

- 324 generate requests, which is 288 calls and 36 unloads.
- 18 loads of each model, and 36 turns, each of 8 calls.
- The other five requests were this run's own: a `GET /api/ps` before it
  started, then a `GET /api/tags` and a `GET /api/version` for each pass's
  header.
- `GET /api/ps` showed Llama still loaded from the library cell when this
  window opened. The pilot's run 2 started Qwen's pass the same way, with Llama
  loaded, and its Qwen replies matched runs 1 and 3 byte for byte.

## Files

| File | Size | What it is |
|---|---|---|
| `qwen2.5-7b-instruct.run1.replies.jsonl` | 114 KB | Qwen's pass: a header, 144 calls, an end line |
| `llama3.2-latest.run1.replies.jsonl` | 102 KB | Llama's pass |
| `ollama-journal.run1.tsv` | 28 KB | the server's requests and loads for the run window |
| `turns.txt` | 1 KB | the excerpt, counted |
| `reversed.score.txt` | 11 KB | every roster against R1 and the baseline |
| `values.txt` | 1 KB | every value each model named, beside the option listed last |
| `quoting.txt` | 1 KB | whose quotation each lone settlement rests on, and unverified quotations of the prompt |
| `compare.txt` | 4 KB | each model's pass against its pilot pass, call by call |

About 265 KB in all, with this README.

## Re-deriving every figure

As for `../library-vulnscout/`, with `R=measurements/council_eval_runs/reversed-vulnscout`.
The replay rebuilt all 288 requests in the variant's words.

## What it shows, and what it cannot

**UI follows the order for both models in this cell.** With the paragraph as
well, Qwen's UI is mixed: see `../library-reversed-vulnscout/`. Reversal lists
N last on UI:

- Llama named N 18 times of 18, where the pilot had R 18 times. All 18 are
  guesses, values with no quotation.
- Qwen named N 16 times, where the pilot had R 12 times.

**AC follows the order for Llama only:**

- Llama named L 12 times, where the pilot had H 18 times. 12 is exactly the
  threshold.
- Qwen named H 16 times, as in the pilot.

**S does not follow the order.** Llama named C 17 times and Qwen C 12 times,
with C now listed first.

**AV and PR moved, not always to the last option:**

- Llama answered AV with A 10 times, the option now listed third. The pilot had
  L 15 times.
- Qwen declined AV 12 times, against 6 in the pilot.
- Qwen's PR went from L 8 times to N 11 times, N being the option now listed
  last. That is one short of holding it.

**Against R1, the pair's agreement rose sharply on AV, PR and UI:**

- AV 3 of 8, PR 6 of 12, UI 13 of 15. The pilot had 0 on each.
- Those are three of the five metrics on which the reversal lists R1's value
  last. On the other two it did not rise: AC 2 of 8, against 2 of 14 in the
  pilot, and S 0 of 12, against 1 of 13.
- On C, I and A it moved by one item at most: 1 of 11, 4 of 14 and 2 of 13,
  against 1, 5 and 2 in the pilot.
- By the rule fixed beforehand, a gain in the reversed order alone is not
  credited to reading. Lift is still negative on every metric, UI's at −0.13.

**Settled:** 102 metrics, with 12 contested and 30 unresolved. The pair reached
one vector, `CVE-2026-4800`, `AV:N/AC:H/PR:H/UI:R/S:C/C:H/I:H/A:H`. That scores
7.6, against 8.1 from GHSA and Red Hat and 9.8 from NVD.

**What moved at all:** against the pilot, 61 of Qwen's 144 replies and 37 of
Llama's are byte-identical (`compare.txt`). The value changed on 56 of Qwen's
and 59 of Llama's.

**Limits:**

- One pass per model, and 18 npm findings.
- The reversal changes the order of every metric at once, so a metric whose
  answer moved was not moved by its own order alone.

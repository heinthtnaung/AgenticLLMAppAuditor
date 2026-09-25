# Library: the product's prompt and the User Guide's paragraph on libraries

`qwen2.5:7b-instruct` and `llama3.2:latest`, one pass each over the pilot's 18
vulnscout findings, asked in the words of the `library` variant. This is one
cell of the 2 × 2. `../README.md` holds the design, the paragraph itself, the
readings fixed before any variant pass, and the comparison across the four
cells. Every figure below is re-derived from the files here and the pilot's
dataset, and none needs a model.

## What was run

- **Variant:** `library`, prompt version `member-base-metric-3+library-1`. It
  is the product's prompt, with the paragraph quoted in `../README.md` placed
  after the metric's value definitions. The options are in the product's order.
- **Dataset:** the pilot's, `../pilot-vulnscout/vulnscout.dataset.json`, named
  in each header by its SHA-256, `2575a983…0d66`.
- **Passes:** `python measurements/council_eval collect --variant library`,
  Qwen then Llama. The model is unloaded before each item, so every turn
  starts cold.
- **Pinning:** temperature 0, seed 11, `num_ctx` 8192, `think` false, on
  Ollama 0.34.3. Qwen's digest is `845dbda0…` and Llama's `a80c4f17…`, as in
  the pilot.
- **Code:** commit `a4e5365`, plus the 37 uncommitted paths each header lists.
  On a call's path, the differences from the pilot are these:
  - `src/council/ollama.py`: a docstring edit.
  - The harness: `council_eval/variants.py`, and the variant threaded through
    `collect`, the recording client and the replay.
  - The pilot's scored passes still replay and score byte for byte on this
    code, so the product's own request path had not moved.

| Pass | Started | Ended |
|---|---|---|
| Qwen | 2026-09-25 10:17:11 +08:00 | 10:20:48 |
| Llama | 10:20:49 | 10:23:13 |

## The journal

`ollama-journal.run1.tsv` covers 10:17:10 to 10:23:14. `turns.txt` counts it:

- 324 generate requests, which is 288 calls and 36 unloads.
- 18 loads of each model, and 36 turns, each of 8 calls.
- The other five requests were this run's own: a `GET /api/ps` before it
  started, then a `GET /api/tags` and a `GET /api/version` for each pass's
  header.

So the window is clean by the rule in `../README.md`.

## Files

| File | Size | What it is |
|---|---|---|
| `qwen2.5-7b-instruct.run1.replies.jsonl` | 117 KB | Qwen's pass: a header, 144 calls, an end line |
| `llama3.2-latest.run1.replies.jsonl` | 105 KB | Llama's pass |
| `ollama-journal.run1.tsv` | 28 KB | the server's requests and loads for the run window |
| `turns.txt` | 1 KB | the excerpt, counted |
| `library.score.txt` | 13 KB | every roster against R1 and the baseline |
| `values.txt` | 1 KB | every value each model named, beside the option listed last |
| `quoting.txt` | 1 KB | whose quotation each lone settlement rests on, and unverified quotations of the prompt |
| `compare.txt` | 3 KB | each model's pass against its pilot pass, call by call |

About 270 KB in all, with this README.

## Re-deriving every figure

From the project root, with the venv active. None of these asks a model:

```bash
R=measurements/council_eval_runs/library-vulnscout
P=measurements/council_eval_runs/pilot-vulnscout
D=$P/vulnscout.dataset.json
Q=$R/qwen2.5-7b-instruct.run1.replies.jsonl; L=$R/llama3.2-latest.run1.replies.jsonl
python measurements/council_eval score --dataset $D --replies $Q $L
python measurements/council_eval values --dataset $D --replies $Q $L
python measurements/council_eval quoting --dataset $D --replies $Q $L
python measurements/council_eval turns --excerpt $R/ollama-journal.run1.tsv
python measurements/council_eval compare --first $P/qwen2.5-7b-instruct.run1.replies.jsonl --second $Q
python measurements/council_eval compare --first $P/llama3.2-latest.run2.replies.jsonl --second $L
```

Each prints what its file here holds. The replay rebuilds every request in the
variant's words, and refuses any whose fingerprint differs from the recorded one.
It rebuilt all 288.

## What it shows, and what it cannot

- **The paragraph did not move either model toward the convention.** Replies
  naming N went from 1 to 0 for Qwen on AV and from 3 to 2 for Llama. On PR
  they stayed at 0 and 10. On UI they went from 2 to 1 for Qwen and from 0 to 5
  for Llama. L on AC stayed at 1 and 0. None of these reaches the shift of 6 of
  18 fixed beforehand.
- **Its largest moves were toward severity.** Qwen named C on S 16 times, up
  from 12. Its High went from 5 to 9 on C and from 12 to 15 on I. Neither model
  quoted the paragraph as evidence.
- **Qwen declined less:** 12 of 144, against 21 in the pilot. Llama still never
  declined, and guessed 51 times against 43.
- **Against R1 the pair agrees on 0 of 13 for AV, 0 of 10 for PR, 0 of 15 for
  UI and 0 of 15 for S.** The baseline scores 1.00 on each of those. The only
  positive lift in any of the four cells is here, on I: 6 of 10, against a
  baseline of 0.50, with an interval of [0.31, 0.83].
- **Settled:** 111 metrics, with 17 contested and 16 unresolved. The pair
  reached one vector, `CVE-2026-2950`, and it is outside the range the vector's
  sources published.
- **What moved at all:** against the pilot, 75 of Qwen's 144 replies and 77 of
  Llama's are byte-identical (`compare.txt`). The value changed on 35 of Qwen's
  and 23 of Llama's.
- **Limits:** one pass per model, with no rerun of this variant, and 18 npm
  findings. The paragraph is one wording of the convention, and no other
  wording was tried.

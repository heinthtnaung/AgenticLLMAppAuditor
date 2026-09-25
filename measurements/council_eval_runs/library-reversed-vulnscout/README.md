# Library + reversed: the paragraph on libraries, and every metric's options listed the other way round

`qwen2.5:7b-instruct` and `llama3.2:latest`, one pass each over the pilot's 18
vulnscout findings, asked in the words of the `library-reversed` variant. This
is one cell of the 2 × 2. `../README.md` holds the design, the paragraph
itself, the readings fixed before any variant pass, and the comparison across
the four cells. Every figure below is re-derived from the files here and the
pilot's dataset, and none needs a model.

## What was run

- **Variant:** `library-reversed`, prompt version
  `member-base-metric-3+library-1+reversed-1`. It carries both changes: the
  values reversed as in `../reversed-vulnscout/`, and the paragraph placed after
  them as in `../library-vulnscout/`.
- **Dataset:** the pilot's, `../pilot-vulnscout/vulnscout.dataset.json`, named
  in each header by its SHA-256, `2575a983…0d66`.
- **Passes:** `python measurements/council_eval collect --variant
  library-reversed`, Qwen then Llama. The model is unloaded before each item,
  so every turn starts cold.
- **Pinning:** temperature 0, seed 11, `num_ctx` 8192, `think` false, on
  Ollama 0.34.3. Qwen's digest is `845dbda0…` and Llama's `a80c4f17…`.
- **Code:** as for `../library-vulnscout/`: commit `a4e5365`, plus the 37
  uncommitted paths each header lists.

| Pass | Started | Ended |
|---|---|---|
| Qwen | 2026-09-25 10:37:47 +08:00 | 10:41:19 |
| Llama | 10:41:19 | 10:43:29 |

## The journal

`ollama-journal.run1.tsv` covers 10:37:47 to 10:43:30. `turns.txt` counts it:

- 324 generate requests, which is 288 calls and 36 unloads.
- 18 loads of each model, and 36 turns, each of 8 calls.
- Four of the other requests were this run's own: a `GET /api/tags` and a
  `GET /api/version` for each pass's header.
- **One was not: another client's `ollama list`** at 10:38:15, a `HEAD /` and
  a `GET /api/tags`. It asks no model and loads nothing. It fell during Qwen's
  pass, and every turn still holds exactly its 8 calls, so the window is clean
  by the rule in `../README.md`.
- Whether Llama was still loaded from the reversed cell when this window opened
  was not checked.

## Files

| File | Size | What it is |
|---|---|---|
| `qwen2.5-7b-instruct.run1.replies.jsonl` | 116 KB | Qwen's pass: a header, 144 calls, an end line |
| `llama3.2-latest.run1.replies.jsonl` | 101 KB | Llama's pass |
| `ollama-journal.run1.tsv` | 28 KB | the server's requests and loads for the run window |
| `turns.txt` | 1 KB | the excerpt, counted |
| `library-reversed.score.txt` | 13 KB | every roster against R1 and the baseline |
| `values.txt` | 1 KB | every value each model named, beside the option listed last |
| `quoting.txt` | 1 KB | whose quotation each lone settlement rests on, and unverified quotations of the prompt |
| `compare.txt` | 4 KB | each model's pass against its pilot pass, call by call |

About 270 KB in all, with this README.

## Re-deriving every figure

As for `../library-vulnscout/`, with
`R=measurements/council_eval_runs/library-reversed-vulnscout`. The replay
rebuilt all 288 requests in the variant's words.

## What it shows, and what it cannot

**UI is N for Llama on 18 of 18, as in the reversed cell,** and every one is
again a guess.

**Qwen's UI came back part way:** N 10 times and R 8 times, where the reversed
cell had N 16 times. The paragraph moved Qwen's UI 6 replies away from N,
which is the convention's value.

**AC:** Llama named L 14 times and Qwen H 16 times.

**S:**

- Llama named C 12 times and U 6 times. That is 5 fewer C than in the reversed
  cell, and 12 is exactly the threshold for holding C.
- Qwen named C 13 times.

**AV:** Qwen named N 9 times, against 5 in the reversed cell. Llama again
answered mostly A, 8 times.

**Against R1:**

- The pair agrees on AV 5 of 10, PR 9 of 14, UI 8 of 16 and S 2 of 14.
- Every lift is still negative. The nearest to zero is I's, at −0.15.

**Settled:** 108 metrics, with 14 contested and 22 unresolved. The pair reached
three vectors, and none lies inside the range its sources published.

**Neither model quoted the paragraph as evidence.**

**What moved at all:** against the pilot, 57 of Qwen's 144 replies and 37 of
Llama's are byte-identical (`compare.txt`). The value changed on 52 of Qwen's
and 72 of Llama's.

**Limits:** one pass per model, and 18 npm findings. This cell alone cannot
tell the paragraph from the order on AV, PR and UI, where both point to N. It
exists to be read against the other three, in `../README.md`.

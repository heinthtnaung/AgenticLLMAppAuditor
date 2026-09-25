# gemma4:latest on the pilot's 18 vulnscout findings, alone and beside Qwen

One pass of `gemma4:latest` over the pilot's dataset, in the product's words
(the baseline prompt), scored alone and as a pair with the pilot's Qwen pass.
Every figure below is re-derived from the files here and the pilot's, and none
needs a model.

## What was run

- **Dataset:** the pilot's, `../pilot-vulnscout/vulnscout.dataset.json`, named
  in the header by its SHA-256, `2575a983…0d66`.
- **Pass:** `python measurements/council_eval collect --model gemma4:latest`,
  from 2026-09-25 15:57:04 to 16:01:04 +08:00. The model is unloaded before
  each item, so every turn starts cold.
- **Pinning:** prompt `member-base-metric-3`, temperature 0, seed 11, `think`
  false, `num_ctx` 8192, on Ollama 0.34.3. Digest `c6eb396d…`.
- **Settings:** read from the operator's `.env`; the header records
  `timeout_seconds` 12000. No call came near it.
- **Code:** commit `76a4b2c`, plus the 18 uncommitted paths the header lists,
  among them the settings change (`src/council/settings.py`).
- **The pair's Qwen:** the pilot's `qwen2.5-7b-instruct.run1.replies.jsonl`,
  whose requests the replay rebuilds unchanged on this code.

## The journal

`ollama-journal.run1.tsv` covers 15:57:04 to 16:01:05. `turns.txt` counts it:
162 generate requests (144 calls and 18 unloads), 18 loads, and 18 turns of 8
calls. The other two requests are the header's `GET /api/tags` and
`GET /api/version`. Clean. Gemma's weights name themselves `n/a` in the load
line, which is why `turns.txt` counts "18 n/a".

## Files

| File | Size | What it is |
|---|---|---|
| `gemma4-latest.run1.replies.jsonl` | 111 KB | the pass: a header, 144 calls, an end line |
| `ollama-journal.run1.tsv` | 14 KB | the server's requests and loads for the window |
| `turns.txt` | 1 KB | the excerpt, counted |
| `gemma4.score.txt` | 14 KB | Qwen alone, Gemma alone, and the pair, against R1 and the baseline |
| `values.txt` | 1 KB | every value Gemma named, beside the option listed last |
| `quoting.txt` | 1 KB | the pair's lone settlements and unverified quotations |

## Re-deriving every figure

```bash
R=measurements/council_eval_runs/gemma4-vulnscout; P=measurements/council_eval_runs/pilot-vulnscout
D=$P/vulnscout.dataset.json; G=$R/gemma4-latest.run1.replies.jsonl; Q=$P/qwen2.5-7b-instruct.run1.replies.jsonl
python measurements/council_eval score --dataset $D --replies $Q $G
python measurements/council_eval values --dataset $D --replies $G
python measurements/council_eval quoting --dataset $D --replies $Q $G
python measurements/council_eval turns --excerpt $R/ollama-journal.run1.tsv
```

## What it shows, and what it cannot

- **Alone, Gemma agrees with R1 far more than the pilot pair did.** It
  settles 129 of 144 metrics, and reaches 12 vectors, two of them inside the
  range their sources published. Agreed of scored, with the baseline's rate on
  the same items:
  - AV 9/12 (baseline 1.00), AC 14/15 (0.93), PR 13/13 (1.00), UI 14/14 (1.00);
  - S 6/15 (1.00), C 11/16 (0.94), I 13/15 (0.53), A 8/13 (0.54).
  - Lift is +0.33 on I and +0.08 on A, 0 on AC, PR and UI, and negative on AV,
    S and C.
- **Its PR and UI are one value throughout:** N on 18 of 18. N is R1's value
  wherever R1 has one, and it is also the option the product's prompt lists
  first on both. So these two metrics cannot tell reading from first-listed
  anchoring, and a constant matching a constant reference scores the baseline,
  not more. AC is L on 16 of 18, again the option listed first.
- **S is its weak metric:** C on 9 of 18, where R1 is U on every finding.
- **It quotes cleanly:** one unverified quotation in 144 replies, and none of
  the prompt's own definitions.
- **Beside Qwen, the pair settles little:** 65 settled, 69 contested and 10
  unresolved, and no vector. The two read most metrics differently, and the
  chairman settles nothing they dispute.
- **Limits:** one pass, one seed, no rerun of this model, and 18 npm findings.
  The reversed-order control was not run on Gemma, so the first-listed pattern
  above is not separated from reading.
- **Since measured:** `../order-checked-vulnscout/` asked Gemma the same findings
  with the options reversed. It names N on PR and UI in all 18 in both orders,
  and L on AC in 16, so those values are not the list's order.

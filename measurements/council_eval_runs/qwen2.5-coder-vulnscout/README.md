# qwen2.5-coder:7b-instruct on the pilot's 18 vulnscout findings, alone and beside Qwen

One pass of `qwen2.5-coder:7b-instruct` over the pilot's dataset, in the
product's words (the baseline prompt), scored alone and as a pair with the
pilot's Qwen pass. Every figure below is re-derived from the files here and the
pilot's, and none needs a model.

## What was run

- **Dataset:** the pilot's, `../pilot-vulnscout/vulnscout.dataset.json`, named
  in the header by its SHA-256, `2575a983…0d66`.
- **Pass:** `python measurements/council_eval collect --model
  qwen2.5-coder:7b-instruct`, from 2026-09-25 16:01:20 to 16:04:06 +08:00. The
  model is unloaded before each item, so every turn starts cold.
- **Pinning:** prompt `member-base-metric-3`, temperature 0, seed 11, `think`
  false, `num_ctx` 8192, on Ollama 0.34.3. Digest `dae161e2…`.
- **Settings:** read from the operator's `.env`; the header records
  `timeout_seconds` 12000. No call came near it.
- **Code:** commit `76a4b2c`, plus the 21 uncommitted paths the header lists.
  The three not in the Gemma pass's list are two HTML report files and the
  Gemma folder, none of them on a call's path.
- **The pair's Qwen:** the pilot's `qwen2.5-7b-instruct.run1.replies.jsonl`.

## The journal

`ollama-journal.run1.tsv` covers 16:01:20 to 16:04:07. `turns.txt` counts it:
162 generate requests (144 calls and 18 unloads), 18 loads of Qwen2.5 Coder,
and 18 turns of 8 calls. The other two requests are the header's. Clean.

## Files

| File | Size | What it is |
|---|---|---|
| `qwen2.5-coder-7b-instruct.run1.replies.jsonl` | 99 KB | the pass: a header, 144 calls, an end line |
| `ollama-journal.run1.tsv` | 14 KB | the server's requests and loads for the window |
| `turns.txt` | 1 KB | the excerpt, counted |
| `qwen2.5-coder.score.txt` | 12 KB | Qwen alone, the coder alone, and the pair, against R1 and the baseline |
| `values.txt` | 1 KB | every value the coder named, beside the option listed last |
| `quoting.txt` | 1 KB | the pair's lone settlements and unverified quotations |

## Re-deriving every figure

```bash
R=measurements/council_eval_runs/qwen2.5-coder-vulnscout; P=measurements/council_eval_runs/pilot-vulnscout
D=$P/vulnscout.dataset.json; C=$R/qwen2.5-coder-7b-instruct.run1.replies.jsonl; Q=$P/qwen2.5-7b-instruct.run1.replies.jsonl
python measurements/council_eval score --dataset $D --replies $Q $C
python measurements/council_eval values --dataset $D --replies $C
python measurements/council_eval quoting --dataset $D --replies $Q $C
python measurements/council_eval turns --excerpt $R/ollama-journal.run1.tsv
```

## What it shows, and what it cannot

- **The coder declines almost everything.** Of 144 replies, 106 are
  `NO_EVIDENCE`: all 18 on PR and on UI, 17 on S, 16 on AV.
- **Alone it settles 21 metrics of 144** and reaches no vector. On what it
  settles, the samples are too small to read: AC 0/4, S 0/1, C 1/4, I 3/5,
  A 1/3, and nothing scored on AV, PR or UI.
- **Beside Qwen it changes almost nothing.** The pair settles 103, contests 5
  and leaves 36 unresolved, nearly Qwen alone (105 settled), and reaches four
  vectors, none inside the published range. Agreed of scored: AV 0/11, AC 2/14,
  PR 0/10, UI 1/13, S 4/15, C 1/10, I 6/12, A 1/9.
- **Whether its declines are right** -- the text saying too little -- or
  refusals of what the text does say, R1 cannot tell: it has no label for "the
  advisory is silent".
- **Limits:** one pass, one seed, no rerun of this model, and 18 npm findings.

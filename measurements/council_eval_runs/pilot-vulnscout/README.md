# Pilot: the current council on the 18 vulnscout findings

`qwen2.5:7b-instruct` and `llama3.2:latest`, each put through the harness in
`measurements/council_eval/`, three times over. The figures are those of the
pair and of each model alone, against R1, the most-common-value baseline, and
the recorded `measurements/council_runs/gpu-full`. Every figure below is
re-derived from the files here; none needs a model or a scan.

## What was run

- **Dataset:** `vulnscout.dataset.json`, the 18 findings of `fetched/vulnscout`,
  frozen by `python measurements/council_eval dataset` on 2026-09-24 at 18:38.
  It holds the audit's own join and order, with Syft 1.52.0, Trivy 0.74.0 and
  the database built 2026-09-23T20:20:57Z.
  - **This is not the database `gpu-full` read**, which was built
    2026-09-22T02:00:05Z and has since been replaced. The same 18 findings come
    back in the same order, every published score matches `gpu-full`'s, and all
    42 of `gpu-full`'s quotations still verify or fail as recorded. That last
    count came from a one-off scratch script, not kept. It is consistent with
    unchanged texts, but does not prove them. The gate below is the check that
    counts.
- **Passes:** `python measurements/council_eval collect`, one model at a time.
  The model is unloaded (`keep_alive: 0`) before each item, so every member's
  turn starts from a fresh load, as in `gpu-full`.
- **Pinning:** prompt `member-base-metric-3`, temperature 0, seed 11,
  `num_ctx` 8192, `think` false. Each file's first line records this, with the
  model digest and Ollama 0.34.3.
- **Code:** commit `a4e5365`, plus the uncommitted paths each header lists (21 to
  29). On the path a call takes:
  - `src/council/ollama.py`: the pinned `think: false`, uncommitted then. This
    is the only change that shapes a request.
  - `src/council/redaction.py`: a docstring.
  - `src/cli/council_run.py` and `src/cli/council_detail.py`: a
    `rests_on_one_member` field added to the record (since renamed
    `nothing_cross_checked`).
  - The harness itself, untracked.
  - Every call's request fingerprint is identical in all three runs. The replay
    rebuilds the requests and refuses any that differ, and it rebuilt them all.

| Run | Qwen | Llama | Journal excerpt |
|---|---|---|---|
| 1 | 2026-09-24 18:50:28–18:53:49 | 18:54:04–18:57:15 | `ollama-journal.run1.tsv` |
| 2 | 19:02:01–19:05:27 | 18:59:43–19:02:01 | `ollama-journal.run2.tsv` |
| 3 | 2026-09-25 09:06:49–09:10:11 | 09:10:11–09:12:31 | `ollama-journal.run3.tsv` |

## Two interference windows, and what was scored

Ollama's journal is the only witness to other clients. Each excerpt is the
journal for one run window, with host and process dropped.
`python measurements/council_eval turns` counts its turns: one unload, then the
eight metrics.

- **Run 1, Llama, `CVE-2026-13676`**, turn at 18:54:36: 12 calls where 8 were
  asked. Qwen was loaded four more times than this run asked. It was another
  agent's live tests (`COUNCIL_LIVE_OLLAMA=1`), and it evicted Llama before its
  AC, PR, UI and S there.
- **Run 2, Qwen, `CVE-2026-6321`**, turn at 19:03:22: 12 calls where 8 were
  asked. Four requests from the same live tests went to the Qwen already loaded,
  with no reload.
- **Run 3:** clean. 324 generate requests, which is 288 calls and 36 unloads,
  18 loads of each model, and every turn eight calls.
- The `HEAD /` and `GET /api/ps` lines are `ollama ps` calls, some of them
  another agent's, and they load nothing.

**Scored:** Qwen run 1 and Llama run 2, the clean run of each available at the
time, give `pilot.score.txt`. The run-3 pair gives `pilot.run3.score.txt`. The
two are identical but for each pass's start time and its count of uncommitted
paths. `compare.txt` shows all 144 replies of each model byte-identical across
all three runs, the interfered calls included.

## Files

| File | Size | What it is |
|---|---|---|
| `vulnscout.dataset.json` | 29 KB | the frozen dataset |
| `qwen2.5-7b-instruct.run{1,2,3}.replies.jsonl` | 113 KB each | Qwen's three passes: a header, 144 calls, an end line |
| `llama3.2-latest.run{1,2,3}.replies.jsonl` | 104 KB each | Llama's three passes |
| `ollama-journal.run{1,2,3}.tsv` | 28–29 KB each | the server's requests and loads for each run window |
| `gate.txt` | 1 KB | the replay against `gpu-full.report.txt`, for the scored pair and the run-3 pair |
| `pilot.score.txt`, `pilot.run3.score.txt` | 12 KB each | every roster against R1 and the baseline |
| `compare.txt` | 2 KB | each model's three runs, pairwise, byte for byte |
| `quoting.txt` | 1 KB | whose quotation each lone settlement rests on, and unverified quotations of the prompt |
| `turns.txt` | 1 KB | the three journal excerpts, counted |
| `values.txt` | 1 KB | every value each model of the scored pair named, beside the option listed last; added on 2026-09-25 as the baseline cell of `../README.md` |

804 KB in all.

## Re-deriving every figure

From the project root, with the venv active. None of these asks a model:

```bash
D=measurements/council_eval_runs/pilot-vulnscout
Q=$D/qwen2.5-7b-instruct; L=$D/llama3.2-latest
python measurements/council_eval gate --dataset $D/vulnscout.dataset.json \
    --replies $Q.run1.replies.jsonl $L.run2.replies.jsonl \
    --recorded measurements/council_runs/gpu-full.report.txt
python measurements/council_eval score --dataset $D/vulnscout.dataset.json \
    --replies $Q.run1.replies.jsonl $L.run2.replies.jsonl
python measurements/council_eval compare --first $Q.run1.replies.jsonl --second $Q.run3.replies.jsonl
python measurements/council_eval quoting --dataset $D/vulnscout.dataset.json \
    --replies $Q.run1.replies.jsonl $L.run2.replies.jsonl
python measurements/council_eval turns --excerpt $D/ollama-journal.run1.tsv
python measurements/council_eval values --dataset $D/vulnscout.dataset.json \
    --replies $Q.run1.replies.jsonl $L.run2.replies.jsonl
```

Each prints what its `.txt` here holds. `score` on the scored pair reproduces
`pilot.score.txt` byte for byte. An excerpt was cut with `server-log --journal`
from `journalctl -u ollama -o short-iso` for the window in the table.

## What it shows, and what it cannot

- **The gate passes.** The pair rebuilt offline prints what `gpu-full` printed:
  105 settled, 13 contested, 26 unresolved, the same four vectors, and every
  unsettled line.
- **Against R1, every metric's lift is negative, for the pair and for each
  model alone.**
  - The pair agrees on 0 of 11 for AV, 0 of 9 for PR, 0 of 13 for UI, and 1 of
    13 for S.
  - On those four metrics R1 gives one value wherever it has one: `N`, `N`, `N`
    and `U`, on 16, 15, 16 and 16 of the 18 findings. So the baseline scores
    1.00 and lift can at best reach 0.
- **Llama:**
  - It never declines.
  - It gives one value throughout on AC (`H`), UI (`R`) and S (`C`), each the
    last the prompt lists.
  - 14 of its 30 unverified quotations are the prompt's own definitions.
- **Settled on one quotation alone:** 36 of the pair's 105 settled values, 27
  on Qwen's and 9 on Llama's.
- **Limits of the pilot.** It covers 18 findings, from one npm repository. With
  R1 giving a single value on four metrics, it cannot show whether the council
  can ever beat the baseline. It cannot tell a wrong reading from a different
  scoring convention for libraries, which only hand labels from the text can.
  It cannot tell reading from list-order anchoring, which only a reversed-order
  control can.

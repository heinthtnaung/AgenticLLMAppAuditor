# Order-checked: a member's value counts only if both orders give it

Qwen and Llama lean to the option the prompt lists last, and Gemma to the one it
lists first (`../README.md`, `../gemma4-vulnscout/`). This measures a rule that
takes position out of a member's answer: every metric is asked in the product's
order and reversed, and a member's value counts only when the two agree. It is a
harness variant, measured on saved and new passes; the product is not changed.

<!-- preregistered: begin -->

## Written before any merged roster was computed or any reversed pass taken

This section was fixed on 2026-09-25, and its SHA-256 was sent to the team lead
before either. `tests/measurements/council_eval_runs/test_order_checked_readme.py`
holds it to that digest.

**What is already known, and what is not.** Qwen's and Llama's replies in both
orders are saved, and their per-order counts are published: `values.txt` in
`../pilot-vulnscout/` and `../reversed-vulnscout/`. Those counts constrain
their stability on the two-option metrics -- Llama's UI, R 18 of 18 in one
order and N 18 of 18 in the other, cannot be stable on any finding. What has
not been computed is any finding's stability, any merged roster, or its
agreement with R1. Gemma's and the Qwen coder's reversed passes do not exist.

### The rule

For each finding, metric and member, F is the reply in the product's order and
R the reply with the options reversed.

- **Stable:** F and R name the same value. The member answers with F -- its
  quotation, its confidence, and whether it is a quoted answer or a guess.
- **Order-sensitive:** F and R name different values. The member is recorded
  as declining.
- **Declined:** F or R declines. The member is recorded as declining.
- **Failed:** F or R fails, or cannot be read. The member is recorded as
  failed, with the reason.

The chairman then works on those answers exactly as it does today.

### The inputs

| Model | Product's order | Reversed |
|---|---|---|
| `qwen2.5:7b-instruct` | `../pilot-vulnscout/qwen2.5-7b-instruct.run1.replies.jsonl` | `../reversed-vulnscout/qwen2.5-7b-instruct.run1.replies.jsonl` |
| `llama3.2:latest` | `../pilot-vulnscout/llama3.2-latest.run2.replies.jsonl` | `../reversed-vulnscout/llama3.2-latest.run1.replies.jsonl` |
| `gemma4:latest` | `../gemma4-vulnscout/gemma4-latest.run1.replies.jsonl` | `gemma4-latest.reversed.run1.replies.jsonl`, to be taken |
| `qwen2.5-coder:7b-instruct` | `../qwen2.5-coder-vulnscout/qwen2.5-coder-7b-instruct.run1.replies.jsonl` | `qwen2.5-coder-7b-instruct.reversed.run1.replies.jsonl`, to be taken |

The two new passes are `collect --variant reversed`, every turn from a fresh
load, on the pilot's dataset. A pass is kept only if its journal window holds
18 turns of 8 calls, 18 loads and no generate request it did not make;
otherwise it is taken again, and the unclean pass kept and named as such.

**Rosters scored:** each model alone, Qwen with Llama (the pilot's pair), Qwen
with Gemma, and Qwen with the coder -- each order-checked, beside the same
roster unchecked in the product's order.

### How it is read

**1. Stability.** Per model and metric, of 18 findings: stable,
order-sensitive, declined, failed. A metric is **mostly order** for a model when
more than 6 of 18 are order-sensitive. Six is the most any metric's values moved
under the library paragraph alone, the measured size of a change of wording that
is not about order.

**2. Coverage against accuracy.** Per roster, order-checked beside unchecked:
metrics settled; agreed of scored against R1; the commonest-value baseline on
the same items; lift; the 95% Wilson interval.

- Expected: fewer settled, and a larger share of those settled agreeing with R1.
- A change in a metric's rate is **distinguishable** only if the two intervals
  do not overlap. Otherwise it is recorded as not distinguishable, whichever
  way it points.

**3. What is left of the bias.**

- **(a)** Among each model's surviving values, the share that are the option
  the product's order lists last -- first, for Gemma -- beside the same share
  among its product-order replies. On a two-option metric the rule removes a
  purely positional answer by construction, so this measures how much of each
  model's answers were positional, not whether the rule works.
- **(b)** The check two orders cannot make: on PR, C, I and A, L is the middle
  option, and stays in the middle when the order is reversed, so a lean to the
  middle survives the rule. If a model's surviving values on one of those
  metrics are L on more than 6 of 18, where R1 gives L on at most one finding,
  a middle-position bias is suspected, and this rule does not remove it.

**4. No verdict on adopting it.** Adopting the rule would mean the product
asking every metric in both orders, twice the calls. The numbers go to the
user, who decides.

### What this cannot show

- **A lean to the middle** on PR, C, I and A (3b only flags it). On AV, A and
  L trade the second and third places when reversed, so a lean there is caught
  only in part.
- **That a stable answer is correct.** Two orders agreeing shows only that the
  answer is not positional.
- **The usual limits:** 18 npm findings, one seed, one pass per order, and R1
  with one value on AV, PR, UI and S, so lift can at best reach 0 there.

<!-- preregistered: end -->

## Results

Added after the runs, on 2026-09-25. Nothing below changes the section above.

### The runs

| Pass | Window | Journal |
|---|---|---|
| `gemma4:latest`, reversed | 16:18:14 to 16:22:15 | 162 generate requests (144 calls, 18 unloads), 18 loads, 18 turns of 8, and the header's two reads: clean |
| `qwen2.5-coder:7b-instruct`, reversed | 16:22:33 to 16:25:18 | the same counts: clean |

Both are `member-base-metric-3+reversed-1`, temperature 0, seed 11, `think`
false, window 8192, on Ollama 0.34.3. Their headers record the timeout, 12000 s,
from the operator's `.env`; no call came near it. Qwen's and Llama's inputs
are the saved passes in the table above, and no model was asked for them.

### 1. Stability

Of 18 findings per model and metric: stable / order-sensitive / declined.
**Bold** marks a metric that is mostly order, with more than 6 of 18
order-sensitive. Nothing failed.

| Metric | Qwen | Llama | Gemma | Qwen coder |
|---|---|---|---|---|
| AV | 2 / 3 / 13 | **4 / 13 / 1** | 11 / 3 / 4 | 2 / 0 / 16 |
| AC | 17 / 0 / 1 | **6 / 12 / 0** | 16 / 0 / 2 | 1 / 4 / 13 |
| PR | **4 / 7 / 7** | 14 / 4 / 0 | 18 / 0 / 0 | 0 / 0 / 18 |
| UI | **4 / 10 / 4** | **0 / 18 / 0** | 18 / 0 / 0 | 0 / 0 / 18 |
| S | 12 / 4 / 2 | 17 / 1 / 0 | 12 / 4 / 2 | 0 / 0 / 18 |
| C | 11 / 4 / 3 | 17 / 1 / 0 | 13 / 4 / 1 | 7 / 1 / 10 |
| I | 13 / 3 / 2 | 13 / 4 / 1 | 16 / 2 / 0 | 9 / 0 / 9 |
| A | 14 / 2 / 2 | 14 / 4 / 0 | 13 / 1 / 4 | 6 / 0 / 12 |

- **Mostly order:** Llama's AV, AC and UI, and Qwen's PR and UI.
- **Nothing is mostly order for Gemma.** Its N on PR and UI holds 18 of 18
  in both orders, and its L on AC 16 of 18, so its agreement with R1 there is
  not the first-listed option.
- **The coder** is order-sensitive on at most 4 of 18, because it declines
  most of what it is asked.

### 2. Coverage against accuracy

Settled, and agreed of scored against R1, unchecked in the product's order
beside order-checked. The baseline and the intervals are in the `*.txt` files.

| Roster | Settled | AV | AC | PR | UI | S | C | I | A |
|---|---|---|---|---|---|---|---|---|---|
| Qwen | 105 → 68 | 0/11 → 0/1 | 2/13 → 2/13 | 0/10 → 0/3 | 1/13 → 1/3 | 4/15 → 2/11 | 1/11 → 1/10 | 6/13 → 5/10 | 1/11 → 1/10 |
| Llama | 71 → 49 | 1/4 → 0/2 | 1/12 → 1/4 | 0/5 → 0/3 | 0/7 → 0/0 | 0/12 → 0/12 | 1/11 → 1/10 | 2/11 → 2/10 | 2/7 → 2/7 |
| Qwen + Llama | 105 → 83 | 0/11 → 0/3 | 2/14 → 2/14 | 0/9 → 0/5 | 0/13 → 1/3 | 1/13 → 0/13 | 1/13 → 1/12 | 5/12 → 5/14 | 2/12 → 2/11 |
| Gemma | 129 → 112 | 9/12 → 9/9 | 14/15 → 14/15 | 13/13 → 13/13 | 14/14 → 14/14 | 6/15 → 6/11 | 11/16 → 9/12 | 13/15 → 12/13 | 8/13 → 5/10 |
| Qwen + Gemma | 65 → 86 | 3/8 → 8/8 | 4/5 → 4/5 | 3/3 → 10/10 | 3/4 → 12/12 | 4/13 → 4/12 | 6/8 → 5/9 | 6/6 → 8/9 | 1/6 → 1/8 |
| Qwen coder | 21 → 14 | 0/0 → 0/0 | 0/4 → 0/0 | 0/0 → 0/0 | 0/0 → 0/0 | 0/1 → 0/0 | 1/4 → 1/4 | 3/5 → 2/4 | 1/3 → 1/2 |
| Qwen + coder | 103 → 68 | 0/11 → 0/1 | 2/14 → 2/13 | 0/10 → 0/3 | 1/13 → 1/3 | 4/15 → 2/11 | 1/10 → 1/9 | 6/12 → 5/10 | 1/9 → 1/9 |

- **Coverage fell as expected** for every roster but Qwen + Gemma. Qwen fell
  from 105 settled to 68, and Llama from 71 to 49.
- **No change in any rate is distinguishable.** On every metric of every
  roster the two 95% intervals overlap.
- **Qwen + Gemma settles more, 86 against 65, with 37 contests against 69.**
  Qwen's positional answers become declines, so Gemma's stable ones settle:
  AV 8/8, PR 10/10 and UI 12/12.
- **For Qwen and Llama, what survives is still mostly off R1.** Qwen's AC is H
  on 16 of 18 in both orders, and both models' S is C on 10 and 17. Those
  departures are not the list's order.
- **Vectors:** Gemma alone reaches 2 order-checked (12 unchecked), and no other
  roster reaches any.

### 3. What is left of the bias

**(a) Positional share.** Among a model's values, the share that are the
option the product's order lists last (first, for Gemma), before and after
the check.

| Model | Before | After |
|---|---|---|
| Qwen, last | 52/123 = 0.42 | 30/77 = 0.39 |
| Llama, last | 61/144 = 0.42 | 27/85 = 0.32 |
| Gemma, first | 90/134 = 0.67 | 87/117 = 0.74 |
| Qwen coder, last | 11/38 = 0.29 | 1/25 = 0.04 |

Qwen's share barely falls, because most of its last-listed answers -- AC H,
and S C -- hold in both orders; only UI (12 to 2), C (6 to 0) and PR (3 to 2)
were positional. Gemma's share rises: its first-listed answers are its stable
ones.

**(b) The middle option,** L among the surviving values on PR, C, I and A,
where R1 gives L on at most one finding:

| Model | PR | C | I | A |
|---|---|---|---|---|
| Qwen | 2 | 6 | 4 | **10** |
| Llama | 1 | 5 | **7** | **11** |
| Gemma | 0 | 0 | 0 | 2 |
| Qwen coder | 0 | 0 | 0 | 0 |

A middle-position bias is **suspected** for Qwen on A, and for Llama on I and
A: more than 6 of 18. Two orders cannot tell it from a reading of "Low", and
this rule does not remove it.

### 4. For the user

Whether the product should ask every metric in both orders is not decided
here. The rule turns Llama's and Qwen's positional answers into declines --
fewer settled values, not more right ones at this n -- and leaves Gemma almost
untouched. It costs twice the calls.

### What this does not show

Everything in the fixed section's list, and one more: a single reversed pass per
model, with no rerun of either order.

## Files

| File | Size | What it is |
|---|---|---|
| `gemma4-latest.reversed.run1.replies.jsonl` | 111 KB | Gemma's reversed pass |
| `qwen2.5-coder-7b-instruct.reversed.run1.replies.jsonl` | 99 KB | the coder's reversed pass |
| `ollama-journal.*.reversed.run1.tsv` | 14 KB each | each reversed pass's journal window |
| `turns.*.reversed.run1.txt` | 1 KB each | each window, counted |
| `qwen-llama.order-checked.txt` | 14 KB | Qwen, Llama and their pair, order-checked |
| `qwen-gemma4.order-checked.txt` | 14 KB | Qwen, Gemma and their pair, order-checked |
| `qwen-coder.order-checked.txt` | 15 KB | Qwen, the coder and their pair, order-checked |

## Re-deriving every figure

From the project root, with the venv active. None of these asks a model:

```bash
R=measurements/council_eval_runs; D=$R/pilot-vulnscout/vulnscout.dataset.json
Q=qwen2.5-7b-instruct.run1.replies.jsonl
python measurements/council_eval order-checked --dataset $D \
    --forward $R/pilot-vulnscout/$Q $R/pilot-vulnscout/llama3.2-latest.run2.replies.jsonl \
    --reversed $R/reversed-vulnscout/$Q $R/reversed-vulnscout/llama3.2-latest.run1.replies.jsonl
python measurements/council_eval order-checked --dataset $D \
    --forward $R/pilot-vulnscout/$Q $R/gemma4-vulnscout/gemma4-latest.run1.replies.jsonl \
    --reversed $R/reversed-vulnscout/$Q $R/order-checked-vulnscout/gemma4-latest.reversed.run1.replies.jsonl
python measurements/council_eval order-checked --dataset $D \
    --forward $R/pilot-vulnscout/$Q $R/qwen2.5-coder-vulnscout/qwen2.5-coder-7b-instruct.run1.replies.jsonl \
    --reversed $R/reversed-vulnscout/$Q \
    $R/order-checked-vulnscout/qwen2.5-coder-7b-instruct.reversed.run1.replies.jsonl
```

Each prints what its `.txt` here holds. The unchecked rosters are the `score`
files of `../pilot-vulnscout/`, `../gemma4-vulnscout/` and
`../qwen2.5-coder-vulnscout/`.

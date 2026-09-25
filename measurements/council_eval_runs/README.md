# The 2 × 2: library guidance and reversed options, on the pilot's findings

The pilot (`pilot-vulnscout/`) left two questions open. Are the pair's
departures from R1 misreadings, or a scoring convention for libraries that the
prompt never states? And are Llama's constant AC, UI and S, each the option the
prompt lists last, readings or list-order anchoring? This crosses the two
controls.

| | options in the product's order | options reversed |
|---|---|---|
| **the product's prompt** | baseline: `pilot-vulnscout/` | `reversed-vulnscout/` |
| **plus the library paragraph** | `library-vulnscout/` | `library-reversed-vulnscout/` |

<!-- preregistered: begin -->

## Written before any variant pass

This section was fixed on 2026-09-25 before the first variant pass started, and
its SHA-256 was sent to the team lead then.
`tests/measurements/council_eval_runs/test_readme_preregistered.py` holds it to
that digest, so any later edit to it fails the suite.

### What is held fixed

- **The pilot's dataset**, `pilot-vulnscout/vulnscout.dataset.json`, SHA-256
  `2575a98327867c3bbc98860cb6d57bdb972a10f26eeaf7ba0b2e74e91bbe0d66`: its 18
  findings in its order. It is not copied, because every pass header names it by
  that digest.
- **The models:** `qwen2.5:7b-instruct` (`845dbda0…`) and `llama3.2:latest`
  (`a80c4f17…`) on Ollama 0.34.3, on the RTX 3070.
- **The pinning:** temperature 0, seed 11, `num_ctx` 8192, `think` false, and
  every turn from a fresh load.
- **The protocol:** one pass per model per cell, Qwen then Llama, back to back,
  as in the pilot's run 3.
- **A cell is kept only if its window's journal is clean:** 36 turns of 8
  calls, 18 loads of each model, and no generate request the passes did not
  make. Otherwise it is run again, and the unclean passes are kept beside the
  clean ones and named as unclean.
- **The product's prompt, `member-base-metric-3`, and `PROMPT_VERSION` are
  untouched.** A variant belongs to the harness, `council_eval/variants.py`:
  the client that sends the product's prompt rewords it first. Each variant
  asks under its own version, which its passes' headers record.

| Cell | Prompt version |
|---|---|
| baseline | `member-base-metric-3` |
| library | `member-base-metric-3+library-1` |
| reversed | `member-base-metric-3+reversed-1` |
| library + reversed | `member-base-metric-3+library-1+reversed-1` |

### The two changes, exactly

**Library.** The system turn gains a lead line and one paragraph, placed after
the metric's value definitions and before "That definition is reference
material":

> The CVSS v3.1 User Guide, on scoring vulnerabilities in software libraries:
>
> When scoring the impact of a vulnerability in a library, independent of any
> adopting program or implementation, the analyst will often be unable to take
> into account the ways in which the library might be used. While specific
> products using the library should generate CVSS scores specific to how they
> use the library, scoring the library itself requires assumptions to be made.
> The analyst should score for the reasonable worst-case implementation
> scenario.

The paragraph is from §3.7 of the CVSS v3.1 **User Guide**, "Scoring
Vulnerabilities in Software Libraries (and Similar)", read from first.org on
2026-09-25. The Specification Document has no section on libraries.

- **It is quoted word for word, but for its last sentence:** "When possible,
  the CVSS information should detail these assumptions." A reply has nowhere
  to put assumptions but its quotation, and the check would refuse them there.
- **The section's next paragraph is left out**, because it names a value: "an
  Attack Vector (AV) of Network (N)".
- `tests/measurements/council_eval/test_variants.py` holds that the added text
  names no metric and no value.

**Reversed.** Each metric's values are listed in the opposite order, in both
places the product lists them: the definition lines, and the reply schema's
"one of …". Nothing else moves. The confidence words and `NO_EVIDENCE` keep
their places.

| Metric | Product's order | Reversed | R1 on the 18 findings |
|---|---|---|---|
| AV | N, A, L, P | P, L, A, N | N on 16 |
| AC | L, H | H, L | L on 15, H on 1 |
| PR | N, L, H | H, L, N | N on 15 |
| UI | N, R | R, N | N on 16 |
| S | U, C | C, U | U on 16 |
| C | H, L, N | N, L, H | N on 15, H on 1 |
| I | H, L, N | N, L, H | H on 8, N on 6, L on 1 |
| A | H, L, N | N, L, H | N on 7, H on 5, L on 1 |

**The reversal lists R1's value last on AC, UI, S, AV and PR.** Anchoring on
the last option would raise agreement with R1 on those five with no reading at
all. So a gain under the reversal alone is not credited to the model.

### How a cell is read

**The unit** is each model's 18 replies on each metric, as `values` counts
them. Every value named counts, quoted or guessed, and a decline or a failure
counts by its kind. The pair's `score` table, against R1 and the
commonest-value baseline, is reported beside them. The readings below are
decided on the per-model counts, because the chairman's settlement mixes both
members and the quotation check.

**The threshold.** Replies here are deterministic: the pilot's 288 reproduced
byte for byte. What moves them is wording, and nothing measured says how far an
arbitrary change of wording moves them.

- **A shift** is a change of at least 6 of 18 replies, a third, in the
  direction stated. A smaller change is recorded as no clear change.
- **A model holds a value** when it names it on at least 12 of 18.

**The baseline cell**, from `values` on the pilot's scored passes:

| Metric | Listed last | Qwen | Llama |
|---|---|---|---|
| AV | P | L 11, declined 6, N 1 | L 15, N 3 |
| AC | H | H 16, L 1, declined 1 | H 18 |
| PR | H | L 8, declined 7, H 3 | N 10, H 7, L 1 |
| UI | R | R 12, declined 4, N 2 | R 18 |
| S | C | C 12, U 4, declined 2 | C 18 |
| C | N | L 7, N 6, H 5 | H 12, L 6 |
| I | N | H 12, L 4, N 1, declined 1 | L 12, H 6 |
| A | N | L 11, H 5, N 2 | L 14, H 4 |

### What each outcome would mean

**1. Anchoring.** Reversed is read against baseline, and library + reversed
against library. The test is on AC, UI and S, where the pilot held the option
listed last: Llama on 18 of 18 on all three, Qwen on 16, 12 and 12.

- **Order-driven:** the model names the option now listed last (L, N, U) on 12
  or more of 18. Its pilot value there was the list's order, not a reading, and
  the agreement with R1 this brings is not credited to it.
- **Order-independent:** it still names its pilot value (H, R, C) on 12 or
  more. The value is not the list position, so its departure from R1 there is a
  reading or a convention.
- **Mixed:** anything else. The order decides part of it; no conclusion.
- **The other five metrics** get the same test against the option each order
  lists last, though the pilot held the last-listed option on none of them.

**2. A convention the prompt lacked.** Library is read against baseline, and
library + reversed against reversed. For a library, the "reasonable worst-case
implementation scenario" is reached over a network, with no privileges and no
user: N on AV, PR and UI, which is R1's value on every finding it scores. For
AC it is L, R1's value on 15 of 16.

- **A convention:** in the product's order, a model's replies naming N rise by
  6 or more of 18 on AV, PR or UI, or those naming L on AC. N is listed first
  there, and the pilot's pull is to the last option, so the guidance works
  against the order. The pilot's departure on that metric was then, at least in
  part, a convention the prompt does not state, not a misreading.
- **S is the check on understanding.** Read as "take the most severe value",
  worst case gives C, away from R1's U, and the paragraph says nothing of
  scope. A shift of 6 or more toward C is the model applying the paragraph as a
  severity rule, and it is not credited.
- **No shift** on AV, PR, UI or AC: this paragraph, worded this way, did not
  change the readings. That does not show the models misread. It shows only
  that this paragraph is not the missing piece.
- **A quotation of the paragraph offered as evidence**, as `quoting` counts
  them, is a cost of the variant, and is reported.

**3. Separating the two.** Each effect is measured twice: the reversal with and
without the paragraph, and the paragraph in each order.

- **Separable:** both measurements of an effect agree in direction, and in
  size to within 3 of 18.
- **N moves only in library + reversed:** there the paragraph and the last
  position both point to N on AV, PR and UI. The "convention" is then anchoring
  given a push, and it is not credited. Only the library cell in the product's
  order can credit it.
- **The reversal flips a value without the paragraph but not with it:** the
  paragraph overrides the order, which is evidence the model reads it.

**4. Neither.** AC, UI and S come out order-independent, and the paragraph
shifts nothing. Then the pilot's departures from R1 are neither the list's
order nor this convention. Three candidates are left: a misreading, a
convention this paragraph does not carry, or R1 itself following a practice the
advisory text does not show. Only labels made by hand from the text can tell
them apart.

### What this design cannot show

- **18 findings, from one npm repository**, every one of them a library.
- **One seed and one pass per cell.**
- **No measure of how far an arbitrary rewording moves these replies.** So a
  shift is judged by its direction as much as by its size.
- **Lift cannot be positive on four metrics.** On AV, PR, UI and S, R1 gives
  one value, so the baseline scores 1.00 there and lift can at best reach 0 in
  any cell.

<!-- preregistered: end -->

## Results

Added after the runs, on 2026-09-25. Each cell's README is its record.

- **No cell was run twice.** All three variant windows were clean, and the
  third held only another client's `ollama list`, which loads nothing.
- **The counts below come from the four `values.txt` files**:
  `pilot-vulnscout/` for the baseline, and one in each variant's folder.

### 1. Anchoring

Of 18 replies, those naming the option each order lists last. That is H, R and
C in the product's order, and L, N and U reversed.

| Model | Metric | baseline | reversed | library | library + reversed | Reading |
|---|---|---|---|---|---|---|
| Llama | AC | H 18 | L 12, H 6 | H 18 | L 14, H 4 | order-driven in both pairs |
| Llama | UI | R 18 | N 18 | R 13, N 5 | N 18 | order-driven in both pairs |
| Llama | S | C 18 | C 17, U 1 | C 18 | C 12, U 6 | order-independent in both pairs |
| Qwen | AC | H 16, L 1 | H 16, L 1 | H 17, L 1 | H 16, L 1 | order-independent in both pairs |
| Qwen | UI | R 12, N 2 | N 16, R 2 | R 14, N 1 | N 10, R 8 | order-driven without the paragraph, mixed with it |
| Qwen | S | C 12, U 4 | C 12, U 4 | C 16, U 1 | C 13, U 5 | order-independent in both pairs |

- **UI follows the order for Llama in both pairs, and for Qwen without the
  paragraph.** With the paragraph, Qwen's UI is mixed.
- **AC follows the order for Llama in both pairs.**
- The pilot's UI:R, from both models, and Llama's AC:H were the list's order,
  not readings. All 18 of Llama's reversed UI answers are guesses with no
  quotation, in both reversed cells.
- **S does not follow the order for either model, and Qwen's AC does not.**
  Those values are readings or a convention, not the list position.
- **Two readings on these three metrics sit exactly on the threshold of 12:**
  Llama's AC reversed, and Llama's S in library + reversed.

**The rule misfires twice on the other five metrics.**

- **As written, it labels three readings there "order-driven":** Llama's C in
  both pairs, and Qwen's PR and I in the library pair, both of Qwen's at
  exactly 12. Llama's C and Qwen's I meet the order-independent condition as
  well, since the value each held, H, is the option the reversal lists last:
  the rule gives neither label precedence, so both apply, and neither means
  anything there. Every other reading on those five is mixed, but for Llama's A
  in the baseline pair, order-independent at exactly 12: L 14 in the pilot, L 12
  reversed.
- **Qwen's PR did move,** from L 8 in the library cell to N 12. N is the option
  the reversed order lists last, so that label is sound.
- **Llama's C and Qwen's I did not move.** Llama named H 12 times in the
  pilot, then 13 and 15. Qwen named H 15 times in the library cell, then 12. H
  is listed first in the product's order and last when reversed, and each
  model named it about as often either way.
- **Why the rule misfires:** on AC, UI and S the pilot's value was the one
  listed last, so naming the new last option means the value flipped. On the
  other five that does not follow, and the rule should have required the value
  to move. The labels on Llama's C and Qwen's I are not evidence of anchoring.

**The moves on those five that did happen:**

- Qwen's PR went from L 8 to N 11 reversed and N 12 in library + reversed. N is
  the option each of those orders lists last.
- Llama's AV went from L 15 to A 10 and A 8, the option listed third.
- Qwen's AV went to declining, 12 times, reversed, and to N, 9 times, in
  library + reversed.

### 2. A convention the prompt lacked

Of 18 replies, those naming the worst-case value, and the change the paragraph
made in each order:

| Model | Metric | Value | baseline → library | reversed → library + reversed |
|---|---|---|---|---|
| Qwen | AV | N | 1 → 0 (−1) | 5 → 9 (+4) |
| Qwen | PR | N | 0 → 0 (0) | 11 → 12 (+1) |
| Qwen | UI | N | 2 → 1 (−1) | 16 → 10 (−6) |
| Qwen | AC | L | 1 → 1 (0) | 1 → 1 (0) |
| Qwen | S | C | 12 → 16 (+4) | 12 → 13 (+1) |
| Llama | AV | N | 3 → 2 (−1) | 3 → 3 (0) |
| Llama | PR | N | 10 → 10 (0) | 11 → 11 (0) |
| Llama | UI | N | 0 → 5 (+5) | 18 → 18 (0) |
| Llama | AC | L | 0 → 0 (0) | 12 → 14 (+2) |
| Llama | S | C | 18 → 18 (0) | 17 → 12 (−5) |

- **No shift toward the convention,** for either model, in either order. The
  nearest are Llama's UI at +5 in the product's order and Qwen's AV at +4
  reversed.
- **The one change of 6 runs away from the convention:** Qwen's UI, reversed.
- **S has no shift toward C.** Qwen's +4 is toward severity, below the
  threshold.
- **Neither model quoted the paragraph as evidence.**
- **By reading 2, this is "no shift".** The paragraph, worded this way, did not
  change the readings. That does not show the models misread.

**What the paragraph did change was declining.**

- Qwen declined 12 times of 144 with it, against 21 without, in the product's
  order. Reversed, it declined 9 times against 24.
- Llama declined at most twice in any cell: twice reversed, and once in
  library + reversed. It guessed 51 times against 43, and 74 against 64.
- The paragraph says scoring a library "requires assumptions to be made". It is
  inferred, not tested, that this licenses answering where the text is silent,
  which the product's prompt calls the correct place to decline.

### 3. Separating the two

**The reversal's effect, with and without the paragraph:** the change, of 18,
in replies naming the option the reversed order lists last.

| Model | Metric | without the paragraph | with it | Within 3 |
|---|---|---|---|---|
| Llama | AC | L +12 | L +14 | yes |
| Llama | UI | N +18 | N +13 | no: 18 of 18 in both reversed cells, so the gap is the paragraph's +5 before reversal |
| Llama | S | U +1 | U +6 | no |
| Qwen | AC | L 0 | L 0 | yes: no effect either way |
| Qwen | UI | N +14 | N +9 | no |
| Qwen | S | U 0 | U +4 | no |

- **Separable:** only AC, for both models.
- **Everywhere else the two changes interact.** With the paragraph present, the
  reversal pulls Qwen's UI less and Llama's S more.
- **"N moves only in library + reversed"** is not met. The one candidate, Qwen's
  AV at +4, is below the threshold.
- **"The reversal flips a value without the paragraph but not with it"** is met
  as written, by Qwen's UI.
  - The rule reads that as evidence the model reads the paragraph.
  - It is weaker than that. The paragraph pulled Qwen's UI toward R, away from
    the no-interaction worst case it describes.
  - So it shows the paragraph's presence changes Qwen's UI, not that Qwen
    understands it.

### 4. Neither

Not met. Llama's UI and AC are order-driven in both pairs, and so is Qwen's UI
without the paragraph.

### Against R1, the pair

Agreed of scored: settled values where R1 has one. Below that, the baseline's
rate on the same items, and the lift.

| Metric | baseline | library | reversed | library + reversed | R1 |
|---|---|---|---|---|---|
| AV | 0/11 | 0/13 | 3/8 | 5/10 | N on 16 |
| AC | 2/14 | 2/15 | 2/8 | 1/8 | L on 15 |
| PR | 0/9 | 0/10 | 6/12 | 9/14 | N on 15 |
| UI | 0/13 | 0/15 | 13/15 | 8/16 | N on 16 |
| S | 1/13 | 0/15 | 0/12 | 2/14 | U on 16 |
| C | 1/13 | 1/10 | 1/11 | 1/11 | N on 15 |
| I | 5/12 | 6/10 | 4/14 | 5/13 | H 8, N 6, L 1 |
| A | 2/12 | 0/9 | 2/13 | 3/11 | N 7, H 5, L 1 |
| settled / contested / unresolved | 105 / 13 / 26 | 111 / 17 / 16 | 102 / 12 / 30 | 108 / 14 / 22 | |
| vectors, and inside the published range | 4, none | 1, none | 1, none | 3, none | |

| Lift | AV | AC | PR | UI | S | C | I | A |
|---|---|---|---|---|---|---|---|---|
| baseline | −1.00 | −0.79 | −1.00 | −1.00 | −0.92 | −0.85 | −0.17 | −0.42 |
| library | −1.00 | −0.80 | −1.00 | −1.00 | −1.00 | −0.80 | +0.10 | −0.78 |
| reversed | −0.62 | −0.62 | −0.50 | −0.13 | −1.00 | −0.82 | −0.21 | −0.38 |
| library + reversed | −0.50 | −0.88 | −0.36 | −0.50 | −0.86 | −0.82 | −0.15 | −0.18 |

- **The large rises are on AV, PR and UI, in the reversed cells:** from 0 in
  the pilot to between 3 and 13 agreed. Those are three of the five metrics on
  which the reversal lists R1's value last, the others being AC and S. By the
  rule fixed beforehand, that gain is not credited.
- **On the other five metrics, the agreed count moves by two items at most in
  any cell, either way.**
- **The one positive lift is library's on I:** 6 of 10 against 0.50, with an
  interval of [0.31, 0.83].

### What moved at all

Replies whose value differs from the pilot's, of 144:

| Model | library | reversed | library + reversed |
|---|---|---|---|
| Qwen | 35 | 56 | 52 |
| Llama | 23 | 59 | 72 |

**Without the reversal, the paragraph changed up to 6 of 18 values on a
metric,** with no direction toward the convention. The threshold of 6 is
therefore about the size of the paragraph's own undirected change. That is why
the readings above lean on direction, and why a directed change of 6 or 7 would
itself have been weak.

### What this does not show

- **One pass per cell.** The variants were not rerun, so their passes are taken
  to reproduce as the pilot's did, not shown to.
- **The reversal moves every metric's order at once.**
- **The rule fixed for the other five metrics misfires** on values that did not
  move, as set out under 1.
- **The design itself:** 18 npm findings, one seed, one wording of the
  convention, and R1 constant on four metrics.

# Thinking and load state

The evidence for two things in `src/council/ollama.py`: that every member is
asked with `think` pinned false, and that a pinned local member reproduces its
replies only between calls in the same load state.

## What was run

One prompt throughout: `build_prompt("AV", ADVISORY)`, prompt version
`member-base-metric-3`, where `ADVISORY` is `tests/council/council_samples.ADVISORY`.
The request is the product's own `build_request`, at temperature 0, seed 11 and
`num_ctx` 8192, with only the `think` field varied: left out, `false` or `true`.

**When and on what:** 2026-09-24, 10:16:41 to 10:20:02 UTC, on Ollama 0.34.3,
one server, on the RTX 3070 (CUDA). No other client was using the server.

| Model | Digest |
|---|---|
| `qwen2.5:7b-instruct` | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` |
| `llama3.2:latest` | `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72` |
| `gemma4:latest` | `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb` |

| File | Lines | What it holds |
|---|---|---|
| `probe_think.jsonl` | 6 | per model: `think` left out, then `think` false |
| `probe_state.jsonl` | 16 | per model: cold left out, warm left out, warm false, cold false, warm false again; Gemma then warm true |

Each line is the model, the step, and Ollama's whole envelope without
`context`, the token ids. **Cold** means the first call after the models were
unloaded; **warm** means straight after the call before it, on the model that
call left loaded. Every cold call's envelope shows a load of several seconds,
and no warm call's does.

## What the files show

`tests/measurements/thinking_and_load/test_probe_records.py` holds each of these
to the files.

- **Qwen and Llama:** with and without `think` false, byte-identical replies in
  the same load state, and the same prompt length: 532 tokens for Qwen, 544 for
  Llama.
- **Gemma:** with `think` left out, the prompt is 554 tokens, and the reply is
  byte-identical to the one given with `think` true. With `think` false, the
  prompt is 552 tokens and the reply differs: the quotation keeps the
  advisory's line breaks in one case and not the other.
- **No envelope has a `thinking` field**, including the one asked with `think`
  true. Every reply is 47 to 55 tokens.
- **Load state:**
  - Qwen answers `medium` confidence cold and `high` warm, with the same value
    and quotation. It gives the same reply in each state: cold twice, warm three
    times.
  - Llama answers identically in all five steps.
  - Gemma answers identically cold and warm under each `think` setting.

## What is inferred, not measured

- **Why Qwen differs cold and warm.** The candidate is the server reusing a
  cached prompt prefix. It is untested.
- **What the two extra Gemma tokens are.** Gemma has no text template: Ollama
  renders its prompt with a built-in `gemma4` renderer. That renderer is taken
  to add a thinking-mode marker unless `think` is false. It was not read.
- **Gemma in the CPU runs of `measurements/council_runs/`.** Those ran on Ollama
  0.34.2 and sent no `think` field. It is inferred that 0.34.2 rendered the
  thinking-mode prompt and returned no reasoning text, as 0.34.3 does. 0.34.2
  is no longer installed, and those runs kept no envelopes.

## Not in these files

- **`qwen2.5-coder:7b-instruct`:** one call with `think` false, 532 prompt
  tokens, answered normally. The reply was printed, not saved.
- **The live test's cold and warm pair.**
  `tests/council/test_ollama_live.py::test_the_same_question_twice_gets_the_same_answer`,
  run alone from a cold model before it unloaded between its calls, failed:
  `medium` then `high`.
- **The council pilot.** Run to run, with every member's turn started cold, its
  288 calls reproduced byte for byte. Those are the harness's own files, not
  these.

## How these were produced, and how to re-run

The files were written by scratch drafts of `probe.py` that made the same
requests in the same order. The drafts unloaded models with `ollama stop`.
`probe.py` unloads with `keep_alive: 0`, which the live test and the council
harness also use. The drafts' thinking probe did not unload Qwen or Llama first;
their first calls loaded them anyway, 3.9 s and 6.4 s, as the files show.
`probe.py` itself has not been run against a server.

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
python measurements/thinking_and_load/probe.py thinking \
    qwen2.5:7b-instruct llama3.2:latest gemma4:latest --out /tmp/think.jsonl
python measurements/thinking_and_load/probe.py load-state \
    qwen2.5:7b-instruct llama3.2:latest --out /tmp/state.jsonl
python measurements/thinking_and_load/probe.py load-state gemma4:latest \
    --with-true --out /tmp/state-gemma.jsonl
```

It refuses to write over an existing file, so a re-run never replaces these.
Run it with no other client using the server. A re-run on other hardware, or on
another Ollama, may rightly differ. The records test would then fail, and the
docs that cite these files would need changing with them.

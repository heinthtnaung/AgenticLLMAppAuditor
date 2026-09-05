# VEX documents

OpenVEX statements this project would *consume* — upstream authors' claims
about the components the corpus apps depend on. **Empty, deliberately and
expected to stay so** — see "Why this folder is empty" below; consuming VEX is
declared out of scope, revived only by an upstream document appearing together
with a product-aware filter. (The VEX this project *emits* is different, lives
under `artifacts/`, and ships: see `findings.openvex.json` in the schema docs.)

A VEX statement says whether a product is *actually* affected by a known
vulnerability, and why not when it is not: `vulnerable_code_not_present`,
`vulnerable_code_not_in_execute_path`, and so on. An SBOM says what is there; a
VEX says what matters.

## Why this folder is empty

Two blockers, both properties of the data rather than of missing code.

**No upstream documents exist for these dependencies.** Checked at the
conventional locations and in PyPI metadata for `langchain`,
`langchain-community`, `langchain-litellm`, `openai`, `streamlit` and `pyyaml`:
none publishes VEX, and none declares a security or VEX URL. That matches where
VEX adoption actually is — container images and a few large vendors, not PyPI or
npm packages.

**Only one Python component is exactly versioned.** A VEX statement names a
specific product version. Of the vulnerable fixture's five components,
`langchain-litellm` is `pinned` at 0.2.0; two are `inferred` from a range and two
are `unconstrained`. `SCHEMAS.md` already refuses to key anything on an inferred
range, because asserting a match against `~=0.3.25` would claim a vulnerability
the app may not have. The npm fixture is the opposite case — 80 of its 82
components are `locked` — so that is where a match could first be honest.

## What is here, and what is not

`manifest.json` pins every document: where it came from, when it was taken, and
whether it is a real upstream statement or one this project wrote. That
distinction is not optional. A hand-written document presented as measured
evidence would overstate the evaluation, the same way `ground_truth.json`'s
`source: ai_drafted` and `baseline.json`'s `source: tool_derived` exist to stop.

**Nothing under `src/` reads this folder.** That is asserted by a test, not
promised: a half-wired reader could make a claim the data cannot support, and an
empty folder with a manifest makes no claim at all.

## Adding a document

The auditor makes no network calls, so documents are fetched out-of-band as a
manual step and read from disk — the same policy `SCHEMAS.md` sets for advisory
snapshots, and for the same reason: a snapshot is reproducible, which is what an
evaluation needs.

1. Download the document into `vex/<source>/`.
2. Add its entry to `manifest.json`, including the date taken and whether it is
   upstream or hand-written.
3. Commit both. These are small files and they are the evidence a supply-chain
   finding would rest on, so an evaluation that cannot be reproduced from a
   clean clone is not reproducible.

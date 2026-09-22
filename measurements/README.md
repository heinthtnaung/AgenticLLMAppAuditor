# Measurements

The corpus behind the numbers in `src/council/redaction.py`,
`src/council/ollama.py`, `src/council/definitions.py` and `docs/COUNCIL.md`.

A measurement nobody can re-run is an assertion. Everything here exists so a
reader can disagree with a number by producing a different one.

## What is here

| Path | What it is |
|---|---|
| `corpus/pypi`, `corpus/npm`, `corpus/golang`, `corpus/rust` | four handwritten manifests pinning deliberately out-of-date packages |
| `rootfs/debian`, `rootfs/alpine` | two synthetic root filesystems: an `os-release`, a version marker and a package database listing old packages |
| `advisories.py` | runs the seven scans and reads them into one set of advisory texts |
| `redaction_gaps.py` | what `council.redaction` catches, lets past, and would cost to widen |
| `prompt_tokens.py` | what a member's prompt costs the pinned model, counted by the model |

The manifests and package databases are written by hand, not captured from a
real system. They are chosen to reach different advisory feeds — GHSA, OSV,
RustSec, the Debian and Alpine security trackers — not to describe a plausible
deployment. Editing one changes every number below, so re-run both scripts and
update the docstrings that cite them.

The seventh scan is not here: it is `fetched/vulnscout`, the repository this
project audits.

## Running it

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
python measurements/redaction_gaps.py
python measurements/prompt_tokens.py
```

`redaction_gaps.py` needs Trivy and the database snapshot in `~/.cache/trivy`,
and touches no network and no model. `prompt_tokens.py` additionally needs
`ollama serve` up with `qwen2.5:7b-instruct` pulled; it talks to loopback only.
The `NO_PROXY` export is this machine's corporate proxy, which otherwise answers
502 for a loopback request.

## The numbers, and what they support

**The corpus: 1,187 distinct advisories** across seven scans — 254 PyPI, 163
npm, 74 Go, 29 Rust, 608 Debian 11, 109 Alpine 3.14, 18 vulnscout. 1,255
findings, deduplicated by published id.

| Number | What it decided |
|---|---|
| **0** advisories redacted differently after bare vectors were added | adding the pattern costs nothing on real text, which is why it went in although it fires on nothing new |
| **0** vector-shaped strings surviving redaction | the panel rule holds on this corpus |
| **1** advisory carrying a prose score, `GHSA-pw6j-qg29-8w7f` | the prose gap stays open: the same sentence publishes an AC value in words that no pattern reaches |
| **878** advisories carrying some `x.y` number | what a general prose-score pattern would eat — three in four, all versions |
| **1** identifier in another namespace, `SNYK-JS-ANGULAR-570058`, in a URL | not worth a namespace list against prefixes like `DSA` that are live words |
| **0** advisories containing their own id | every identifier in advisory text is a cross-reference |
| **421** tokens for a prompt with no advisory in it | one metric's definitions, instructions and reply schema — not the 2,700 of the whole table |
| **4,897** tokens for the worst advisory's prompt | against 8,192 pinned: a 1.7× margin, not the "several times" an 18-advisory corpus suggested |
| **39** tokens of error on the guard's estimate | 0.8%, which is what makes four-characters-to-the-token acceptable in `refuse_overlong_prompt` |

It supersedes an earlier 153-advisory measurement — 18 vulnscout advisories and
135 from a PyPI manifest that was never committed. That manifest is why this
folder exists.

## Two limits, stated

**The Ubuntu rootfs was dropped.** A `rootfs/ubuntu` built the same way as the
Debian one returned 0 findings: Trivy keys Ubuntu advisories on Ubuntu package
versions, and the Debian version strings it was given match nothing. Fixing it
means sourcing real Ubuntu versions, which nobody has needed yet.

**RHSA is untested by occurrence.** Red Hat advisories need an rpm database,
which is a binary format this folder cannot synthesise offline. So the claim
that `RHSA-` identifiers do not appear in advisory text rests on their absence
from seven scans that do not index them — it is an untested namespace, not a
measured zero. The same holds for any feed reached only through an OS this
corpus does not cover.

# The knowledge base

What the remediation advice is grounded on. `src/checks/advise.py` asks the
local model how to fix each finding; since Phase 6 the prompt also carries a
few passages retrieved from here, each attributed in `remediation.json` so a
reader can open the page the advice leaned on.

**Only this file and `manifest.json` are committed**, and the manifest appears
the first time the index is built -- until then this folder holds nothing else.
The clones and the index are fetched and built out-of-band and gitignored, the
same policy as the corpus apps and the advisory database: the auditor makes no
network call, so nothing in `src/` fetches these. The manifest pins what was
indexed -- commit, content digest, embedding model, chromadb version -- so the
index can be rebuilt from the same inputs and checked against it.

## Setting it up

```sh
git clone --depth 1 https://github.com/OWASP/CheatSheetSeries knowledge/owasp-cheatsheets
ollama pull nomic-embed-text
python src/index_knowledge.py
```

The third step needs Ollama running. It reads every `cheatsheets/*.md`, cuts
the prose under each heading into passages (code blocks and tables are left
out), embeds them, builds the ChromaDB index under `knowledge/index/` and
writes `manifest.json`. Run it again after pulling a newer clone.

Without an index an audit still completes: `remediation.json` records
`knowledge_base.status: not_indexed` with the reason, and the advice is
written ungrounded, exactly as a missing Syft yields no bill of materials.

## Sources

| Name | Upstream | Licence | Indexed |
|---|---|---|---|
| `owasp-cheatsheets` | https://github.com/OWASP/CheatSheetSeries | CC BY-SA 4.0 | `cheatsheets/*.md` |

Passages from the Cheat Sheets are reproduced into `remediation.json` and
`remediation.md` under that licence; each carries its source and the URL of
the page it came from, and the report states the licence once. MITRE ATLAS was
considered as a second source and deferred (`docs/TODO.md`, Task 6.5).

## What the index must never do

Two of ChromaDB's defaults are switched off and asserted by tests
(`src/retrieval/store.py`): its default embedding function, which downloads a
model from the internet the first time it embeds text -- a refusing function is
always attached and the store takes vectors only -- and its usage telemetry.
Opening a client on a missing path would create a database file, so an audit
checks the index exists before opening anything; retrieval leaves the index
byte-identical.

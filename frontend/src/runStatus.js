// The server's run-status vocabulary, spelled once for the whole page.
//
// `web/run_record.py`'s `RUN_STATUSES` is the source; this is the copy the
// browser reads, and one copy is the most there may be. It was five, and they
// are exactly today's five importers: `useRun.js`, `RunSummary.jsx`,
// `StageProgress.jsx`, `AuditPage.jsx` and `HistoryTable.jsx`. The last of
// those is the one worth remembering -- it spelled all three as **bare object
// keys** (`{ finished: ..., running: ..., failed: ... }`), so the search that
// found the other four walked straight past it. A vocabulary can be duplicated
// in a form your search for duplicates cannot see.
//
// A test holds these three equal to the server's tuple, so a value renamed in
// `src/` fails there rather than silently un-triggering the audit redirect.

export const RUNNING = "running";
export const FINISHED = "finished";
export const FAILED = "failed";

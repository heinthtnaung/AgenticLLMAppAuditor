import { useEffect, useState } from "react";
import HistoryTable from "../components/HistoryTable.jsx";
import { clearHistory, fetchHistory, forgetRun } from "../api.js";
import { FAILED } from "../runStatus.js";

/** Ask once before deleting the runs a reader ticked.
 *
 * The finished ones are named separately because they are the ones that cost
 * something irreversible: a finished run's stored findings and its own
 * artifacts directory both go, and neither is recoverable.
 */
function confirmedPicked(runs) {
  const finished = runs.filter((run) => run.status !== FAILED).length;
  const also = finished ? `, ${finished} of them finished` : "";
  return window.confirm(
    `Delete ${runs.length} selected run${runs.length === 1 ? "" : "s"}${also}? `
    + "Their rows and the files each one wrote are deleted, and cannot be "
    + "recovered.");
}

/** Ask once before forgetting every failed run on the page. */
function confirmedForget(failed) {
  return window.confirm(
    `Forget ${failed.length} failed run${failed.length === 1 ? "" : "s"}, `
    + "across every repository? Their rows cannot be recovered.");
}

/** Ask twice before wiping the history, naming what is really at stake.
 *
 * Twice because this is the one control that destroys a *finished* run: its
 * stored envelope is the only copy of what that audit found once
 * `artifacts/<app>/` has been cleaned or written over by a later run, which is
 * what "overwritten" and "gone" in the files column already mean. The count is
 * the store's total and not the list's, because the list is capped and the
 * delete is not.
 */
function confirmedClear(stored, shown) {
  const hidden = stored > shown ? ` Only ${shown} of them are shown here.` : "";
  return window.confirm(
    `Delete all ${stored} stored run${stored === 1 ? "" : "s"}?${hidden} `
    + "A finished run's stored findings are the only copy once its files are "
    + "cleaned or written over.")
    && window.confirm("This cannot be undone. Delete the whole history?");
}

/** Every audit this server has run, newest first. */
export default function HistoryPage() {
  const [held, setHeld] = useState(null);
  const [error, setError] = useState(null);
  // What the last delete actually did, kept separately from `error`: a run of
  // five where two were refused is neither a success nor a failure, and
  // collapsing it into one of those loses the number a reader asked for.
  const [said, setSaid] = useState(null);
  // One flag for both page-level controls, so neither can be pressed while the
  // other is mid-flight and the two cannot interleave requests over one store.
  const [working, setWorking] = useState(false);
  // Which rows a reader ticked, by run id, across every repository group. Held
  // here rather than in the table so one delete can span groups, and cleared
  // after every delete: the ids are the server's and a refetch may not carry
  // them any more.
  const [picked, setPicked] = useState(() => new Set());

  // Bumped after a delete, which is how the list re-reads itself. Re-fetching
  // rather than splicing the row out: `stored_run_count` and the cap below are
  // the server's figures, and a page that removed a row locally would keep
  // reporting the old count beside a shorter list.
  const [read, setRead] = useState(0);

  useEffect(() => {
    let watching = true;
    fetchHistory()
      .then((found) => { if (watching) setHeld(found); })
      .catch((failure) => { if (watching) setError(failure.message); });
    return () => { watching = false; };
  }, [read]);

  function pick(runId) {
    setPicked((was) => {
      const next = new Set(was);
      if (!next.delete(runId)) next.add(runId);
      return next;
    });
  }

  async function forget(runs) {
    setError(null);
    setSaid(null);
    setWorking(true);
    // Sequential and counted. `Promise.all` would report whichever rejection
    // arrived last and say nothing about the rest; what a reader needs after
    // asking for five is how many went, not one message from an arbitrary one
    // of them. A refusal does not stop the others: each run is its own
    // decision on the server, so one that is no longer failed should not
    // cancel the four that still are.
    const refused = [];
    let gone = 0;
    for (const run of runs) {
      try {
        await forgetRun(run.run_id);
        gone += 1;
      } catch (failure) {
        refused.push(failure.message);
      }
    }
    setWorking(false);
    setPicked(new Set());
    setRead((was) => was + 1);
    setSaid({ asked: runs.length, gone, refused });
  }

  // One request, not a loop: the server deletes the whole table in one
  // statement, so there is no partial outcome to count and nothing a
  // per-row refusal could mean.
  async function clear(stored) {
    setError(null);
    setSaid(null);
    setWorking(true);
    try {
      const reply = await clearHistory();
      setSaid({ asked: stored, gone: reply.forgotten_count, refused: [] });
    } catch (failure) {
      setError(failure.message);
    }
    setWorking(false);
    setPicked(new Set());
    setRead((was) => was + 1);
  }

  if (error) {
    return (
      <div className="notice notice--error">
        <strong>The history could not be read.</strong>
        <p className="notice__detail">{error}</p>
      </div>
    );
  }
  if (!held) return <p className="empty">Reading the history…</p>;

  // The list is capped, so the two numbers differ once the store outgrows it --
  // and a reader comparing them is how they learn there is more than is shown.
  // The prose that stood beside them went on 2026-09-18; the figures did not,
  // because a list that silently omits rows is not a thing to leave unsaid.
  const capped = held.stored_run_count > held.runs.length;
  const failed = held.runs.filter((run) => run.status === FAILED);
  const chosen = held.runs.filter((run) => picked.has(run.run_id));
  return (
    <div className="card">
      <div className="history__head">
        <div>
          <h2 className="card__title">History</h2>
          <p className="card__hint">
            {held.stored_run_count} run{held.stored_run_count === 1 ? "" : "s"} stored
            {capped && `, showing the newest ${held.runs.length}`}
          </p>
        </div>
        {held.stored_run_count > 0 && (
          <div className="history__actions">
            {chosen.length > 0 && (
              <button type="button" className="filter filter--danger" disabled={working}
                      onClick={() => confirmedPicked(chosen) && forget(chosen)}>
                {`Delete ${chosen.length} selected`}
              </button>
            )}
            {failed.length > 0 && (
              <button type="button" className="filter" disabled={working}
                      onClick={() => confirmedForget(failed) && forget(failed)}>
                {`Forget all ${failed.length} failed`}
              </button>
            )}
            <button type="button" className="filter filter--danger" disabled={working}
                    onClick={() => confirmedClear(held.stored_run_count,
                                                  held.runs.length)
                                   && clear(held.stored_run_count)}>
              {working ? "Working…" : "Clear all"}
            </button>
          </div>
        )}
      </div>
      {said && (
        <p className={`notice notice--${said.refused.length ? "error" : "wait"}`}>
          <strong>
            {said.gone} of {said.asked} forgotten
            {said.refused.length > 0 && `, ${said.refused.length} refused`}.
          </strong>
          {said.refused.length > 0 && (
            <span className="notice__detail">{said.refused.join("; ")}</span>
          )}
        </p>
      )}
      <HistoryTable runs={held.runs} onForget={forget}
                    picked={picked} onPick={pick} />
    </div>
  );
}

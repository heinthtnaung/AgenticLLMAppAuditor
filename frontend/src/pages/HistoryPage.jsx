import { useEffect, useState } from "react";
import HistoryTable from "../components/HistoryTable.jsx";
import { fetchHistory, forgetRun } from "../api.js";

/** Every audit this server has run, newest first. */
export default function HistoryPage() {
  const [held, setHeld] = useState(null);
  const [error, setError] = useState(null);
  // What the last delete actually did, kept separately from `error`: a run of
  // five where two were refused is neither a success nor a failure, and
  // collapsing it into one of those loses the number a reader asked for.
  const [said, setSaid] = useState(null);

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

  async function forget(runs) {
    setError(null);
    setSaid(null);
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
    setRead((was) => was + 1);
    setSaid({ asked: runs.length, gone, refused });
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
  return (
    <div className="card">
      <h2 className="card__title">History</h2>
      <p className="card__hint">
        {held.stored_run_count} run{held.stored_run_count === 1 ? "" : "s"} stored
        {capped && `, showing the newest ${held.runs.length}`}
      </p>
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
      <HistoryTable runs={held.runs} onForget={forget} />
    </div>
  );
}

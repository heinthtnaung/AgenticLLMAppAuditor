import { useEffect, useState } from "react";
import HistoryTable from "../components/HistoryTable.jsx";
import { fetchHistory } from "../api.js";

/** Every audit this server has run, newest first. */
export default function HistoryPage() {
  const [held, setHeld] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let watching = true;
    fetchHistory()
      .then((found) => { if (watching) setHeld(found); })
      .catch((failure) => { if (watching) setError(failure.message); });
    return () => { watching = false; };
  }, []);

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
  const capped = held.stored_run_count > held.runs.length;
  return (
    <div className="card">
      <h2 className="card__title">Past runs</h2>
      <p className="card__hint">
        {held.stored_run_count} run{held.stored_run_count === 1 ? "" : "s"} stored
        {capped && `, showing the newest ${held.runs.length}`}. A finished run
        keeps its findings even after its files are cleaned from disk.
      </p>
      <HistoryTable runs={held.runs} />
    </div>
  );
}

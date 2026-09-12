import RunSummary from "../components/RunSummary.jsx";
import { AUDIT, navigate } from "../router.js";
import { useRun } from "../useRun.js";

/** One past run, opened from the history by its own link. */
export default function RunPage({ runId, stages, onRerun }) {
  const { record, error } = useRun(runId);

  if (error && !record) {
    return (
      <div className="notice notice--error">
        <strong>That run could not be read.</strong>
        <p className="notice__detail">{error}</p>
      </div>
    );
  }
  if (!record) return <p className="empty">Reading the run…</p>;

  return (
    <>
      <div className="card">
        <h2 className="card__title">Run this again</h2>
        <p className="card__hint">
          The options are carried back to the form, and you submit it yourself.
          A one-click repeat would re-send the audited source to a third party
          whenever the stored options asked for a model comparison, which is not
          something a page should do on one click.
        </p>
        <button className="run run--secondary" type="button"
                onClick={() => { onRerun(record); navigate(AUDIT); }}>
          Open in the audit form
        </button>
      </div>
      <RunSummary record={record} stages={stages} />
    </>
  );
}

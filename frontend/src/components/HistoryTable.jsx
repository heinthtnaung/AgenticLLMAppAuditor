import { count, seconds, when } from "../format.js";
import { navigate, runPath } from "../router.js";
import { FAILED, FINISHED, RUNNING } from "../runStatus.js";

// How a status reads. A dot and a word, not a pill: the reference design
// reserves pills for a severity, and a run's status is not one. `interrupted`
// is not a status the API has -- a run whose server stopped is stored as failed
// with that reason -- so three is the whole vocabulary, and a value outside it
// still shows as itself.
// Keyed by the constants, as `StageProgress` keys `MARK`. Written as bare
// object keys this was the sixth copy of the status vocabulary and the only
// one with no quotes to be grepped for -- which is why the test that found
// it looks for object keys as well as strings.
const TONE = { [FINISHED]: "low", [RUNNING]: "mid", [FAILED]: "crit" };

/** Every past run, newest first, each opening its own page. */
export default function HistoryTable({ runs }) {
  if (!runs.length) {
    return (
      <p className="empty">
        No audits yet. Every run started from this page is kept here, including
        the ones that failed.
      </p>
    );
  }
  return (
    <div className="table-scroll">
      <table className="table">
        <thead>
          <tr>
            <th>Started</th><th>Auditor</th><th>App</th><th>Status</th>
            <th>Findings</th><th>Surfaces</th><th>Took</th><th>Files</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.run_id} className="row--clickable"
                onClick={() => navigate(runPath(run.run_id))}>
              <td>{when(run.started_at)}</td>
              <td>{run.auditor}</td>
              <td className="mono">{run.app ?? run.repo_url}</td>
              <td className="nowrap">
                <span className={`dot dot--${TONE[run.status] ?? "none"}`} />
                {run.status}
              </td>
              <td>{count(run.finding_count)}</td>
              <td>{count(run.surface_count)}</td>
              <td>{seconds(run.seconds)}</td>
              <td>
                {!run.artifacts_present ? "gone"
                  : run.artifacts_current ? "on disk" : "overwritten"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

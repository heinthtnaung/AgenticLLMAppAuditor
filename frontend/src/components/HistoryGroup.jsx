import Icon from "./Icon.jsx";
import RunOptions from "./RunOptions.jsx";
import { count, seconds, when } from "../format.js";
import { navigate, runPath } from "../router.js";
import { FAILED, FINISHED, RUNNING } from "../runStatus.js";
import { failedIn } from "../repoGroup.js";

// How a status reads. A dot and a word, not a pill: the reference design
// reserves pills for a severity, and a run's status is not one.
const TONE = { [FINISHED]: "low", [RUNNING]: "mid", [FAILED]: "crit" };

/** Ask before forgetting. The endpoint has no authentication and this is final.
 *
 * `window.confirm` rather than a styled dialog: it blocks, it cannot be
 * mis-clicked past, and it needs nothing this page does not already have. The
 * count is in the question because "forget 1" and "forget 9" are different
 * decisions.
 */
function confirmed(failed) {
  return window.confirm(
    `Forget ${failed.length} failed run${failed.length === 1 ? "" : "s"}? `
    + "Their rows are deleted from the history and cannot be recovered.");
}

/** Where a run's files stand: on disk, written over, or gone. */
function files(run) {
  if (!run.artifacts_present) return "gone";
  return run.artifacts_current ? "on disk" : "overwritten";
}

/** One run, as a row that opens its own page. */
function Row({ run }) {
  return (
    <tr className="row--clickable" onClick={() => navigate(runPath(run.run_id))}>
      <td className="nowrap">{when(run.started_at)}</td>
      <td>{run.auditor}</td>
      <td className="nowrap">
        <span className={`dot dot--${TONE[run.status] ?? "none"}`} />
        {run.status}
      </td>
      <td><RunOptions options={run.options} /></td>
      <td>{count(run.finding_count)}</td>
      <td>{count(run.surface_count)}</td>
      <td className="nowrap">{seconds(run.seconds)}</td>
      <td className="nowrap">{files(run)}</td>
    </tr>
  );
}

/** Every run of one repository, folded away until asked for.
 *
 * Closed by default: the screenshot that prompted this had thirteen runs of one
 * repository under two spellings of its URL, which is a page of rows saying the
 * same thing. The header carries what a reader scans for -- which repository,
 * how many runs, whether any failed -- and opening it is one click.
 */
export default function HistoryGroup({ group, open, onToggle, onForget, forgetting }) {
  const failed = failedIn(group, FAILED);
  return (
    <>
      <div className="group">
        <button type="button" className="group__open" aria-expanded={open}
                onClick={onToggle}>
          <Icon name="chevron"
                className={open ? "disclose__mark disclose__mark--open" : "disclose__mark"} />
          <span className="group__name mono">{group.key}</span>
          {/* "shown", not "stored": the list this page was handed is capped at
              `HISTORY_LIST_LIMIT`, so a repository with ten runs behind the cap
              can head a group of three. The stored/shown pair beside the page
              heading is what makes this number readable. */}
          <span className="group__count">
            {group.runs.length} shown
          </span>
          {failed.length > 0 && (
            <span className="tag tag--crit">{failed.length} failed</span>
          )}
        </button>
        {failed.length > 0 && (
          <button type="button" className="filter group__forget"
                  disabled={forgetting}
                  onClick={() => confirmed(failed) && onForget(failed)}>
            {forgetting ? "Forgetting…" : `Forget ${failed.length} failed`}
          </button>
        )}
      </div>

      {open && (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Started</th><th>Auditor</th><th>Status</th><th>Options</th>
                <th>Findings</th><th>Surfaces</th><th>Took</th><th>Files</th>
              </tr>
            </thead>
            <tbody>
              {group.runs.map((run) => <Row key={run.run_id} run={run} />)}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

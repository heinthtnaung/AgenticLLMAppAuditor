import Icon from "./Icon.jsx";
import RunOptions, { cloudModel, isModelName, localModel } from "./RunOptions.jsx";
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

/** One arm's model as a cell: monospaced for a name, faint for its absence.
 *
 * A name is data and reads as data; "no model" and "unreachable" are this
 * page's own words about a gap, so they are not dressed up as identifiers.
 */
function ModelCell({ shown }) {
  return (
    <td className="nowrap">
      {isModelName(shown)
        ? <span className="mono">{shown}</span>
        : <span className="model--none">{shown}</span>}
    </td>
  );
}

/** One run, as a row that opens its own page, with a box that picks it out. */
function Row({ run, picked, onPick }) {
  return (
    <tr className="row--clickable" onClick={() => navigate(runPath(run.run_id))}>
      {/* `stopPropagation`, because the row navigates: without it, ticking the
          box would leave the page before the tick was recorded. */}
      <td className="pick" onClick={(event) => event.stopPropagation()}>
        {/* A real `<label>` with hidden text, **not** `aria-label`. The
            accessible name is the same either way, but on a bare form control
            some browsers render `aria-label` as hover text -- which is where
            the tooltip over this checkbox came from. A `<label>` is never
            rendered as a tooltip. */}
        <label className="pick__label">
          <span className="visually-hidden">
            Select the run started {when(run.started_at)}
          </span>
          <input type="checkbox" className="pick__box" checked={picked}
                 onChange={() => onPick(run.run_id)} />
        </label>
      </td>
      <td className="nowrap">{when(run.started_at)}</td>
      <td>{run.auditor}</td>
      <td className="nowrap">
        <span className={`dot dot--${TONE[run.status] ?? "none"}`} />
        {run.status}
      </td>
      <td><RunOptions options={run.options} /></td>
      {/* The whole run, not its options: what answered is served beside the
          record, because `options.model` is only what was asked for. */}
      <ModelCell shown={localModel(run)} />
      <ModelCell shown={cloudModel(run)} />
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
export default function HistoryGroup({ group, open, onToggle, onForget, forgetting,
                                      picked, onPick }) {
  const failed = failedIn(group, FAILED);
  return (
    <>
      <div className={open ? "group group--open" : "group"}>
        <button type="button" className="group__open" aria-expanded={open}
                onClick={onToggle}>
          <Icon name="chevron"
                className={open ? "disclose__mark disclose__mark--open" : "disclose__mark"} />
          <span className="group__name mono">{group.key}</span>
          {/* This group's rows, which is not necessarily this repository's
              runs: the list the page was handed is capped at
              `HISTORY_LIST_LIMIT`, so a repository with ten runs behind the cap
              heads a group of three. The heading's own "N runs stored" is the
              store's total, and the pair is what makes this number readable. */}
          <span className="group__count">
            {group.runs.length} record{group.runs.length === 1 ? "" : "s"}
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
        <div className="group__runs">
          <table className="table">
            <thead>
              <tr>
                <th className="pick" />
                <th>Started</th><th>Auditor</th><th>Status</th><th>Options</th>
                <th>Local</th><th>Cloud</th>
                <th>Findings</th><th>Surfaces</th><th>Took</th><th>Files</th>
              </tr>
            </thead>
            <tbody>
              {group.runs.map((run) => (
                <Row key={run.run_id} run={run} picked={picked.has(run.run_id)}
                     onPick={onPick} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

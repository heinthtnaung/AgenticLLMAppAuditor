import { seconds, when } from "../format.js";

/** When a run started and finished, and how long the whole job took.
 *
 * Its own component because two views show it: the overlay while a run is
 * going, and the report once it is stored. Copied instead, the two would drift
 * over which durations a run has — and the pair below is the whole point.
 */
export default function RunStamps({ record }) {
  return (
    <div className="stamps">
      <div><span className="stamps__label">Started</span> {when(record.started_at)}</div>
      <div><span className="stamps__label">Finished</span> {when(record.finished_at)}</div>
      {/* Two durations, and they are not the same fact: the job includes
          resolving the repository, the audit's own timer starts after it. */}
      <div><span className="stamps__label">Whole job</span> {seconds(record.seconds)}</div>
      {record.result && (
        <div><span className="stamps__label">Audit itself</span>
          {" "}{seconds(record.result.seconds)}</div>
      )}
    </div>
  );
}

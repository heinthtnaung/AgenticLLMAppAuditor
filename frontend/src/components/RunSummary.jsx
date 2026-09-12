import DownloadPanel from "./DownloadPanel.jsx";
import ResultsDashboard from "./ResultsDashboard.jsx";
import StageProgress from "./StageProgress.jsx";
import StatRail from "./StatRail.jsx";
import { seconds, when } from "../format.js";
import { useListing } from "../useRun.js";

const FINISHED = "finished";

/** When a run started and finished, and how long the whole job took. */
function Stamps({ record }) {
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

/** Every file the run left on disk, in the rail. */
function DownloadCard({ record, listing }) {
  return (
    <div className="card">
      <h2 className="card__title">Download</h2>
      <p className="card__hint">
        Every file this run wrote. <code>report.md</code> is the one to read; the
        SBOM, AIBOM, SARIF and OpenVEX documents are here for a tool.
      </p>
      <DownloadPanel runId={record.run_id} listing={listing}
                     current={record.artifacts_current} />
    </div>
  );
}

/** One run: how far it got, what it found, and what it left on disk.
 *
 * Three columns, and the two outer ones follow the scroll: the numbers and the
 * files are what a reader keeps referring back to while reading down the
 * findings, so scrolling them away costs a trip back up the page.
 */
export default function RunSummary({ record, stages }) {
  const listing = useListing(record.run_id, record.artifacts_present);
  const finished = record.status === FINISHED;

  return (
    <div className="report">
      <aside className="report__rail">
        {record.result && <StatRail result={record.result} />}
      </aside>

      <div className="report__main">
        <div className="card">
          <h2 className="card__title">{record.app ?? record.repo_url}</h2>
          <p className="card__hint mono">{record.repo_url}</p>
          <Stamps record={record} />
          <StageProgress stages={stages} announced={record.stages}
                         status={record.status} />
          {record.error && (
            <p className="notice notice--error">
              <strong>The audit did not complete.</strong>
              <span className="notice__detail">{record.error}</span>
            </p>
          )}
        </div>
        {record.result && <ResultsDashboard result={record.result} />}
      </div>

      <aside className="report__rail report__rail--files">
        {finished && <DownloadCard record={record} listing={listing} />}
      </aside>
    </div>
  );
}

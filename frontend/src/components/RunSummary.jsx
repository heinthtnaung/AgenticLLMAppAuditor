import DownloadPanel from "./DownloadPanel.jsx";
import ResultsDashboard from "./ResultsDashboard.jsx";
import RunStamps from "./RunStamps.jsx";
import StageProgress from "./StageProgress.jsx";
import StatRail from "./StatRail.jsx";
import { FINISHED } from "../runStatus.js";
import { useListing } from "../useRun.js";

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
          <RunStamps record={record} />
          <StageProgress stages={stages} announced={record.stages}
                         status={record.status} />
          {record.error && (
            <p className="notice notice--error">
              <strong>The audit did not complete.</strong>
              <span className="notice__detail">{record.error}</span>
            </p>
          )}
        </div>
        {record.result && <ResultsDashboard result={record.result}
                                            runId={record.run_id} />}
        {/* No rendered-report card. `report.html` and `remediation.html` are
            two of the sixteen files the run wrote, and the Download panel now
            opens any of them -- a card that framed those two alone was a second
            way to read a subset of what the file list already holds. */}
      </div>

      <aside className="report__rail report__rail--files">
        {finished && <DownloadCard record={record} listing={listing} />}
        {/* No evidence panel. Attaching a file changed no finding by design, so
            the page offered an upload whose only effect was on the page --
            `POST /api/runs/{id}/uploads` and the record's `uploads` field are
            untouched and still tested, so nothing was demolished to hide the
            control. */}
      </aside>
    </div>
  );
}

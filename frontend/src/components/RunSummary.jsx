import { useState } from "react";
import ArmToggle, { CLOUD, LOCAL } from "./ArmToggle.jsx";
import ComparisonCard from "./ComparisonCard.jsx";
import DownloadPanel from "./DownloadPanel.jsx";
import ResultsDashboard from "./ResultsDashboard.jsx";
import RunStamps from "./RunStamps.jsx";
import StageProgress from "./StageProgress.jsx";
import StatRail from "./StatRail.jsx";
import { FINISHED } from "../runStatus.js";
import { useListing } from "../useRun.js";

/** Every file one arm left on disk, in the rail. */
function DownloadCard({ record, listing, refused, arm }) {
  return (
    <div className="card">
      <h2 className="card__title">
        {arm === CLOUD ? "Cloud model files" : "Local model files"}
      </h2>
      <p className="card__hint">
        Every file this arm wrote. <code>report.md</code> is the one to read;
        the SBOM, AIBOM, SARIF and OpenVEX documents are here for a tool.
      </p>
      {/* The server's own sentence, not a guess at it. A listing can be refused
          because the directory is gone, because a later run of the app
          overwrote it, or because this run had no hosted arm -- three different
          statements, and rendering one blank for all of them is the gap-as-a-
          result this page exists to avoid. */}
      {refused && <p className="caveat">{refused}</p>}
      <DownloadPanel runId={record.run_id} listing={listing} arm={arm}
                     current={record.artifacts_current} />
    </div>
  );
}

/** One run: how far it got, what it found, and what it left on disk.
 *
 * Three columns, and the two outer ones follow the scroll: the numbers and the
 * files are what a reader keeps referring back to while reading down the
 * findings, so scrolling them away costs a trip back up the page.
 *
 * A `--compare-models` run audited the same tree twice, so everything that is
 * *one arm's* -- the rail's counts, the findings, the surfaces, the files --
 * follows one control. The alternative was showing the local arm's ten
 * findings under a rail that said ten while the hosted arm's nine sat in a
 * summary card above, which is two numbers for one page.
 */
export default function RunSummary({ record, stages }) {
  const [arm, setArm] = useState(LOCAL);
  const finished = record.status === FINISHED;
  const result = record.result;
  const comparison = result?.comparison ?? null;
  // The hosted arm's own documents are already in the reply, so choosing it
  // fetches nothing. Falling back to the local arm rather than trusting the
  // state: a run with no second arm has no `comparison` to show.
  const reading = arm === CLOUD && comparison ? comparison : result;
  // Keyed on the arm, so switching re-reads that arm's own directory. The
  // hosted arm's files are served now, so the only thing that makes a listing
  // absent is the directory being gone or overwritten -- and `refused` carries
  // which, because those are not the same statement.
  const { listing, refused } = useListing(record.run_id, record.artifacts_present, arm);

  return (
    <div className="report">
      <aside className="report__rail">
        {reading && <StatRail result={reading} />}
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
        {result && <ComparisonCard result={result} />}
        {comparison && (
          <ArmToggle chosen={arm} onChoose={setArm}
                     localSystem={comparison.compared_with}
                     cloudSystem={comparison.system} />
        )}
        {reading && <ResultsDashboard result={reading} runId={record.run_id}
                                      arm={arm} />}
        {/* No rendered-report card. `report.html` and `remediation.html` are
            two of the sixteen files the run wrote, and the Download panel now
            opens any of them -- a card that framed those two alone was a second
            way to read a subset of what the file list already holds. */}
      </div>

      <aside className="report__rail report__rail--files">
        {finished && <DownloadCard record={record} listing={listing}
                                   refused={refused} arm={arm} />}
        {/* No evidence panel. Attaching a file changed no finding by design, so
            the page offered an upload whose only effect was on the page --
            `POST /api/runs/{id}/uploads` and the record's `uploads` field are
            untouched and still tested, so nothing was demolished to hide the
            control. */}
      </aside>
    </div>
  );
}

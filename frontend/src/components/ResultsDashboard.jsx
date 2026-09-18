import AdvisoryComponents from "./AdvisoryComponents.jsx";
import FindingList from "./FindingList.jsx";
import MissingArtifact from "./MissingArtifact.jsx";
import SurfaceList from "./SurfaceList.jsx";

/** The findings, or the reason there are none to show. */
function FindingsCard({ document, unreached, runId, arm }) {
  return (
    <div className="card">
      <h2 className="card__title">Findings</h2>
      <p className="card__hint">
        Each carries the risk class, the check that produced it, and where it
        sits. <strong>Click a row for how to fix it.</strong> A probe finding
        also shows the reasoning the model gave.
      </p>
      {/* Without this, "no findings" beside a repository carrying vulnerable
          packages reads as a clean bill. A finding here means a vulnerable
          component an LLM surface can reach; that is a narrower claim than
          "nothing is wrong", and the difference has to be said where the zero
          is, not only further down the page. */}
      {document && !document.findings.length && unreached > 0 && (
        <p className="notice notice--error">
          <strong>No findings, and that is not a clean bill.</strong>
          <span className="notice__detail">
            {unreached} dependenc{unreached === 1 ? "y carries" : "ies carry"} a
            known advisory, itemised under Known vulnerabilities in
            dependencies. None is reached by an LLM surface, which is why none
            is a finding of this tool.
          </span>
        </p>
      )}
      {document
        ? <FindingList findings={document.findings} probes={document.probes}
                       runId={runId} arm={arm} />
        : <MissingArtifact name="findings.json" />}
    </div>
  );
}

/** What the checks ran over. */
function SurfacesCard({ document, runId }) {
  return (
    <div className="card">
      <h2 className="card__title">LLM surfaces</h2>
      <p className="card__hint">
        What the checks ran over. A defect at a line no surface covers is one
        this tool cannot reach. <strong>Click a row to see the line.</strong>
      </p>
      {document
        ? <SurfaceList surfaces={document.surfaces} runId={runId} />
        : <MissingArtifact name="surfaces.json" />}
    </div>
  );
}

/** Which checks had something to examine, and where the rest of the output went. */
function CoverageCard({ checks, artifactsDir }) {
  return (
    <div className="card">
      <h2 className="card__title">What could look</h2>
      <p className="card__hint">
        A check absent here could not run at all (a missing Syft, no advisory
        data), which the scorer reads as a gap rather than a clean result.
      </p>
      <div className="checks">
        {checks.length
          ? checks.map((check) => (
              <span key={check} className="tag tag--rule">{check}</span>
            ))
          : <span className="empty">no check had anything to examine</span>}
      </div>
      <p className="caveat">
        Artifacts are written to <code>{artifactsDir}</code>. This page renders
        two of them; every file the run wrote is in the Download panel, and
        <code>report.md</code> is the one to read.
      </p>
    </div>
  );
}

/** One arm's results: the findings, what it looked at, and where they went.
 *
 * `arm` reaches `FindingList`, which reads that arm's own `remediation.json`
 * rather than the other one's. The two-arm summary is `ComparisonCard`,
 * rendered by `RunSummary` above the control that chooses between them: it is
 * about both arms, so it does not belong to either one's results.
 */
export default function ResultsDashboard({ result, runId, arm }) {
  const findings = result.findings;
  const surfaces = result.surfaces;
  const checksRun = findings?.coverage?.checks_run;
  const checks = checksRun ?? [];
  // A count of components, not of findings, and *only the ones no LLM surface
  // reaches* -- a component an LLM surface does reach becomes a
  // `known_advisory` finding instead, and is counted in the Findings stat. The
  // label carries the qualifier because the number does not mean "every
  // vulnerable dependency".
  const unreached = findings?.coverage?.advisory_unreached_component_count;

  return (
    <>
      <FindingsCard document={findings} unreached={unreached ?? 0} runId={runId}
                    arm={arm} />
      <AdvisoryComponents coverage={findings?.coverage} />
      <SurfacesCard document={surfaces} runId={runId} />
      <CoverageCard checks={checks} artifactsDir={result.artifacts_dir} />
    </>
  );
}

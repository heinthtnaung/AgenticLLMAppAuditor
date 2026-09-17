import { count, seconds } from "../format.js";

/** One arm's headline numbers, named by the system that produced them. */
function Arm({ system, envelope }) {
  return (
    <div className="arm">
      <div className="arm__system mono">{system}</div>
      <dl className="arm__facts">
        <div><dt>Findings</dt><dd>{count(envelope.findings?.finding_count)}</dd></div>
        <div><dt>Surfaces</dt><dd>{count(envelope.surfaces?.surface_count)}</dd></div>
        <div><dt>Took</dt><dd>{seconds(envelope.seconds)}</dd></div>
      </dl>
    </div>
  );
}

/** The hosted arm beside the local one, when a run audited twice.
 *
 * Renders nothing at all when `comparison` is null -- which means one arm ran,
 * never that a second arm found nothing.
 */
export default function ComparisonCard({ result }) {
  if (!result.comparison) return null;
  return (
    <div className="card">
      <h2 className="card__title">Local against hosted</h2>
      <p className="card__hint">
        The same tree audited twice. Only the semantic probe is model-dependent,
        so a difference in findings is a difference in what one model confirmed
        — not two different tools disagreeing.
      </p>
      <div className="arms">
        <Arm system={result.comparison.compared_with} envelope={result} />
        <Arm system={result.comparison.system} envelope={result.comparison} />
      </div>
      {/* Said rather than implied: the download panel serves the local arm's
          directory, and nothing checks whether a later run overwrote the
          hosted arm's. Offering its files here would be a link with no
          evidence path behind it. */}
      <p className="caveat">
        The hosted arm wrote to <code>{result.comparison.artifacts_dir}</code>.
        Those files are not downloadable from this page and nothing here checks
        whether a later run overwrote them — read them on disk.
      </p>
    </div>
  );
}

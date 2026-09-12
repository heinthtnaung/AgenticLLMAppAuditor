import Icon from "./Icon.jsx";
import { ABSENT, count } from "../format.js";

/** One headline number, its label and its icon. */
function Stat({ value, label, icon, tone }) {
  return (
    <div className={`stat${tone ? ` stat--${tone}` : ""}`}>
      <div className="stat__row">
        <span className="stat__label">{label}</span>
        <span className="stat__chip"><Icon name={icon} /></span>
      </div>
      <div className="stat__value">{value}</div>
    </div>
  );
}

/** The four headline numbers, stacked in the rail beside the report.
 *
 * `Vulnerable deps, unreached` carries its qualifier because the number does:
 * it counts only components no LLM surface reaches, and one that *is* reached
 * becomes a finding instead, counted in the Findings stat. Position is not part
 * of the claim -- these stack in a rail on a wide screen and sit in a row on a
 * narrow one.
 */
export default function StatRail({ result }) {
  const findings = result.findings;
  const surfaces = result.surfaces;
  const checksRun = findings?.coverage?.checks_run;

  return (
    <div className="stats stats--rail">
      <Stat label="Findings" icon="finding" tone="high"
            value={findings ? findings.findings.length : ABSENT} />
      <Stat label="LLM surfaces" icon="surface"
            value={surfaces ? surfaces.surfaces.length : ABSENT} />
      {/* No tone. Red on this page means a database said CRITICAL, and this is
          a number the tool counted itself -- wearing red would be the tool
          assigning a severity, which it does not do anywhere else. */}
      <Stat label="Vulnerable deps, unreached" icon="package"
            value={count(findings?.coverage?.advisory_unreached_component_count)} />
      <Stat label="Checks that could look" icon="check" tone="low"
            value={checksRun ? checksRun.length : ABSENT} />
    </div>
  );
}

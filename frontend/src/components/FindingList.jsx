import { useState } from "react";

// How each risk class reads. **A reading aid, not a rating.** This tool never
// assigns its own severity -- a severity here is always a quotation from an
// advisory database, carried beside its source -- so among the *severity pills*
// red is used only where a database said CRITICAL, and a risk class never gets
// it. (`--crit` also paints a gap notice, which is a different thing: that is
// the page reporting its own inability to say something.) LLM01 and LLM02 are
// the two that put untrusted text in front of a model or a database, so they
// carry the strongest tone this page is willing to use; the rest are muted.
//
// The keys are `OWASP_IDS`, declared beside the `Finding` record in
// `src/artifacts/finding.py`, and a test holds the two copies together.
const RISK_TONE = {
  LLM01: "high",
  LLM02: "high",
  LLM03: "mid",
  LLM06: "mid",
  AUDITABILITY: "none",
};

const CONFIRMED = "confirmed";

// The filter showing everything. Not a risk class, so it cannot collide.
const ALL = "all";

// How the finding was reached. `static` repeats byte for byte on every run;
// `probe` means a model was consulted and it may not.
const DETECTION_LABEL = { static: "static", probe: "model probe" };

/** Where a finding sits, as `file:line`, or the component when it has no line. */
function location(finding) {
  if (finding.file && finding.line) return `${finding.file}:${finding.line}`;
  return finding.component_name ?? finding.purl ?? "—";
}

/** One block of model-written prose, labelled so it is not read as evidence. */
function Prose({ label, text }) {
  if (!text) return null;
  return (
    <p className="prose__block">
      <span className="prose__label">{label}</span>
      {text}
    </p>
  );
}

/** The risk classes present: the known ones in tone order, then anything else.
 *
 * Derived from the findings, not from the tone map. A class the map has never
 * heard of would otherwise be counted in "All N" with no chip to filter it --
 * the asymmetry `AdvisoryComponents.severitiesIn` exists to avoid.
 */
function classesIn(findings) {
  const present = [...new Set(findings.map((finding) => finding.owasp_id))];
  const known = Object.keys(RISK_TONE).filter((owasp) => present.includes(owasp));
  const unforeseen = present.filter((owasp) => !(owasp in RISK_TONE)).sort();
  return [...known, ...unforeseen];
}

/** One button per risk class actually found, plus everything. */
function Filters({ findings, chosen, onChoose }) {
  const classes = classesIn(findings);
  // One class is not a choice, so no buttons rather than a button that does
  // nothing when pressed.
  if (classes.length < 2) return null;
  return (
    <div className="filters">
      {[ALL, ...classes].map((owasp) => (
        <button key={owasp} type="button"
                className={`filter${chosen === owasp ? " filter--on" : ""}`}
                onClick={() => onChoose(owasp)}>
          {owasp === ALL ? `All ${findings.length}` : owasp}
          {owasp !== ALL &&
            ` ${findings.filter((finding) => finding.owasp_id === owasp).length}`}
        </button>
      ))}
    </div>
  );
}

/** Every finding, with the model's reasoning where it wrote any. */
export default function FindingList({ findings, probes }) {
  const [chosen, setChosen] = useState(ALL);
  if (!findings.length) {
    return (
      <p className="empty">
        No findings. That is a result, not a blank: <code>coverage.checks_run</code>{" "}
        in findings.json says which checks had something to look at.
      </p>
    );
  }

  // A probe finding cites the probe that confirmed it, and both sides ship the
  // same `probe_id`, so the join is that field on both.
  const rationale = Object.fromEntries(
    (probes ?? [])
      .filter((probe) => probe.outcome === CONFIRMED)
      .map((probe) => [probe.probe_id, probe.detail]),
  );

  const shown = chosen === ALL
    ? findings
    : findings.filter((finding) => finding.owasp_id === chosen);

  return (
    <>
      <Filters findings={findings} chosen={chosen} onChoose={setChosen} />
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr><th>Risk</th><th>Check</th><th>Title</th><th>Where</th><th>How</th></tr>
          </thead>
          <tbody>
            {shown.map((finding) => {
              const prose = [
                ["Narrative", finding.narrative],
                ["Probe", rationale[finding.probe_id]],
              ].filter(([, text]) => text);
              return [
                <tr key={finding.finding_id}>
                  <td><span className={`tag tag--${RISK_TONE[finding.owasp_id] ?? "none"}`}>
                    {finding.owasp_id}
                  </span></td>
                  <td><span className="tag tag--rule">{finding.rule_id}</span></td>
                  <td>{finding.title}</td>
                  <td className="mono">{location(finding)}</td>
                  <td>{DETECTION_LABEL[finding.detection] ?? finding.detection}</td>
                </tr>,
                prose.length ? (
                  <tr key={`${finding.finding_id}-prose`}>
                    <td className="prose" colSpan={5}>
                      {prose.map(([label, text]) => (
                        <Prose key={label} label={label} text={text} />
                      ))}
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

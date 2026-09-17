import { useEffect, useState } from "react";
import ExpandAll from "./ExpandAll.jsx";
import FindingAdvice from "./FindingAdvice.jsx";
import { fetchArtifactJson } from "../api.js";
import { useExpanded } from "../useExpanded.js";

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

// The document that holds "how to fix it", read on demand rather than carried
// in the reply: the envelope's keys are frozen, and this is one artifact of
// sixteen the download route already serves.
const REMEDIATION = "remediation.json";

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

/** Every advice entry a run wrote, keyed by the finding it is about. */
function useAdvice(runId) {
  const [advice, setAdvice] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let watching = true;
    fetchArtifactJson(runId, REMEDIATION)
      .then((document) => {
        if (!watching) return;
        setAdvice(Object.fromEntries(
          (document.advice ?? []).map((entry) => [entry.finding_id, entry])));
        setLoading(false);
      })
      // A run that wrote no remediation document is a run with no advice, not a
      // broken page: the rows still open and say so.
      .catch(() => { if (watching) { setAdvice({}); setLoading(false); } });
    return () => { watching = false; };
  }, [runId]);

  return { advice, loading };
}

/** Every finding, with the model's reasoning and, on click, how to fix it. */
export default function FindingList({ findings, probes, runId }) {
  const [chosen, setChosen] = useState(ALL);
  const { advice, loading } = useAdvice(runId);
  const shown = chosen === ALL
    ? findings
    : findings.filter((finding) => finding.owasp_id === chosen);
  // Above the early return below, with every other hook: an empty list would
  // otherwise render one fewer hook than a filled one, which React refuses the
  // moment the list stops being empty. Keyed on what is on screen, so "show
  // every fix" means the filtered rows and not the hidden ones.
  const rows = useExpanded(shown.map((finding) => finding.finding_id));
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

  return (
    <>
      <Filters findings={findings} chosen={chosen} onChoose={setChosen} />
      <ExpandAll allOpen={rows.allOpen} onToggle={rows.toggleAll} noun="fix" />
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Risk</th><th>Check</th><th>Title</th><th>Where</th>
              <th>How</th><th />
            </tr>
          </thead>
          <tbody>
            {shown.map((finding) => {
              const prose = [
                ["Narrative", finding.narrative],
                ["Probe", rationale[finding.probe_id]],
              ].filter(([, text]) => text);
              const expanded = rows.isOpen(finding.finding_id);
              return [
                <tr key={finding.finding_id} className="row--clickable"
                    aria-expanded={expanded}
                    onClick={() => rows.toggle(finding.finding_id)}>
                  <td><span className={`tag tag--${RISK_TONE[finding.owasp_id] ?? "none"}`}>
                    {finding.owasp_id}
                  </span></td>
                  <td><span className="tag tag--rule">{finding.rule_id}</span></td>
                  <td>
                    {finding.title}
                    {/* Nine advisory findings share one title and differ only by
                        the CVE, so the id that distinguishes them is shown. */}
                    {finding.advisory_id && (
                      <span className="finding__advisory mono">{finding.advisory_id}</span>
                    )}
                  </td>
                  <td className="mono">{location(finding)}</td>
                  <td>{DETECTION_LABEL[finding.detection] ?? finding.detection}</td>
                  <td className="row__action">
                    <span className="details">{expanded ? "Hide" : "How to fix"}</span>
                  </td>
                </tr>,
                prose.length ? (
                  <tr key={`${finding.finding_id}-prose`}>
                    <td className="prose" colSpan={6}>
                      {prose.map(([label, text]) => (
                        <Prose key={label} label={label} text={text} />
                      ))}
                    </td>
                  </tr>
                ) : null,
                expanded ? (
                  <tr key={`${finding.finding_id}-advice`}>
                    <td className="prose" colSpan={6}>
                      <FindingAdvice advice={advice?.[finding.finding_id]}
                                     loading={loading} />
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

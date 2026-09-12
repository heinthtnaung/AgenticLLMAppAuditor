import { useState } from "react";
import AuditForm from "../components/AuditForm.jsx";
import RunSummary from "../components/RunSummary.jsx";
import { startAudit } from "../api.js";
import { useRun } from "../useRun.js";

// What the form starts as, and what the backend expects. Every flag is off:
// the tool's own default is an audit that calls no model and opens no socket.
export const INITIAL = {
  url: "",
  semantic_probe: false,
  draft_key: false,
  compare_models: false,
  cloud_model: "",
};

/** Start an audit, then watch it. */
export default function AuditPage({ stages, prefill }) {
  const [values, setValues] = useState(prefill ?? INITIAL);
  const [runId, setRunId] = useState(null);
  const [refused, setRefused] = useState(null);
  const { record, error } = useRun(runId);
  const running = record?.status === "running";

  const change = (key, value) => setValues((old) => ({ ...old, [key]: value }));

  async function submit() {
    setRefused(null);
    // Cleared before the run, not after it: leaving the previous audit on
    // screen beside a new one reads as though it were this run's answer.
    setRunId(null);
    try {
      setRunId((await startAudit(values)).run_id);
    } catch (failure) {
      setRefused(failure.message);
    }
  }

  return (
    <>
      <AuditForm values={values} onChange={change} onSubmit={submit}
                 running={running} />
      {refused && (
        <div className="notice notice--error">
          <strong>The audit was refused before it started.</strong>
          <p className="notice__detail">{refused}</p>
        </div>
      )}
      {error && (
        <div className="notice notice--wait">
          Lost contact with the server; still asking. <span className="mono">{error}</span>
        </div>
      )}
      {record && <RunSummary record={record} stages={stages} />}
    </>
  );
}

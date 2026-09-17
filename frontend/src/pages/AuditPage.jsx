import { useEffect, useState } from "react";
import AuditForm from "../components/AuditForm.jsx";
import RunOverlay from "../components/RunOverlay.jsx";
import { startAudit } from "../api.js";
import { navigate, runPath } from "../router.js";
import { FAILED, FINISHED, RUNNING } from "../runStatus.js";
import { useRun } from "../useRun.js";

// What the form starts as, and what the backend expects. Every flag is off:
// the tool's own default is an audit that calls no model and opens no socket.
export const INITIAL = {
  url: "",
  auditor: "",
  model: "",
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
  // The 202's own record, kept rather than discarded. `run_record.body` says
  // the accept answers the same shape a poll does, and keeping it closes the
  // window between the click and the first `GET` answering: without it that
  // window had no overlay, no notice and a live Audit button, so a first poll
  // that failed left a bare form polling for ever, and a second click detached
  // the page from a run that then completed unseen.
  const [accepted, setAccepted] = useState(null);
  const { record: polled, error } = useRun(runId);
  const record = polled ?? accepted;
  // `Boolean(runId)` because `setRunId(null)` commits one render before
  // `useRun` resets: a stale record would otherwise build `/runs/null`.
  const running = Boolean(runId) && record?.status === RUNNING;

  // An effect, because pushing history is synchronising with something outside
  // React rather than deriving a value: the audit finishes on a poll the page
  // did not initiate, so there is no event to hang this on.
  //
  // `runId`, not `record.run_id`: the id came back in the 202 and is what is
  // being polled, and `runPath(undefined)` matches no route, so `routeOf` would
  // answer "audit" -- a silent bounce back to this page with nothing said.
  //
  // Only `FINISHED` moves the page. A failed run has not been through all the
  // steps, and navigating off a failure before it is read is how a reason gets
  // lost; it is reported below instead, beside the URL that produced it.
  useEffect(() => {
    if (record?.status !== FINISHED || !runId) return;
    navigate(runPath(runId));
  }, [record?.status, runId]);

  const change = (key, value) => setValues((old) => ({ ...old, [key]: value }));

  async function submit() {
    setRefused(null);
    // Cleared before the run, not after it: leaving the previous audit on
    // screen beside a new one reads as though it were this run's answer.
    setRunId(null);
    setAccepted(null);
    try {
      // Both, from one answer: the id to poll, and the record to show until the
      // first poll replaces it.
      const started = await startAudit(values);
      setAccepted(started);
      setRunId(started.run_id);
    } catch (failure) {
      setRefused(failure.message);
    }
  }

  const failed = Boolean(runId) && record?.status === FAILED;
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
      {/* A run that started and stopped badly, reported where the form still
          shows what was typed. The overlay is gone by now: a page covered by a
          panel a reader may not dismiss, over a run that is over, states the
          outcome and offers nothing to do about it. */}
      {failed && (
        <div className="notice notice--error">
          <strong>The audit did not complete.</strong>
          <p className="notice__detail">{record.error}</p>
          <p className="notice__detail">
            <a href={runPath(runId)}
               onClick={(event) => { event.preventDefault(); navigate(runPath(runId)); }}>
              Open this run&rsquo;s page
            </a>{" "}
            for the stages it reached before it stopped.
          </p>
        </div>
      )}
      {/* While the run is going, and only then. `error` goes into the card
          because the page body is under the scrim. */}
      {running && (
        <RunOverlay record={record} stages={stages} error={error}
                    onOpenRun={() => navigate(runPath(runId))} />
      )}
    </>
  );
}

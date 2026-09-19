import { useEffect, useState } from "react";
import KeyBadge from "../components/KeyBadge.jsx";
import KeyEditor from "../components/KeyEditor.jsx";
import PageHead from "../components/PageHead.jsx";
import RunSummary from "../components/RunSummary.jsx";
import { fetchDraft } from "../api.js";
import { AUDIT, navigate } from "../router.js";
import { useRun } from "../useRun.js";

/** The grading key this run drafted, if it drafted one.
 *
 * Keyed on the run and not on its app. A run drafts into its own folder, so two
 * runs of one app have two keys and asking by app could only ever answer about
 * one of them -- which is the half of this that was broken: the editor read
 * `grading_keys/drafts/` and the server had written under `artifacts/runs/`.
 */
function useDraft(runId) {
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    if (!runId) return undefined;
    let watching = true;
    fetchDraft(runId)
      .then((found) => { if (watching) setDraft(found); })
      // No draft for this run is the ordinary case -- `--draft-key` writes one
      // and most runs do not ask for it -- so it is absence, not an error.
      .catch(() => { if (watching) setDraft(null); });
    return () => { watching = false; };
  }, [runId]);

  return [draft, setDraft];
}

/** One past run, opened from the history by its own link. */
export default function RunPage({ runId, stages, onRerun }) {
  const { record, error } = useRun(runId);
  const [draft, setDraft] = useDraft(runId);
  const [editing, setEditing] = useState(false);

  if (error && !record) {
    return (
      <div className="notice notice--error">
        <strong>That run could not be read.</strong>
        <p className="notice__detail">{error}</p>
      </div>
    );
  }
  if (!record) return <p className="empty">Reading the run…</p>;

  // Carries the options back to the form; the submit stays yours. A one-click
  // repeat would re-send the audited source to a third party whenever the
  // stored options asked for a model comparison, which is not something a page
  // should do on one click -- so the button opens the form rather than running.
  const actions = (
    <div className="head__actions">
      {draft && (
        <button className="run run--secondary" type="button"
                onClick={() => setEditing(!editing)}>
          {editing ? "Close the key" : "Grading key"}
          <KeyBadge keyDocument={draft.key} />
        </button>
      )}
      <button className="run run--secondary" type="button"
              onClick={() => { onRerun(record); navigate(AUDIT); }}>
        Re-run
      </button>
    </div>
  );

  return (
    <>
      {/* One line, which means inside `.head__subtitle`'s 74ch. The sentence
          about a finished run keeping its findings went with the second line;
          the Download card is where that matters and it says so there. */}
      <PageHead title="Report" action={actions}>
        What one audit found, the stages it reached, and every file it wrote.
      </PageHead>
      {/* Beside the run it was drafted from, rather than on a page of its own:
          a key is about one app, and this is where that app's evidence is. */}
      {editing && draft && (
        <KeyEditor draft={draft} runId={runId} onClose={() => setEditing(false)}
                   onSaved={setDraft} />
      )}
      <RunSummary record={record} stages={stages} />
    </>
  );
}

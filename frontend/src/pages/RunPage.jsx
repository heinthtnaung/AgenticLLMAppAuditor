import { useEffect, useState } from "react";
import KeyBadge from "../components/KeyBadge.jsx";
import KeyEditor from "../components/KeyEditor.jsx";
import PageHead from "../components/PageHead.jsx";
import RunSummary from "../components/RunSummary.jsx";
import { fetchDraft } from "../api.js";
import { AUDIT, navigate } from "../router.js";
import { useRun } from "../useRun.js";

/** The drafted key for this run's app, if one was drafted. */
function useDraft(app) {
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    if (!app) return undefined;
    let watching = true;
    fetchDraft(app)
      .then((found) => { if (watching) setDraft(found); })
      // No draft for this app is the ordinary case -- `--draft-key` writes one
      // and most runs do not ask for it -- so it is absence, not an error.
      .catch(() => { if (watching) setDraft(null); });
    return () => { watching = false; };
  }, [app]);

  return [draft, setDraft];
}

/** One past run, opened from the history by its own link. */
export default function RunPage({ runId, stages, onRerun }) {
  const { record, error } = useRun(runId);
  const [draft, setDraft] = useDraft(record?.app);
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
                title="The grading key this app was drafted, for a human to correct"
                onClick={() => setEditing(!editing)}>
          {editing ? "Close the key" : "Grading key"}
          <KeyBadge keyDocument={draft.key} />
        </button>
      )}
      <button className="run run--secondary" type="button"
              title="Opens the audit form with this run's options. You submit it."
              onClick={() => { onRerun(record); navigate(AUDIT); }}>
        Re-run
      </button>
    </div>
  );

  return (
    <>
      <PageHead title="Report" action={actions}>
        What one audit found, the stages it went through, and every file it
        wrote. A finished run keeps its findings even after its files are
        cleaned from disk.
      </PageHead>
      {/* Beside the run it was drafted from, rather than on a page of its own:
          a key is about one app, and this is where that app's evidence is. */}
      {editing && draft && (
        <KeyEditor draft={draft} onClose={() => setEditing(false)}
                   onSaved={setDraft} />
      )}
      <RunSummary record={record} stages={stages} />
    </>
  );
}

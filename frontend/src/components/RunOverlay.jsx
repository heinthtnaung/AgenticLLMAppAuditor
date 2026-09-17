import Modal from "./Modal.jsx";
import RunStamps from "./RunStamps.jsx";
import StageProgress from "./StageProgress.jsx";

/** The audit advancing, over the page rather than under it.
 *
 * Shown only while the run is going, which is what leaves it one job: a
 * finished run navigates to its own page, and a failed one is reported in the
 * notice the audit page owns, beside the URL that produced it.
 *
 * **No dismiss, and exactly one exit.** An audit cannot be cancelled, so
 * closing this would hide a run that carries on — but the scrim covers the nav
 * bar too, so offering no way out would strand a reader for the length of a
 * multi-minute audit. The link opens this run's own page, which renders a
 * running run and keeps polling. Nothing is lost by taking it, and it is not a
 * cancel.
 */
export default function RunOverlay({ record, stages, error, onOpenRun }) {
  return (
    <Modal title={record.app ?? record.repo_url} titleId="run-overlay-title">
      <p className="card__hint mono">{record.repo_url}</p>
      <RunStamps record={record} />
      <StageProgress stages={stages} announced={record.stages}
                     status={record.status} />
      {/* Inside the card, because the page body is under the scrim: the one
          message that can arrive *during* a run was invisible exactly when it
          mattered while `useRun` went on polling behind the cover. */}
      {error && (
        <p className="notice notice--wait">
          Lost contact with the server; still asking.{" "}
          <span className="mono">{error}</span>
        </p>
      )}
      <div className="form__actions overlay__actions">
        <button className="run run--secondary" type="button" onClick={onOpenRun}>
          Open this run&rsquo;s page
        </button>
      </div>
    </Modal>
  );
}

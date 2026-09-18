import Modal from "./Modal.jsx";
import RunStamps from "./RunStamps.jsx";
import StageProgress from "./StageProgress.jsx";

/** The audit advancing, over the page rather than under it.
 *
 * Shown only while the run is going, which is what leaves it one job: a
 * finished run navigates to its own page, and a failed one is reported in the
 * notice the audit page owns, beside the URL that produced it.
 *
 * **No dismiss and no exit**, which is a decision the user made on 2026-09-18
 * and worth stating rather than leaving to be discovered. An audit cannot be
 * cancelled, so closing this would hide a run that carries on. The link out was
 * removed on 2026-09-18 at the user's request; the scrim is `z-index: 20` and
 * `.topbar` is 3,
 * so the nav is covered until the run reaches a terminal status -- the page
 * then navigates itself on `finished`, or drops the overlay on `failed`.
 * `docs/TODO.md` carries what that costs.
 */
export default function RunOverlay({ record, stages, error }) {
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
    </Modal>
  );
}

// Which arm's audit the page below is showing. Two values, not a boolean, so a
// third arm would be a new entry rather than a rename of `isCloud`.
export const LOCAL = "local";
export const CLOUD = "cloud";

/** Which arm's results everything below shows, and the system that produced them.
 *
 * Switching reads a document that was already in the reply -- `comparison`
 * carries the hosted arm's own `findings` and `surfaces` -- so nothing is
 * recomputed and nothing is fetched. What a reader is choosing is which of two
 * audits of the same tree to look at, not a filter over one of them.
 */
export default function ArmToggle({ chosen, onChoose, localSystem, cloudSystem }) {
  const arms = [[LOCAL, "Local model", localSystem], [CLOUD, "Cloud model", cloudSystem]];
  return (
    <div className="arm-pick">
      <span className="arm-pick__label">Showing</span>
      <div className="filters arm-pick__buttons">
        {arms.map(([arm, label, system]) => (
          <button key={arm} type="button"
                  className={`filter${chosen === arm ? " filter--on" : ""}`}
                  aria-pressed={chosen === arm}
                  onClick={() => onChoose(arm)}>
            {label}
            {/* The system name, because the cards below are that arm's own
                documents and `agentic_auditor` / `cloud_auditor` is how every
                artifact and the scorer spell them. */}
            <span className="arm-pick__system mono">{system}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

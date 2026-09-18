/** Said when an artifact was never written, which is not the same as empty.
 *
 * The distinction this whole tool is about: "no findings" is a result, "no
 * findings.json" is a gap. Rendering them the same way would let a run that
 * could not look read as a run that looked and found nothing clean.
 */
export default function MissingArtifact({ name }) {
  return (
    <p className="notice notice--error">
      <strong>{name} was not written.</strong>
      <span className="notice__detail">
        This is a gap, not a clean result: the audit did not get far enough to
        produce it. The server console says why.
      </span>
    </p>
  );
}

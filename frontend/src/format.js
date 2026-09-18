// Turning facts into words. Kept out of the components so each one can be read
// without a detour, and so "N/A" for absent is spelled once.

// What a missing number shows as. Never "0": a count with no document behind it
// is a gap, and the whole tool exists to keep those two apart.
export const ABSENT = "N/A";

/** A byte count a person can read. */
export function bytes(count) {
  if (typeof count !== "number") return ABSENT;
  if (count < 1024) return `${count} B`;
  if (count < 1024 * 1024) return `${(count / 1024).toFixed(1)} kB`;
  return `${(count / (1024 * 1024)).toFixed(1)} MB`;
}

/** An ISO 8601 UTC stamp in the reader's own locale and zone. */
export function when(stamp) {
  if (!stamp) return ABSENT;
  const at = new Date(stamp);
  return Number.isNaN(at.getTime()) ? stamp : at.toLocaleString();
}

/** A duration in seconds, or a dash when the run has not finished. */
export function seconds(value) {
  return typeof value === "number" ? `${value.toFixed(1)}s` : ABSENT;
}

/** A count, or a dash when no document stands behind it. */
export function count(value) {
  return typeof value === "number" ? String(value) : ABSENT;
}

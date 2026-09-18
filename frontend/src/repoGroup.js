// Which runs are about the same repository.
//
// **The rule is not here.** `src/repo_url.py::canonical_url` owns it and the
// server serves the answer as `canonical_repo_url`, so this file groups on a
// value rather than deriving one. A `.git` strip written again in JavaScript
// would be a second owner of a join key `pipeline._reused` already joins on --
// and unlike the run-status vocabulary, which is a closed set of three a test
// can compare name-for-name, a function over an open domain cannot be pinned
// equal to another implementation by any number of examples.

/** The runs gathered by repository, newest group first, each newest run first.
 *
 * Grouped on the server's `canonical_repo_url` and never on `app`: a run that
 * failed before it resolved one has no app at all, and those are exactly the
 * rows a reader wants beside the successful runs of the same repository rather
 * than in a group of their own.
 */
export function groupRuns(runs) {
  const groups = new Map();
  runs.forEach((run) => {
    const key = run.canonical_repo_url;
    if (!groups.has(key)) groups.set(key, { key, runs: [] });
    groups.get(key).runs.push(run);
  });
  // Insertion order is the server's order, which is newest first, so the group
  // a reader sees first is the one with the most recent run in it.
  return [...groups.values()];
}

/** Every run in this group that failed, which are the only ones that may be forgotten.
 *
 * The status word is a **parameter** rather than an import, and the real reason
 * is not "so the page keeps one copy of the vocabulary" -- importing `FAILED`
 * from `runStatus.js` would keep one copy too. It is that this module must
 * import nothing at all, so `test_repo_group_runs.py` can lift it whole into a
 * `.mjs` and run it under node. That is a test shaping a production signature,
 * which is worth doing and worth saying rather than dressing up as something
 * else.
 */
export function failedIn(group, failedStatus) {
  return group.runs.filter((run) => run.status === failedStatus);
}

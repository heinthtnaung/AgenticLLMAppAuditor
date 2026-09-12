// What each stage is, in words. Keyed by the vocabulary the server serves, and
// falling back to the stage's own name -- a stage added in `src/` should show
// up as itself rather than disappear from the list.
const SAID = {
  fetch: "Fetch and pin the repository",
  surfaces: "Find the LLM surfaces",
  dependencies: "Build the SBOM and AIBOM",
  advisories: "Read advisory data",
  checks: "Run every check",
  advice: "Build remediation advice",
  write: "Write the artifacts",
  publish: "Author VEX and export the reports",
};

const DONE = "done";
const WORKING = "working";
const PENDING = "pending";
const UNREACHED = "unreached";
const RUNNING = "running";

const MARK = { [DONE]: "\u2713", [WORKING]: "\u27f3", [PENDING]: "\u00b7", [UNREACHED]: "\u00b7" };

/** Where one stage stands: announced, being worked on, waiting, or never reached. */
function stateOf(stage, index, announced, status) {
  if (announced.includes(stage)) return DONE;
  // Any run that is no longer going reached no further, so the rest are not
  // pending -- saying "pending" about a stage that will never run is the same
  // kind of lie as showing 0 for a count with no document behind it. This
  // covers a failed run, a local-path audit that ends at `write`, and a
  // `--compare-models` run, which announces nothing at all.
  if (status !== RUNNING) return UNREACHED;
  if (index === announced.length) return WORKING;
  return PENDING;
}

/** The audit advancing, stage by stage, with what has not happened yet shown. */
export default function StageProgress({ stages, announced, status }) {
  return (
    <ol className="stages">
      {stages.map((stage, index) => {
        const state = stateOf(stage, index, announced, status);
        return (
          <li key={stage} className={`stage stage--${state}`}>
            <span className="stage__mark" aria-hidden="true"><span>{MARK[state]}</span></span>
            <span className="stage__name">{SAID[stage] ?? stage}</span>
          </li>
        );
      })}
    </ol>
  );
}

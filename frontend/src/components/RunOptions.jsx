// What a run asked for, from the options the record already carries. The three
// flags are the ones that change what the audit does; `url` and `auditor` are
// shown elsewhere on the row, so they are not repeated here. The two model
// names used to live in this cell too and now have columns of their own, which
// is why the helpers below are exported rather than rendered here.
import { ABSENT } from "../format.js";

const FLAGS = [
  ["semantic_probe", "semantic probe"],
  ["draft_key", "draft key"],
  ["compare_models", "compare models"],
];

// `model_run.status` from `src/artifacts/findings_document.py`, which is a
// closed set of three. Only two are named here: `used` never reaches these
// words, because a used run always carries an identifier to show instead --
// `model_provenance` raises if it does not.
const DISABLED = "disabled";
const UNAVAILABLE = "unavailable";

// **Three different absences, and they are not interchangeable.** This column
// said "server default" for every run that named no model, which read as "a
// model answered, we just did not pick it" -- and on a run with no semantic
// probe no model answered at all. That is a gap rendered as a result, the one
// thing this page may not do.
const SAID = {
  [DISABLED]: "no model",
  [UNAVAILABLE]: "unreachable",
};

/** The model that answered for one arm, or which kind of nothing it was.
 *
 * Reads the **served** fields, not `options`: `options.model` is what was
 * *asked for* and is empty on almost every run, while
 * `findings.json`'s `model_run` records what actually answered. There is
 * deliberately no fallback to `options.model` -- printing a requested name on a
 * run whose model was unreachable would be a fact-shaped guess.
 */
function modelOf(identifier, status) {
  if (identifier) return identifier;
  return SAID[status] ?? ABSENT;
}

/** The local model that answered, or which kind of nothing it was. */
export function localModel(run) {
  return modelOf(run.local_model_identifier, run.local_model_status);
}

/** The hosted model that answered. `N/A` covers "there was no second arm". */
export function cloudModel(run) {
  return modelOf(run.cloud_model_identifier, run.cloud_model_status);
}

/** Whether a cell holds a model's name rather than a statement about its absence. */
export function isModelName(shown) {
  return shown !== ABSENT && !Object.values(SAID).includes(shown);
}

/** The flags one run was started with. */
export default function RunOptions({ options }) {
  // No `!options` branch. The column is `TEXT NOT NULL`, the record's field is
  // a `dict`, `asdict` always carries it, and `{}` is truthy -- so the guard
  // was a branch against a case no producer can reach, and the class it
  // rendered was a live CSS rule no markup could ever select. The same reason
  // the delete route has no defensive `artifacts_dir` check.
  const chosen = FLAGS.filter(([key]) => options[key]);
  return (
    <div className="run-options">
      {chosen.length === 0
        ? <span className="tag tag--rule">defaults</span>
        : chosen.map(([key, label]) => (
            <span key={key} className="tag tag--mid">{label}</span>
          ))}
    </div>
  );
}

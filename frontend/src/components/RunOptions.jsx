// What a run asked for, from the options the record already carries. The three
// flags are the ones that change what the audit does; `url` and `auditor` are
// shown elsewhere on the row, so they are not repeated here.
const FLAGS = [
  ["semantic_probe", "semantic probe"],
  ["draft_key", "draft key"],
  ["compare_models", "compare models"],
];

/** The options one run was started with, and the models it named. */
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
      {/* Named, or "server default" -- and deliberately not resolved against
          `GET /api/model`'s `configured_model`, which reports what the server
          is set to *now* rather than what answered then. The row cannot say
          which model ran when none was named: `findings.json`'s `model_run`
          records it, and the history summary drops the result envelope. */}
      <span className="run-options__model">
        local <span className="mono">{options.model || "server default"}</span>
      </span>
      {/* Only under `compare_models`: a cloud model named without it is refused
          before the audit starts, so showing one here would be showing a value
          that never reached a model. */}
      {options.compare_models && (
        <span className="run-options__model">
          cloud <span className="mono">{options.cloud_model || "server default"}</span>
        </span>
      )}
    </div>
  );
}

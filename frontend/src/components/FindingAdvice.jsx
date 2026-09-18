// What `remediation.json` can say about one finding. A closed vocabulary in
// `src/artifacts/remediation.py`, and the three mean different things: advice
// was written, advice was **refused** for a named reason, or no model was
// reachable to ask. A refusal is not an absence of advice, and the difference
// is one this project measured rather than assumed.
const WRITTEN = "written";
const REJECTED = "rejected";
const UNAVAILABLE = "unavailable";

const SAID = {
  [REJECTED]: "The model's answer was refused.",
  [UNAVAILABLE]: "No advice: the model could not be reached for this finding.",
};

/** Where a passage came from, so advice is never ungrounded prose. */
function Sources({ sources }) {
  if (!sources?.length) return null;
  return (
    <div className="advice__sources">
      <span className="prose__label">Grounded in</span>
      <ul>
        {sources.map((source) => (
          <li key={`${source.path}#${source.heading}`}>
            <a href={source.url} target="_blank" rel="noreferrer noopener">
              {source.heading}
            </a>{" "}
            <span className="mono">{source.path}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The remediation advice for one finding, or why there is none. */
export default function FindingAdvice({ advice, loading }) {
  if (loading) return <p className="empty">Reading the advice…</p>;
  if (!advice) {
    return (
      <p className="advice__none">
        <code>remediation.json</code> holds no entry for this finding, which is
        not the same as advice that was refused. The run may not have written
        one.
      </p>
    );
  }
  if (advice.status !== WRITTEN) {
    return (
      <p className="advice__none">
        <strong>{SAID[advice.status] ?? advice.status}</strong>{" "}
        {advice.reason && (
          <>Reason: <code>{advice.reason}</code>
          {advice.rejected_on && <> (on its <code>{advice.rejected_on}</code>)</>}.{" "}</>
        )}
        The finding above stands either way: advice is written about a finding,
        never the other way round.
      </p>
    );
  }
  return (
    <div className="advice">
      <p className="advice__guidance">{advice.guidance}</p>
      {advice.snippets?.map((snippet, at) => (
        <figure className="advice__snippet" key={at}>
          <figcaption>
            {snippet.label}
            {snippet.language && <span className="mono"> · {snippet.language}</span>}
          </figcaption>
          <pre><code>{snippet.code}</code></pre>
        </figure>
      ))}
      {/* Said plainly because this tool never patches: a snippet is an
          illustration of a safer shape, not a change to apply. */}
      <p className="advice__caveat">
        Model-written, and illustrative. This tool reports; it never patches,
        so nothing here has been applied to the audited code or tested against it.
      </p>
      <Sources sources={advice.sources} />
    </div>
  );
}

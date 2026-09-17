import OptionsMenu from "./OptionsMenu.jsx";

/** The target, who is running it, the options, and the button. */
export default function AuditForm({ values, onChange, onSubmit, running }) {
  const ready = values.url.trim().length > 0 && values.auditor.trim().length > 0;

  return (
    <form
      className="card"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready && !running) onSubmit();
      }}
    >
      <h2 className="card__title">Target</h2>
      <p className="card__hint">
        An https:// link is fetched and pinned at its current commit. A
        filesystem path is refused: it would resolve against the server's own
        disk, which is a far larger permission than cloning a public repository.
      </p>

      <label className="field">
        <span className="field__label">Auditor</span>
        <input
          className="field__input"
          type="text"
          required
          placeholder="who is running this audit"
          value={values.auditor}
          disabled={running}
          onChange={(event) => onChange("auditor", event.target.value)}
        />
        {/* Recorded with the run and shown on the report, and deliberately in
            no artifact: two people auditing one commit still produce
            byte-identical files. The server has no authentication, so this is
            a claim about who ran it, not proof of one. */}
        <p className="field__note">
          Kept with the run and shown on its report. It goes into no artifact,
          so the files an audit writes stay identical whoever runs it.
        </p>
      </label>

      <label className="field">
        <span className="field__label">Repository</span>
        <input
          className="field__input field__input--large"
          type="text"
          placeholder="https://github.com/owner/app"
          value={values.url}
          disabled={running}
          onChange={(event) => onChange("url", event.target.value)}
        />
      </label>

      <OptionsMenu values={values} onChange={onChange} disabled={running} />

      <div className="form__actions form__actions--centre">
        <button className="run run--large" type="submit" disabled={!ready || running}>
          {running && <span className="spinner" aria-hidden="true" />}
          {running ? "Auditing…" : "Audit"}
        </button>
      </div>
    </form>
  );
}

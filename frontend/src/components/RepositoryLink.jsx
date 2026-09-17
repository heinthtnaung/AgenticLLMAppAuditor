import Icon from "./Icon.jsx";

// Where this tool's own source lives. Not the audited repository -- that one
// changes per run and is named on the report; this is the auditor itself.
const SOURCE_URL = "https://github.com/heinthtnaung/AgenticLLMAppAuditor";

/** A corner link to the auditor's own source, opened in its own tab. */
export default function RepositoryLink() {
  return (
    <a className="source-link" href={SOURCE_URL}
       target="_blank" rel="noreferrer noopener"
       title="The auditor's own source on GitHub (opens a new tab)"
       aria-label="The auditor's own source on GitHub, opens in a new tab">
      <Icon name="github" />
    </a>
  );
}

import Icon from "./Icon.jsx";

// Who built this. **One list, in one place** -- this is a Master's project and
// a footer is where a reader looks for authorship, so a name here is a claim
// about a person rather than decoration. Given by the project owner, and not
// derived from the commit history, which names only one of the three.
//
// Held in the order it was given and **sorted for display rather than by
// hand**, so alphabetical order is a property of the code instead of something
// a later edit can quietly break.
const MEMBERS = ["Tan Bing Hong", "Hein Thet Naung", "Neo Jia Wei"];
const NAMED = [...MEMBERS].sort((one, other) => one.localeCompare(other));

// Where this tool's own source lives. Not the audited repository: that one
// changes per run and is named on the report.
const SOURCE_URL = "https://github.com/heinthtnaung/AgenticLLMAppAuditor";

/** Who built this, on one line, with a link to the auditor's own source.
 *
 * Two things this deliberately does not carry, both because they are said
 * elsewhere on the same screen: the description sentence, which the audit
 * page's own head states above the form where it matters, and the brand mark,
 * which the top bar states on every page.
 */
export default function SiteFooter() {
  return (
    <footer className="footer">
      <div className="footer__inner">
        {/* No brand mark here. The top bar carries it on every page, two rows
            above on a short one, and naming the tool twice on one screen told
            a reader nothing the first one had not. */}
        <p className="footer__members">
          <span className="footer__label">Project members:</span>{" "}
          {NAMED.join(", ")}
        </p>

        {/* No label above it: the mark and the word say what it is. */}
        <a className="footer__source" href={SOURCE_URL}
           target="_blank" rel="noreferrer noopener">
          <Icon name="github" />
          <span>GitHub</span>
        </a>
      </div>
    </footer>
  );
}

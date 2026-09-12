import { useState } from "react";

// Severities as the advisory database words them, worst first. The order is the
// display order, and `UNRATED` is not one of them -- a database that rated
// nothing is not the same as one that rated something low, and 46 of the
// advisories on a real scan carry no severity at all.
//
// **Not treated as the whole vocabulary.** Trivy has a fifth word, `UNKNOWN`,
// and nothing in `src/` constrains what arrives here -- the severity is copied
// verbatim from the database and carried as a quotation. So the list below
// orders the words this page knows and `severitiesIn` derives the rest from the
// data, rather than a word being counted in the total with no chip to filter it.
const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const UNRATED = "unrated";

// Red only here, and only because a database said CRITICAL. This tool never
// picks a severity of its own; every value in this map is a quotation.
const TONE = {
  CRITICAL: "crit",
  HIGH: "high",
  MEDIUM: "mid",
  LOW: "low",
  [UNRATED]: "none",
};

// `coverage.advisory_data` when no advisory database was read at all.
const NOT_INGESTED = "not_ingested";

const ALL = "all";

/** How the database rated one advisory, or that it did not. */
function severityOf(advisory) {
  return advisory.severity ?? UNRATED;
}

/** A purl is percent-encoded in the artifact; scoped npm names read badly that way. */
function readable(purl) {
  try {
    return decodeURIComponent(purl);
  } catch {
    // A literal `%` in a purl would throw. The encoded form is still the truth.
    return purl;
  }
}

/** Every severity present: the known words worst-first, then anything else. */
function severitiesIn(counts) {
  // Both halves filtered the same way. `tally` never emits a zero, so a count
  // of none is unreachable from any artifact -- but filtering one half and not
  // the other is the kind of asymmetry a reader has to stop and check.
  const counted = (severity) => Boolean(counts[severity]);
  const known = SEVERITIES.filter(counted);
  const unforeseen = Object.keys(counts)
    .filter((severity) => severity !== UNRATED && !SEVERITIES.includes(severity))
    .filter(counted)
    .sort();
  // Unrated last: it is the absence of a rating, not the mildest one.
  return [...known, ...unforeseen, ...(counts[UNRATED] ? [UNRATED] : [])];
}

/** How many advisories carry each severity, across every component. */
function tally(items) {
  const counts = {};
  for (const item of items) {
    for (const advisory of item.advisories) {
      const severity = severityOf(advisory);
      counts[severity] = (counts[severity] ?? 0) + 1;
    }
  }
  return counts;
}

/** One component, with every advisory the database holds against it. */
function Component({ item, only }) {
  const shown = only === ALL
    ? item.advisories
    : item.advisories.filter((advisory) => severityOf(advisory) === only);
  if (!shown.length) return null;
  return (
    <li className="vuln">
      <code className="vuln__purl mono">{readable(item.purl)}</code>
      <span className="vuln__advisories">
        {shown.map((advisory) => (
          <span key={advisory.id} className={`tag tag--${TONE[severityOf(advisory)] ?? "none"}`}>
            {advisory.id}{advisory.severity ? ` ${advisory.severity}` : " unrated"}
          </span>
        ))}
      </span>
    </li>
  );
}

/** The vulnerable dependencies no LLM surface reaches.
 *
 * Deliberately prominent, and deliberately not folded into the findings. A
 * finding in this tool means a vulnerable component an LLM surface can actually
 * reach; nothing reaches these. But they are real, and showing only the
 * findings is how a repository full of vulnerable packages reads as clean --
 * which is what `report.md` says at length and this page used to omit.
 */
export default function AdvisoryComponents({ coverage }) {
  const [only, setOnly] = useState(ALL);
  if (!coverage) return null;

  if (coverage.advisory_data === NOT_INGESTED) {
    return (
      <div className="card">
        <h2 className="card__title">Known vulnerabilities in dependencies</h2>
        <p className="notice notice--error">
          <strong>No advisory data was read.</strong>
          <span className="notice__detail">
            So a supply-chain finding here names a package but not what is known
            to be wrong with it, and this section is empty because nothing was
            checked — not because nothing was found.
          </span>
        </p>
      </div>
    );
  }

  const items = coverage.advisory_unreached_components ?? [];
  const counts = tally(items);
  const present = severitiesIn(counts);
  // Summed from every count, not from `present`: a total that could disagree
  // with the chips beside it would be the page's own arithmetic, not the data's.
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0);

  return (
    <div className="card">
      <h2 className="card__title">Known vulnerabilities in dependencies</h2>
      <p className="card__hint">
        Known-vulnerability data: <code>{coverage.advisory_generator_name}</code>{" "}
        {coverage.advisory_generator_version}, database of{" "}
        <code>{coverage.advisory_db_updated_at}</code>.
      </p>

      {!items.length ? (
        <p className="empty">
          No component carries a known advisory. That is a result: the database
          above was read and matched nothing.
        </p>
      ) : (
        <>
          <p className="caveat">
            <strong>{items.length} component{items.length === 1 ? "" : "s"} carry
            a known advisory</strong> ({total} advisor{total === 1 ? "y" : "ies"} in
            total). None is reached by an LLM surface, so none is a scored finding
            of this tool — but they are real, and an ordinary dependency scanner
            would flag every one.
          </p>
          <div className="bars">
            {present.map((severity) => (
              <div key={severity} className={`bar--${TONE[severity] ?? "none"}`}>
                <div className="bar__head">
                  <span>{severity}</span>
                  <span className="bar__count">{counts[severity]}</span>
                </div>
                <div className="bar__track">
                  <div className="bar__fill"
                       style={{ width: `${(counts[severity] / total) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="filters">
            <button type="button" className={`filter${only === ALL ? " filter--on" : ""}`}
                    onClick={() => setOnly(ALL)}>
              All {total}
            </button>
            {present.map((severity) => (
              <button key={severity} type="button"
                      className={`filter${only === severity ? " filter--on" : ""}`}
                      onClick={() => setOnly(severity)}>
                {severity} {counts[severity]}
              </button>
            ))}
          </div>
          <ul className="vulns">
            {items.map((item) => (
              <Component key={item.purl} item={item} only={only} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import PageHead from "./components/PageHead.jsx";
import SiteFooter from "./components/SiteFooter.jsx";
import TopBar from "./components/TopBar.jsx";
import AuditPage, { INITIAL } from "./pages/AuditPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";
import RunPage from "./pages/RunPage.jsx";
import { fetchStages } from "./api.js";
import { useRoute } from "./router.js";

// One entry, not two. The history page carries no head: its own card is titled
// and the sentence that stood here was removed on 2026-09-18 at the user's
// request. `head` is looked up and may be undefined, which the render guards.
const HEADS = {
  audit: {
    title: "Audit an application",
    // The parentheses stand where the copy had em dashes: those are barred from
    // this UI as a house style, so the wording is kept and the punctuation is
    // not.
    line: "A non-invasive security auditor for LLM applications. Evaluate your "
        + "codebase against the OWASP Top 10 for LLMs (backed by strict SBOM "
        + "and AIBOM evidence) without ever executing, patching, or modifying "
        + "your code.",
  },
};

export default function App() {
  const route = useRoute();
  const [stages, setStages] = useState([]);
  // What "run this again" hands the form. Held here rather than in the audit
  // page, which unmounts while another page is showing.
  const [prefill, setPrefill] = useState(INITIAL);

  // Fetched once, not restated in JavaScript: the stage vocabulary lives in
  // `src/reporting/progress.py`, and a second copy of a closed vocabulary
  // across a language boundary is how the two copies start disagreeing.
  useEffect(() => {
    let watching = true;
    fetchStages()
      .then((found) => { if (watching) setStages(found.stages); })
      // An empty list is honest: the progress panel then shows only what the
      // run has actually announced, rather than inventing a list of steps.
      .catch(() => { if (watching) setStages([]); });
    return () => { watching = false; };
  }, []);

  // The run page renders its own head, because the head carries a button that
  // needs the record this component has not fetched.
  const head = HEADS[route.page];
  return (
    <div className="shell">
      {/* Decorative and stated as such: three drifting tints behind the page,
          carrying no information, so a reader using a screen reader loses
          nothing by not hearing about them. */}
      <div className="waves" aria-hidden="true">
        <span /><span /><span />
      </div>
      <TopBar page={route.page} />
      <main className={`content${route.page === "run" ? " content--wide" : ""}`}>
        {head && <PageHead title={head.title}>{head.line}</PageHead>}
        {route.page === "history" && <HistoryPage />}
        {route.page === "run" && (
          <RunPage runId={route.runId} stages={stages}
                   onRerun={(record) => setPrefill({ ...INITIAL, ...record.options,
                                                     url: record.repo_url })} />
        )}
        {route.page === "audit" && (
          // The key remounts the page when a re-run changes the prefill:
          // `AuditPage` seeds its form with `useState(prefill)`, which only
          // reads its argument on the first render.
          <AuditPage key={JSON.stringify(prefill)} stages={stages} prefill={prefill} />
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

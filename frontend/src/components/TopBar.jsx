import Icon from "./Icon.jsx";
import ModelStatus from "./ModelStatus.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import { AUDIT, HISTORY, navigate } from "../router.js";

const PAGES = [
  { path: AUDIT, name: "Audit", page: "audit", icon: "audit" },
  { path: HISTORY, name: "History", page: "history", icon: "history" },
];

/** The brand, the two pages, and the theme toggle, across the top. */
export default function TopBar({ page }) {
  return (
    <header className="topbar">
      <div className="topbar__inner">
        <div className="brand">
          <Icon name="shield" className="brand__mark" />
          <span className="brand__name">LLM&nbsp;App Auditor</span>
        </div>

        <nav className="nav">
          {PAGES.map((entry) => (
            <a key={entry.path} href={entry.path}
               className={`nav__link${page === entry.page ? " nav__link--here" : ""}`}
               aria-current={page === entry.page ? "page" : undefined}
               onClick={(event) => {
                 // Left-click with no modifier only: a middle or ctrl click
                 // should still open a real tab, which means letting the
                 // browser have the event rather than intercepting it.
                 if (event.button !== 0 || event.metaKey || event.ctrlKey
                     || event.shiftKey || event.altKey) return;
                 event.preventDefault();
                 navigate(entry.path);
               }}>
              <Icon name={entry.icon} />
              {entry.name}
            </a>
          ))}
        </nav>

        {/* Top right, on its own so the nav stays centred on the brand. */}
        <div className="topbar__end">
          <ModelStatus />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

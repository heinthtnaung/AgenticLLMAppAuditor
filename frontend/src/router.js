// Which page is showing, in about forty lines.
//
// No router library: the README claims React with no other runtime dependency,
// and `web/page.py`'s catch-all already answers any deep link with
// `index.html`, so real paths work without a hash. All this needs to do is read
// `location.pathname`, push a new one, and re-render when it changes.

import { useEffect, useState } from "react";

export const AUDIT = "/";
export const HISTORY = "/history";

// A run's own page. `/runs/<id>` is matched rather than parsed by a table,
// because it is the only route with a variable in it.
const RUN = /^\/runs\/([0-9a-f]{32})$/;

/** Which page a path means, and the run id when it names one. */
export function routeOf(pathname) {
  const run = RUN.exec(pathname);
  if (run) return { page: "run", runId: run[1] };
  if (pathname === HISTORY) return { page: "history", runId: null };
  return { page: "audit", runId: null };
}

/** Where one run's page lives. */
export function runPath(runId) {
  return `/runs/${runId}`;
}

/** Show another page without reloading. */
export function navigate(path) {
  if (path !== window.location.pathname) {
    window.history.pushState({}, "", path);
  }
  // Pushing state does not fire `popstate`, so the listeners below would not
  // hear a navigation this function made. One synthetic event, and every
  // subscriber is treated the same whether the browser or the page moved.
  window.dispatchEvent(new PopStateEvent("popstate"));
}

/** The current route, re-read whenever the history moves. */
export function useRoute() {
  const [pathname, setPathname] = useState(() => window.location.pathname);
  useEffect(() => {
    const reread = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", reread);
    return () => window.removeEventListener("popstate", reread);
  }, []);
  return routeOf(pathname);
}

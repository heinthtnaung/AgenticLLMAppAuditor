// The one place the UI talks to the backend.
//
// Relative paths, because FastAPI serves this page and the API from the same
// origin: `web/page.py` serves the built `dist/` alongside the routes in
// `web/run_routes.py`. Same origin means no CORS at all -- not a permissive
// CORS policy, none -- which is one fewer thing that can be got wrong on an
// endpoint with no authentication.

/** Ask for one audit. Returns the run record that will do it, not a result. */
export async function startAudit(options) {
  return ask("/api/audit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
}

/** One run as it stands: its stages so far, and its result once it finished. */
export async function fetchRun(runId) {
  return ask(`/api/runs/${runId}`);
}

/** The newest runs, and how many the store holds in total. */
export async function fetchHistory() {
  return ask("/api/runs");
}

/** Every boundary an audit can announce, so the page can show what is pending. */
export async function fetchStages() {
  return ask("/api/stages");
}

/** Which of a run's files are on disk, and how large each one is. */
export async function fetchListing(runId) {
  return ask(`/api/artifacts/${runId}`);
}

/** Where one artifact of one run is served from. A link, never a fetch. */
export function artifactUrl(runId, name) {
  return `/api/artifacts/${runId}/${name}`;
}

/** Where the whole run's artifacts are served as one archive. */
export function bundleUrl(runId) {
  return artifactUrl(runId, "artifacts.zip");
}

async function ask(path, options) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    // The backend puts the reason in `detail`; a proxy or a crash may not, so
    // the status is the fallback rather than an empty message.
    throw new Error(body?.detail ?? `the backend answered ${response.status}`);
  }
  return body;
}

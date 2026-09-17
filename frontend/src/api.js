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

/** Whether the local model server is up, and what it holds. */
export async function fetchModelStatus() {
  return ask("/api/model");
}

/** Every boundary an audit can announce, so the page can show what is pending. */
export async function fetchStages() {
  return ask("/api/stages");
}

/** Which of a run's files are on disk, and how large each one is. */
export async function fetchListing(runId) {
  return ask(`/api/artifacts/${runId}`);
}

/** The lines around the one a surface names, as the tree holds them now. */
export async function fetchSource(runId, file, line) {
  return ask(`/api/runs/${runId}/source?file=${encodeURIComponent(file)}&line=${line}`);
}

/** Every drafted grading key on disk. */
export async function fetchDrafts() {
  return ask("/api/keys");
}

/** One drafted key, with what an edit may not touch named beside it. */
export async function fetchDraft(app) {
  return ask(`/api/keys/${encodeURIComponent(app)}`);
}

/** Save a corrected draft. Refused if it would move the key's standing. */
export async function saveDraft(app, key) {
  return ask(`/api/keys/${encodeURIComponent(app)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
}

/** Record that a human checked this draft. Its own route, not part of a save.
 *
 * Correcting a title and signing off a key are different acts, and keeping them
 * apart is what lets `source` stay frozen: a save may move neither field, so the
 * pair cannot be flipped together into a key that reads as human-authored. Only
 * `verified` moves here, and the date is the server's -- sending one would let a
 * claim be backdated through the page.
 */
export async function verifyDraft(app, verifiedBy) {
  return ask(`/api/keys/${encodeURIComponent(app)}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ verified_by: verifiedBy }),
  });
}

/** One artifact's text, for rendering rather than downloading.
 *
 * `Content-Disposition: attachment` governs navigation, not `fetch`, so the
 * download route serves this too and its "every reply is an attachment" rule
 * stays exactly as absolute as it reads.
 */
export async function fetchArtifactText(runId, name) {
  const response = await fetch(artifactUrl(runId, name));
  if (!response.ok) throw new Error(`the backend answered ${response.status}`);
  return response.text();
}

/** One artifact parsed as JSON, for a document the page reads on demand. */
export async function fetchArtifactJson(runId, name) {
  return JSON.parse(await fetchArtifactText(runId, name));
}

// No `attachFile` or `uploadUrl` here. Both went with the evidence panel on
// 2026-09-17: nothing in `frontend/src` called them once it was removed, and an
// exported function with no caller is one more thing to keep true. The routes
// they spoke to are untouched and still tested -- `POST` and `GET
// /api/runs/{id}/uploads` -- so re-adding the panel means re-adding two
// four-line functions, which is cheaper than carrying them dead.

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

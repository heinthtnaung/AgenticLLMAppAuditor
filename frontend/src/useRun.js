// Watching one run from the browser.
//
// The audit is a background job on the server, so the page asks for it, gets a
// run id, and polls. Both hooks below stop polling the moment a run reaches a
// terminal status -- a finished run cannot change, so continuing to ask would
// be a request per second about a fact that is settled.

import { useEffect, useState } from "react";
import { fetchListing, fetchRun } from "./api.js";
import { RUNNING } from "./runStatus.js";

// Often enough that the stage list feels live, rarely enough that a minutes-long
// audit is not thousands of requests.
const POLL_MS = 1000;

/** One run, re-read while it is going. Returns `{ record, error }`. */
export function useRun(runId) {
  const [record, setRecord] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!runId) {
      setRecord(null);
      setError(null);
      return undefined;
    }
    // Guards every state write below: an effect cleaned up mid-request would
    // otherwise set state for a run the page has already navigated away from.
    let watching = true;
    let timer = null;

    async function read() {
      try {
        const next = await fetchRun(runId);
        if (!watching) return;
        setRecord(next);
        setError(null);
        if (next.status === RUNNING) timer = setTimeout(read, POLL_MS);
      } catch (failure) {
        if (!watching) return;
        // Kept polling on purpose: a single failed poll is usually a restart or
        // a dropped connection, and the run itself may still be going.
        setError(failure.message);
        timer = setTimeout(read, POLL_MS);
      }
    }

    read();
    return () => { watching = false; if (timer) clearTimeout(timer); };
  }, [runId]);

  return { record, error };
}

/** Which files a finished run left on disk, once there is a point in asking. */
export function useListing(runId, ready) {
  const [listing, setListing] = useState(null);

  useEffect(() => {
    if (!runId || !ready) {
      setListing(null);
      return undefined;
    }
    let watching = true;
    fetchListing(runId)
      .then((found) => { if (watching) setListing(found); })
      // A refused listing is not an error worth a banner: the panel says what
      // it knows, and the run's own status already says why the files are not
      // there. `DownloadPanel` renders null for a null listing.
      .catch(() => { if (watching) setListing(null); });
    return () => { watching = false; };
  }, [runId, ready]);

  return listing;
}

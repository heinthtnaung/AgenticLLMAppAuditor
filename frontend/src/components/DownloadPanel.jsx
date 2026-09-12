import Icon from "./Icon.jsx";
import { artifactUrl, bundleUrl } from "../api.js";
import { bytes } from "../format.js";

/** Every file this run left on disk, each as a download. */
export default function DownloadPanel({ runId, listing, current }) {
  if (!listing) return null;
  if (!listing.files.length) {
    return (
      <p className="empty">
        This run wrote no files that are still on disk. Its findings are stored
        and shown in the Findings panel; the artifacts themselves are gone.
      </p>
    );
  }
  const total = listing.files.reduce((sum, file) => sum + file.bytes, 0);
  return (
    <>
      {!current && (
        <p className="notice notice--error">
          <strong>A later run overwrote these files.</strong>
          <span className="notice__detail">
            Artifacts are keyed on the app name, not on the run, so what is on
            disk is no longer what this run produced. The downloads are refused
            rather than serving another run&rsquo;s bytes under this
            run&rsquo;s timestamp.
          </span>
        </p>
      )}
      <div className="downloads">
        {listing.files.map((file) => (
          <a
            key={file.name}
            className="download"
            href={artifactUrl(runId, file.name)}
            download={file.name}
          >
            <Icon name="download" />
            <span className="download__name mono">{file.name}</span>
            <span className="download__size">{bytes(file.bytes)}</span>
          </a>
        ))}
      </div>
      <a className="run run--secondary" href={bundleUrl(runId)} download>
        <Icon name="download" />
        Download all {listing.files.length} files ({bytes(total)})
      </a>
    </>
  );
}

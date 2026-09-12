/** Every LLM surface the extractor found, which is what the checks ran over. */
export default function SurfaceList({ surfaces }) {
  if (!surfaces.length) {
    return <p className="empty">No LLM surfaces found in this repository.</p>;
  }
  return (
    <table className="table">
      <thead>
        <tr><th>Kind</th><th>Name</th><th>Location</th><th>Language</th></tr>
      </thead>
      <tbody>
        {surfaces.map((surface) => (
          <tr key={surface.id}>
            <td><span className="tag tag--rule">{surface.kind}</span></td>
            <td className="mono">{surface.name}</td>
            <td className="mono">{surface.file}:{surface.line}</td>
            <td>{surface.language}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

import { apiGet, formatDate, type Page, type SourceFile } from "../../lib/api";
export default async function SourceFilesPage() {
  try {
    const data = await apiGet<Page<SourceFile>>(
      "/api/v1/admin/source-files?page_size=100",
    );
    return (
      <main>
        <h1>Source files</h1>
        {data.items.length === 0 ? (
          <p>No source files recorded.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>URL</th>
                  <th>Checksum</th>
                  <th>Published</th>
                  <th>Downloaded</th>
                  <th>Parser</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.source_name}</td>
                    <td>
                      <a href={item.source_url}>Source</a>
                    </td>
                    <td>{item.checksum_sha256}</td>
                    <td>{formatDate(item.source_published_at)}</td>
                    <td>{formatDate(item.downloaded_at)}</td>
                    <td>{item.parser_version}</td>
                    <td>{item.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    );
  } catch (error) {
    return (
      <main>
        <h1>Source files</h1>
        <p className="error" role="alert">
          Unable to load source files:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}

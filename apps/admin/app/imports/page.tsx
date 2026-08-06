import { apiGet, formatDate, type ImportRun, type Page } from "../../lib/api";
export default async function ImportsPage() {
  try {
    const data = await apiGet<Page<ImportRun>>(
      "/api/v1/admin/import-runs?page_size=100",
    );
    return (
      <main>
        <h1>Imports</h1>
        {data.items.length === 0 ? (
          <p>No imports recorded.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Importer</th>
                  <th>Status</th>
                  <th>Source</th>
                  <th>Started</th>
                  <th>Finished</th>
                  <th>Read</th>
                  <th>Inserted</th>
                  <th>Updated</th>
                  <th>Rejected</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.importer_name}</td>
                    <td>{item.status}</td>
                    <td>{item.source_name}</td>
                    <td>{formatDate(item.started_at)}</td>
                    <td>{formatDate(item.finished_at)}</td>
                    <td>{item.rows_read}</td>
                    <td>{item.rows_inserted}</td>
                    <td>{item.rows_updated}</td>
                    <td>{item.rows_rejected}</td>
                    <td>{item.error_summary ?? "—"}</td>
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
        <h1>Imports</h1>
        <p className="error" role="alert">
          Unable to load imports:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}

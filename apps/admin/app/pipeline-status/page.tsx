import { apiGet, Page, Pipeline, formatDate } from "../../lib/api";
export default async function Pipelines() {
  try {
    const data = await apiGet<Page<Pipeline>>(
      "/api/v1/admin/pipeline-status?page_size=100",
    );
    return (
      <main>
        <p className="eyebrow">INTERNAL ONLY</p>
        <h1>Pipeline status</h1>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Importer</th>
                <th>Status</th>
                <th>Freshness</th>
                <th>Last success</th>
                <th>Records</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((i) => (
                <tr key={i.id}>
                  <td>{i.importer_name}</td>
                  <td>{i.current_status}</td>
                  <td>{i.freshness_status}</td>
                  <td>{formatDate(i.latest_success_at)}</td>
                  <td>{i.records_last_imported ?? "—"}</td>
                  <td>{i.error_summary ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    );
  } catch {
    return (
      <main>
        <h1>Pipeline status</h1>
        <p className="error">Pipeline API unavailable.</p>
      </main>
    );
  }
}

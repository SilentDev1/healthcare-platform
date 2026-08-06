import { apiGet, HealthEvaluation, Page } from "../../lib/api";
export default async function Health() {
  try {
    const data = await apiGet<Page<HealthEvaluation>>(
      "/api/v1/admin/data-health?page_size=100",
    );
    return (
      <main>
        <p className="eyebrow">INTERNAL ONLY</p>
        <h1>Data health</h1>
        {data.items.length === 0 && (
          <p>No evaluations yet. Run make evaluate-data-health.</p>
        )}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rule</th>
                <th>Severity</th>
                <th>Entity</th>
                <th>Status</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((i) => (
                <tr key={i.id}>
                  <td>{i.rule_name}</td>
                  <td>{i.severity}</td>
                  <td>{i.entity_type}</td>
                  <td>{i.status}</td>
                  <td>{i.message}</td>
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
        <h1>Data health</h1>
        <p className="error">Data-health API unavailable.</p>
      </main>
    );
  }
}

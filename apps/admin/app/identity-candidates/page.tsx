import { apiGet, IdentityCandidate, Page } from "../../lib/api";
export default async function Candidates() {
  try {
    const data = await apiGet<Page<IdentityCandidate>>(
      "/api/v1/admin/identity-candidates?page_size=100",
    );
    return (
      <main>
        <p className="eyebrow">INTERNAL ONLY · READ-ONLY REVIEW</p>
        <h1>Identity candidates</h1>
        {data.items.length === 0 && <p>No pending candidates.</p>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Supplied identity</th>
                <th>Method</th>
                <th>Score</th>
                <th>Status</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((i) => (
                <tr key={i.id}>
                  <td>
                    {i.supplied_name}
                    <br />
                    <small>{JSON.stringify(i.supplied_identifiers)}</small>
                  </td>
                  <td>{i.deterministic_method}</td>
                  <td>{i.score}</td>
                  <td>{i.status}</td>
                  <td>{i.reason}</td>
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
        <h1>Identity candidates</h1>
        <p className="error">Identity API unavailable.</p>
      </main>
    );
  }
}

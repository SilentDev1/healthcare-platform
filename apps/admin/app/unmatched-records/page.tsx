import { apiGet, type Page, type Unmatched } from "../../lib/api";
export default async function UnmatchedPage() {
  try {
    const data = await apiGet<Page<Unmatched>>(
      "/api/v1/admin/unmatched-records?page_size=100",
    );
    return (
      <main>
        <h1>Unmatched records</h1>
        {data.items.length === 0 ? (
          <p>No unmatched source records.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source identifier</th>
                  <th>Supplied CCN</th>
                  <th>Facility name</th>
                  <th>Reason</th>
                  <th>Source file</th>
                  <th>Review status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.source_record_identifier}</td>
                    <td>{item.supplied_cms_certification_number ?? "—"}</td>
                    <td>{item.supplied_facility_name ?? "—"}</td>
                    <td>{item.reason_unmatched}</td>
                    <td>{item.source_file_id}</td>
                    <td>{item.review_status}</td>
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
        <h1>Unmatched records</h1>
        <p className="error" role="alert">
          Unable to load unmatched records:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}

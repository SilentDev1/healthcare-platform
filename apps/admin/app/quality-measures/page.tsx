import { apiGet, type Page, type QualityMeasure } from "../../lib/api";
export default async function MeasuresPage() {
  try {
    const data = await apiGet<Page<QualityMeasure>>(
      "/api/v1/quality-measures?page_size=100",
    );
    return (
      <main>
        <h1>Quality measures</h1>
        {data.items.length === 0 ? (
          <p>No quality measures available.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>CMS ID</th>
                  <th>Measure</th>
                  <th>Category</th>
                  <th>Unit</th>
                  <th>Directionality</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.cms_measure_id}</td>
                    <td>{item.measure_name}</td>
                    <td>{item.category}</td>
                    <td>{item.unit ?? "—"}</td>
                    <td>{item.directionality}</td>
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
        <h1>Quality measures</h1>
        <p className="error" role="alert">
          Unable to load quality measures:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}

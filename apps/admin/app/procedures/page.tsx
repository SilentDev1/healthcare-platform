import { apiGet, Page, Procedure } from "../../lib/api";
export default async function Procedures() {
  try {
    const data = await apiGet<Page<Procedure>>(
      "/api/v1/procedures?page_size=100",
    );
    return (
      <main>
        <p className="eyebrow">INTERNAL ONLY</p>
        <h1>Procedure catalog</h1>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>Setting</th>
                <th>Aliases</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((i) => (
                <tr key={i.id}>
                  <td>{i.consumer_name}</td>
                  <td>{i.category.name}</td>
                  <td>{i.service_setting}</td>
                  <td>{i.aliases.join(", ")}</td>
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
        <h1>Procedure catalog</h1>
        <p className="error">Catalog API unavailable.</p>
      </main>
    );
  }
}

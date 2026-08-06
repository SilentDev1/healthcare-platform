import Link from "next/link";
import {
  apiGet,
  formatDate,
  type AdminFacility,
  type Page,
} from "../../lib/api";

export default async function FacilitiesPage() {
  try {
    const data = await apiGet<Page<AdminFacility>>(
      "/api/v1/admin/facilities?state=NH&page_size=100",
    );
    return (
      <main>
        <h1>Facilities</h1>
        <p>{data.total} New Hampshire facilities</p>
        {data.items.length === 0 ? (
          <p>No facilities found.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <caption className="muted">
                Facility identity, provenance, and quality coverage
              </caption>
              <thead>
                <tr>
                  <th>Facility</th>
                  <th>Location</th>
                  <th>CCN</th>
                  <th>Type</th>
                  <th>Active</th>
                  <th>Latest source</th>
                  <th>Quality measures</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link href={`/facilities/${item.id}`}>
                        {item.display_name}
                      </Link>
                    </td>
                    <td>
                      {item.city}, {item.state}
                    </td>
                    <td>{item.cms_certification_number}</td>
                    <td>{item.facility_type ?? "—"}</td>
                    <td>{item.active ? "Yes" : "No"}</td>
                    <td>{item.latest_source_name}</td>
                    <td>{item.quality_measure_count}</td>
                    <td>{formatDate(item.updated_at)}</td>
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
        <h1>Facilities</h1>
        <p className="error" role="alert">
          Unable to load facilities:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}

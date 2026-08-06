import { apiGet, formatDate, type SourceFile } from "../../../lib/api";

interface Location {
  address_line_1: string;
  city: string;
  state: string;
  postal_code: string;
  county: string | null;
}
interface Facility {
  id: string;
  display_name: string;
  legal_name: string;
  cms_certification_number: string;
  facility_type: string | null;
  ownership_type: string | null;
  phone: string | null;
  website_url: string | null;
  active: boolean;
  updated_at: string;
  locations: Location[];
}
interface Detail {
  facility: Facility;
  latest_source: SourceFile;
  import_run_count: number;
  raw_source_observation_count: number;
  quality_measure_count: number;
}
interface Quality {
  items: Array<{
    id: string;
    measure_name: string;
    category: string;
    score: string | null;
    footnote_code: string | null;
    reporting_period_end: string | null;
  }>;
  total: number;
}

export default async function FacilityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  try {
    const [detail, quality] = await Promise.all([
      apiGet<Detail>(`/api/v1/admin/facilities/${id}`),
      apiGet<Quality>(`/api/v1/admin/facilities/${id}/quality`),
    ]);
    const f = detail.facility;
    const location = f.locations[0];
    return (
      <main>
        <h1>{f.display_name}</h1>
        <div className="grid">
          <section className="panel">
            <h2>Identity</h2>
            <dl>
              <dt>Legal name</dt>
              <dd>{f.legal_name}</dd>
              <dt>CMS certification number</dt>
              <dd>{f.cms_certification_number}</dd>
              <dt>Type</dt>
              <dd>{f.facility_type ?? "—"}</dd>
              <dt>Ownership</dt>
              <dd>{f.ownership_type ?? "—"}</dd>
              <dt>Status</dt>
              <dd>{f.active ? "Active" : "Inactive"}</dd>
            </dl>
          </section>
          <section className="panel">
            <h2>Location</h2>
            {location ? (
              <address>
                {location.address_line_1}
                <br />
                {location.city}, {location.state} {location.postal_code}
              </address>
            ) : (
              <p>No location available.</p>
            )}
          </section>
          <section className="panel">
            <h2>Provenance</h2>
            <p>{detail.latest_source.source_name}</p>
            <p className="muted">
              Checksum {detail.latest_source.checksum_sha256}
            </p>
            <p>Downloaded {formatDate(detail.latest_source.downloaded_at)}</p>
            <p>
              {detail.import_run_count} quality imports ·{" "}
              {detail.raw_source_observation_count} raw observations
            </p>
          </section>
        </div>
        <h2>Quality measures ({detail.quality_measure_count})</h2>
        {quality.items.length === 0 ? (
          <p>No quality data available.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Measure</th>
                  <th>Category</th>
                  <th>Value</th>
                  <th>Footnote</th>
                  <th>Period end</th>
                </tr>
              </thead>
              <tbody>
                {quality.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.measure_name}</td>
                    <td>{item.category}</td>
                    <td>{item.score ?? "Not available"}</td>
                    <td>{item.footnote_code ?? "—"}</td>
                    <td>{item.reporting_period_end ?? "—"}</td>
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
        <h1>Facility detail</h1>
        <p className="error" role="alert">
          Unable to load facility:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}

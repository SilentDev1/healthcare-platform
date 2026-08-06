import { apiGet, formatDate } from "../lib/api";

interface Dashboard {
  total_facilities: number;
  nh_facilities: number;
  latest_import_status: string | null;
  failed_import_count: number;
  unmatched_record_count: number;
  facilities_with_quality: number;
  facilities_without_quality: number;
  latest_source_downloaded_at: string | null;
}

export default async function AdminHome() {
  try {
    const data = await apiGet<Dashboard>("/api/v1/admin/dashboard");
    const metrics = [
      ["Total facilities", data.total_facilities],
      ["NH facilities", data.nh_facilities],
      ["Latest import", data.latest_import_status ?? "None"],
      ["Failed imports", data.failed_import_count],
      ["Unmatched records", data.unmatched_record_count],
      ["With quality data", data.facilities_with_quality],
      ["Without quality data", data.facilities_without_quality],
    ];
    return (
      <main>
        <h1>Dashboard</h1>
        <p className="muted">
          Latest source downloaded{" "}
          {formatDate(data.latest_source_downloaded_at)}
        </p>
        <section className="metrics" aria-label="Operational metrics">
          {metrics.map(([label, value]) => (
            <article className="metric" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </article>
          ))}
        </section>
      </main>
    );
  } catch (error) {
    return (
      <main>
        <h1>Dashboard</h1>
        <p className="error" role="alert">
          Unable to load dashboard:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}

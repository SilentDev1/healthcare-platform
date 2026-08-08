import Link from "next/link";
import { apiGet, formatDate, type StatewideScorecard } from "../lib/api";

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

    let scorecard: StatewideScorecard | null = null;
    try {
      scorecard = await apiGet<StatewideScorecard>(
        "/api/v1/pricing/scorecard",
      );
    } catch {
      // Scorecard may not be available yet
    }

    const metrics: [string, string | number][] = [
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

        {/* Statewide readiness score */}
        {scorecard && (
          <section className="panel" style={{ marginBottom: "1.5rem" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h2 style={{ margin: 0 }}>Statewide readiness</h2>
              <span
                style={{
                  background: scorecard.meets_target ? "#087f5b" : "#e67700",
                  color: "white",
                  padding: "0.3rem 0.8rem",
                  borderRadius: "0.3rem",
                  fontWeight: 700,
                  fontSize: "1.2rem",
                }}
              >
                {scorecard.overall_readiness}%
              </span>
            </div>
            <div
              className="metrics"
              style={{ marginTop: "1rem" }}
              aria-label="Component scores"
            >
              {Object.entries(scorecard.component_scores).map(
                ([name, score]) => (
                  <article className="metric" key={name}>
                    <span style={{ textTransform: "capitalize" }}>{name}</span>
                    <strong>{score}%</strong>
                  </article>
                ),
              )}
            </div>
            <Link
              href="/scorecard"
              style={{
                display: "inline-block",
                marginTop: "0.75rem",
                fontSize: "0.9rem",
              }}
            >
              View full scorecard →
            </Link>
          </section>
        )}

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

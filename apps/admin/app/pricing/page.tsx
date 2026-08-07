import Link from "next/link";
import { apiGet, type PricingCoverage } from "../../lib/api";

const sections = [
  ["sources", "Price sources"],
  ["source-discovery-runs", "Discovery runs"],
  ["import-runs", "Downloads and imports"],
  ["records", "Normalized records"],
  ["payers", "Payer normalization"],
  ["plans", "Plan normalization"],
  ["procedure-candidates", "Procedure mapping review"],
  ["anomalies", "Pricing anomalies"],
  ["facility-procedure-summaries", "Facility procedure summaries"],
  ["source-discovery-observations", "Parser and discovery review"],
];

export default async function PricingDashboard() {
  try {
    const coverage = await apiGet<PricingCoverage>("/api/v1/pricing/coverage");
    const metrics = [
      ["NH facilities", coverage.nh_facilities],
      ["Sources discovered", coverage.facilities_with_sources],
      ["Files downloaded", coverage.facilities_with_downloads],
      ["Facilities parsed", coverage.facilities_with_parsed_records],
      ["Facilities publishable", coverage.facilities_with_publishable_prices],
      ["Procedures publishable", coverage.publishable_procedures],
    ];
    return (
      <main>
        <p className="eyebrow">INTERNAL ONLY</p>
        <h1>Pricing operations</h1>
        <section className="metrics" aria-label="Pricing coverage">
          {metrics.map(([label, value]) => (
            <article className="metric" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </article>
          ))}
        </section>
        <h2>Review queues</h2>
        <ul>
          {sections.map(([path, label]) => (
            <li key={path}>
              <Link href={`/pricing/${path}`}>{label}</Link>
            </li>
          ))}
        </ul>
        <p className="muted">
          Raw source observations are immutable. Only publishable, reviewed
          mappings reach the public API.
        </p>
      </main>
    );
  } catch (error) {
    return (
      <main>
        <h1>Pricing operations</h1>
        <p className="error" role="alert">
          Unable to load pricing:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}

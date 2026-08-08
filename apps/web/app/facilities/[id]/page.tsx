import Link from "next/link";
import {
  apiGet,
  type Facility,
  type PricePage,
  type PricingHealth,
  type QualityPage,
} from "../../../lib/api";

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? "#087f5b" : score >= 50 ? "#e67700" : "#c92a2a";
  return (
    <span
      style={{
        background: color,
        color: "white",
        padding: "0.25rem 0.6rem",
        borderRadius: "0.3rem",
        fontWeight: 700,
        fontSize: "0.9rem",
      }}
    >
      {Math.round(score)}%
    </span>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 80 ? "#087f5b" : value >= 50 ? "#e67700" : "#c92a2a";
  return (
    <div style={{ marginBottom: "0.4rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.85rem",
          color: "#526862",
        }}
      >
        <span>{label}</span>
        <span>{Math.round(value)}%</span>
      </div>
      <div
        style={{
          background: "#e8efed",
          borderRadius: "0.25rem",
          height: "0.5rem",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            background: color,
            width: `${Math.max(2, value)}%`,
            height: "100%",
            borderRadius: "0.25rem",
          }}
        />
      </div>
    </div>
  );
}

export default async function FacilityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  try {
    const [facility, quality, prices] = await Promise.all([
      apiGet<Facility>(`/api/v1/facilities/${id}`),
      apiGet<QualityPage>(`/api/v1/facilities/${id}/quality?page_size=100`),
      apiGet<PricePage>(`/api/v1/facilities/${id}/prices?page_size=10`),
    ]);

    let pricingHealth: PricingHealth | null = null;
    try {
      pricingHealth = await apiGet<PricingHealth>(
        `/api/v1/facilities/${id}/pricing-health`,
      );
    } catch {
      // Pricing health may not be available for all facilities
    }

    const location = facility.locations[0];
    const rating = quality.items.find(
      (item) => item.cms_measure_id === "OVERALL_RATING",
    );
    return (
      <main>
        <Link href="/">← All facilities</Link>
        <p className="eyebrow">NEW HAMPSHIRE FACILITY</p>
        <h1>{facility.display_name}</h1>
        {location && (
          <p>
            {location.address_line_1}, {location.city}, {location.state}{" "}
            {location.postal_code}
          </p>
        )}

        {pricingHealth && (
          <section className="card" style={{ marginBottom: "1.5rem" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "1rem",
              }}
            >
              <h2 style={{ margin: 0 }}>Pricing data health</h2>
              <ScoreBadge score={pricingHealth.overall_score} />
            </div>
            <ScoreBar
              label="Source discovery"
              value={pricingHealth.source_discovery_score}
            />
            <ScoreBar label="Download" value={pricingHealth.download_score} />
            <ScoreBar label="Parse" value={pricingHealth.parse_score} />
            <ScoreBar label="Mapping" value={pricingHealth.mapping_score} />
            <ScoreBar
              label="Payer normalization"
              value={pricingHealth.payer_normalization_score}
            />
            <ScoreBar label="Anomaly" value={pricingHealth.anomaly_score} />
            <ScoreBar label="Freshness" value={pricingHealth.freshness_score} />
            <ScoreBar
              label="Price coverage"
              value={pricingHealth.price_coverage_score}
            />
            <p
              style={{
                fontSize: "0.8rem",
                color: "#526862",
                margin: "0.5rem 0 0",
              }}
            >
              Last evaluated{" "}
              {new Date(pricingHealth.calculated_at).toLocaleDateString(
                "en-US",
              )}
            </p>
          </section>
        )}

        <section className="rating" aria-label="Overall CMS rating">
          <h2>Overall CMS rating</h2>
          <strong>
            {rating?.score ?? "Not available"}
            {rating?.score ? " out of 5" : ""}
          </strong>
          {rating?.footnote_code && <p>CMS footnote: {rating.footnote_code}</p>}
        </section>
        <h2>Available quality measures</h2>
        {quality.items.length === 0 ? (
          <p>
            No CMS quality measures are currently available for this facility.
          </p>
        ) : (
          <ul className="measures">
            {quality.items.map((item) => (
              <li key={item.id}>
                <span>{item.measure_name}</span>
                <strong>{item.score ?? "Not available"}</strong>
              </li>
            ))}
          </ul>
        )}
        <h2>Published prices</h2>
        {!prices?.items?.length ? (
          <p>No reviewed, publishable prices are currently available.</p>
        ) : (
          <ul className="measures">
            {prices.items.map((item) => (
              <li key={item.id}>
                <Link href={`/procedures/${item.procedure_slug}/prices`}>
                  {item.procedure_name}
                </Link>
                <strong>
                  {item.cash_price_min
                    ? `$${Number(item.cash_price_min).toLocaleString()}`
                    : "Negotiated rate available"}
                </strong>
              </li>
            ))}
          </ul>
        )}
        <p>
          Hospital transparency prices may not equal your final bill. Other
          professional and ancillary charges may be separate; verify network
          status and benefits.
        </p>
        <p className="source">
          Source: Centers for Medicare &amp; Medicaid Services. Facility record
          last updated{" "}
          {new Date(facility.updated_at).toLocaleDateString("en-US")}.
        </p>
      </main>
    );
  } catch (error) {
    return (
      <main>
        <h1>Facility</h1>
        <p className="error" role="alert">
          Unable to load this facility:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}

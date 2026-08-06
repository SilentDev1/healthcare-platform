import Link from "next/link";
import { apiGet, type Facility, type QualityPage } from "../../../lib/api";

export default async function FacilityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  try {
    const [facility, quality] = await Promise.all([
      apiGet<Facility>(`/api/v1/facilities/${id}`),
      apiGet<QualityPage>(`/api/v1/facilities/${id}/quality?page_size=100`),
    ]);
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
        <p>Pricing comparison is coming later.</p>
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

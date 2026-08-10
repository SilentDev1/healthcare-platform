import Link from "next/link";
import {
  apiGet,
  type Facility,
  type PricePage,
  type QualityPage,
} from "../../../lib/api";
import {
  CoverageNotice,
  EmptyState,
  PriceRange,
  PricingDisclaimer,
  QualityRating,
  SourceAttribution,
} from "../../components/ui";
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
      apiGet<PricePage>(`/api/v1/facilities/${id}/prices?page_size=25`),
    ]);
    const location = facility.locations[0];
    const overall = quality.items.find(
      (q) => q.cms_measure_id === "OVERALL_RATING",
    );
    const groups = Object.groupBy(quality.items, (q) => q.category);
    return (
      <main>
        <nav className="breadcrumbs">
          <Link href="/">Home</Link>
          <span>/</span>
          <Link href="/hospitals">Hospitals</Link>
          <span>/</span>
          <span>{facility.display_name}</span>
        </nav>
        <div className="page-heading">
          <p className="eyebrow">{facility.facility_type ?? "Hospital"}</p>
          <h1>{facility.display_name}</h1>
          <p className="lede">
            {location
              ? `${location.city}, ${location.state}`
              : "Location not published"}{" "}
            · <QualityRating value={overall?.score} />
          </p>
        </div>
        <div className="toolbar" aria-label="Page sections">
          <div className="toolbar-group">
            <a href="#overview">Overview</a>
            <a href="#prices">Prices</a>
            <a href="#quality">Quality</a>
            <a href="#sources">Data sources</a>
          </div>
        </div>
        <section id="overview" className="section" style={{ paddingInline: 0 }}>
          <div className="section-heading">
            <p className="eyebrow">Overview</p>
            <h2>Facility information</h2>
          </div>
          <div className="feature-grid">
            <article className="card">
              <h3>Address</h3>
              <p>
                {location
                  ? `${location.address_line_1}, ${location.city}, ${location.state} ${location.postal_code}`
                  : "Not available"}
              </p>
            </article>
            <article className="card">
              <h3>Contact</h3>
              <p>{facility.phone ?? "Phone not available"}</p>
              {facility.website_url && (
                <a href={facility.website_url}>Facility website</a>
              )}
            </article>
            <article className="card">
              <h3>Facility details</h3>
              <p>
                {facility.facility_type ?? "Type not listed"}
                <br />
                {facility.ownership_type ?? "Ownership not listed"}
              </p>
            </article>
          </div>
        </section>
        <section id="prices" className="section" style={{ paddingInline: 0 }}>
          <div className="section-heading">
            <p className="eyebrow">Published prices</p>
            <h2>Available procedures</h2>
          </div>
          {prices.items.length ? (
            <>
              <CoverageNotice>
                {prices.total} publishable procedure price summaries are
                currently available for this facility.
              </CoverageNotice>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Procedure</th>
                      <th scope="col">Cash price</th>
                      <th scope="col">Negotiated range</th>
                      <th scope="col">Setting</th>
                      <th scope="col">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prices.items.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <Link href={`/procedures/${p.procedure_slug}/prices`}>
                            {p.procedure_name}
                          </Link>
                        </td>
                        <td>
                          <PriceRange
                            min={p.cash_price_min}
                            max={p.cash_price_max}
                          />
                        </td>
                        <td>
                          <PriceRange
                            min={p.negotiated_price_min}
                            max={p.negotiated_price_max}
                          />
                        </td>
                        <td>{p.service_setting?.replaceAll("_", " ")}</td>
                        <td>
                          <SourceAttribution
                            updated={p.last_updated}
                            url={p.source_url}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <EmptyState title="Pricing data is not currently available for this facility">
              Hospital transparency data may still be processing or may not meet
              publication safety rules. The facility remains listed so the
              coverage gap is visible.
            </EmptyState>
          )}
        </section>
        <section id="quality" className="section" style={{ paddingInline: 0 }}>
          <div className="section-heading">
            <p className="eyebrow">CMS quality</p>
            <h2>Quality measures</h2>
            <p>
              These measures provide context and should not be interpreted as a
              complete judgment of care.
            </p>
          </div>
          <article className="rating">
            <h3>Overall rating</h3>
            <QualityRating value={overall?.score} />
          </article>
          {quality.items.length ? (
            <div className="cards">
              {Object.entries(groups).map(([category, values]) => (
                <article className="card" key={category}>
                  <h3>{category.replaceAll("_", " ")}</h3>
                  <ul className="measures">
                    {values?.slice(0, 5).map((q) => (
                      <li key={q.id}>
                        <span>{q.measure_name}</span>
                        <strong>{q.score ?? "Not available"}</strong>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="CMS quality measures are unavailable">
              No quality records are currently available for this facility.
            </EmptyState>
          )}
        </section>
        <section id="sources" className="section" style={{ paddingInline: 0 }}>
          <div className="section-heading">
            <p className="eyebrow">Data sources</p>
            <h2>Where this information comes from</h2>
          </div>
          <SourceAttribution quality updated={facility.updated_at} />
          {prices.items[0] && (
            <SourceAttribution
              updated={prices.items[0].last_updated}
              url={prices.items[0].source_url}
            />
          )}
        </section>
        <PricingDisclaimer />
      </main>
    );
  } catch {
    return (
      <main>
        <h1>Hospital information unavailable</h1>
        <p className="error" role="alert">
          We couldn’t load this facility right now.
        </p>
      </main>
    );
  }
}

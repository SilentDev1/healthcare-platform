import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  apiGet,
  ApiError,
  type Facility,
  type FacilityProcedureOverview,
  type QualityPage,
} from "../../../lib/api";
import {
  CoverageNotice,
  EmptyState,
  PricingDisclaimer,
  QualityRating,
  SourceAttribution,
} from "../../components/ui";
import { FacilityPrices } from "../../components/FacilityPrices";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const facility = await apiGet<Facility>(`/api/v1/facilities/${id}`);
    const location = facility.locations[0];
    return {
      title: facility.display_name,
      description: `View published prices, service locations, and CMS quality information for ${facility.display_name}${location ? ` in ${location.city}, ${location.state}` : ""}.`,
      alternates: { canonical: `/hospitals/${facility.id}` },
    };
  } catch {
    return { title: "Hospital information" };
  }
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
      apiGet<FacilityProcedureOverview>(
        `/api/v1/facilities/${id}/procedure-overview`,
      ),
    ]);
    const location = facility.locations[0];
    const overall = quality.items.find(
      (q) => q.cms_measure_id === "OVERALL_RATING",
    );
    const groups = Object.groupBy(quality.items, (q) => q.category);
    const priceSources = Array.from(
      new Map(
        prices.items.map((price) => [
          price.source_url,
          {
            url: price.source_url,
            updated: price.latest_updated,
            context: price.location_name ?? price.city,
          },
        ]),
      ).values(),
    );
    const structuredData = {
      "@context": "https://schema.org",
      "@type": "Hospital",
      name: facility.display_name,
      telephone: facility.phone ?? undefined,
      url: facility.website_url ?? undefined,
      address: location
        ? {
            "@type": "PostalAddress",
            streetAddress: location.address_line_1,
            addressLocality: location.city,
            addressRegion: location.state,
            postalCode: location.postal_code,
          }
        : undefined,
    };
    return (
      <main>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
        />
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
              <h3>Service locations</h3>
              {facility.locations.length ? (
                <ul className="plain-list">
                  {facility.locations.map((item) => (
                    <li key={item.id}>
                      {item.location_name && (
                        <strong>{item.location_name}: </strong>
                      )}
                      {item.address_line_1}, {item.city}, {item.state}{" "}
                      {item.postal_code}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Not available</p>
              )}
            </article>
            <article className="card">
              <h3>Contact</h3>
              <p>
                {facility.phone ? (
                  <a href={`tel:${facility.phone.replace(/[^\d+]/g, "")}`}>
                    Call {facility.phone}
                  </a>
                ) : (
                  "Phone not available"
                )}
              </p>
              {facility.website_url && (
                <a href={facility.website_url} target="_blank" rel="noreferrer">
                  Visit official facility website (external)
                </a>
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
                Published pricing is currently available for{" "}
                {prices.procedure_count} procedure
                {prices.procedure_count === 1 ? "" : "s"} at this facility.
              </CoverageNotice>
              <FacilityPrices items={prices.items} />
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
          <SourceAttribution
            quality
            updated={overall?.reporting_period_end ?? undefined}
          />
          {priceSources.map((source) => (
            <SourceAttribution
              key={source.url}
              updated={source.updated}
              url={source.url}
              context={source.context}
            />
          ))}
        </section>
        <PricingDisclaimer />
      </main>
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
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

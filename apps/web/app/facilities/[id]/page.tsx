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
import { FacilityImage } from "../../components/FacilityImage";
import { localePath } from "../../../lib/i18n";
import { requestLocale, requestMessages } from "../../../lib/i18n-server";

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
  const locale = await requestLocale();
  const t = await requestMessages();
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
        <nav className="breadcrumbs" aria-label={t.breadcrumb}>
          <Link href={localePath(locale, "/")}>{t.home}</Link>
          <span>/</span>
          <Link href={localePath(locale, "/hospitals")}>{t.hospitals}</Link>
          <span>/</span>
          <span>{facility.display_name}</span>
        </nav>
        {facility.image_url && (
          <FacilityImage
            name={facility.display_name}
            imageUrl={facility.image_url}
            imageAlt={
              facility.image_alt ??
              t.imageAltPhotoOf.replace("{hospital}", facility.display_name)
            }
            attribution={facility.image_attribution ?? undefined}
            variant="card"
            className="facility-hero-media"
          />
        )}
        <div className="page-heading">
          <p className="eyebrow">
            {facility.facility_type ?? t.facilityTypeHospital}
          </p>
          <h1>{facility.display_name}</h1>
          <p className="lede">
            {location
              ? `${location.city}, ${location.state}`
              : t.hospLocationNotPublished}{" "}
            · <QualityRating value={overall?.score} messages={t} />
          </p>
        </div>
        <div className="toolbar" aria-label={t.hospPageSections}>
          <div className="toolbar-group">
            <a href="#overview">{t.hospOverviewNav}</a>
            <a href="#prices">{t.hospPricesNav}</a>
            <a href="#quality">{t.hospQualityNav}</a>
            <a href="#sources">{t.hospDataSourcesNav}</a>
          </div>
        </div>
        <section id="overview" className="section" style={{ paddingInline: 0 }}>
          <div className="section-heading">
            <p className="eyebrow">{t.hospOverviewNav}</p>
            <h2>{t.hospFacilityInformation}</h2>
          </div>
          <div className="feature-grid">
            <article className="card">
              <h3>{t.hospServiceLocations}</h3>
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
                <p>{t.notAvailable}</p>
              )}
            </article>
            <article className="card">
              <h3>{t.hospContact}</h3>
              <p>
                {facility.phone ? (
                  <a href={`tel:${facility.phone.replace(/[^\d+]/g, "")}`}>
                    {t.hospCall.replace("{phone}", facility.phone)}
                  </a>
                ) : (
                  t.hospPhoneNotAvailable
                )}
              </p>
              {facility.website_url && (
                <a href={facility.website_url} target="_blank" rel="noreferrer">
                  {t.hospVisitWebsite}
                </a>
              )}
            </article>
            <article className="card">
              <h3>{t.hospFacilityDetails}</h3>
              <p>
                {facility.facility_type ?? t.hospTypeNotListed}
                <br />
                {facility.ownership_type ?? t.hospOwnershipNotListed}
              </p>
            </article>
          </div>
        </section>
        <section id="prices" className="section" style={{ paddingInline: 0 }}>
          <div className="section-heading">
            <p className="eyebrow">{t.hospPublishedPrices}</p>
            <h2>{t.hospAvailableProcedures}</h2>
          </div>
          {prices.items.length ? (
            <>
              <CoverageNotice messages={t}>
                {(prices.procedure_count === 1
                  ? t.hospPricingCountOne
                  : t.hospPricingCountOther
                ).replace("{count}", String(prices.procedure_count))}
              </CoverageNotice>
              <FacilityPrices items={prices.items} messages={t} locale={locale} />
            </>
          ) : (
            <EmptyState title={t.hospNoPricingTitle}>
              {t.hospNoPricingBody}
            </EmptyState>
          )}
        </section>
        <section id="quality" className="section" style={{ paddingInline: 0 }}>
          <div className="section-heading">
            <p className="eyebrow">{t.hospCmsQuality}</p>
            <h2>{t.hospQualityMeasures}</h2>
            <p>{t.hospQualityMeasuresIntro}</p>
          </div>
          <article className="rating">
            <h3>{t.hospOverallRating}</h3>
            <QualityRating value={overall?.score} messages={t} />
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
                        <strong>{q.score ?? t.notAvailable}</strong>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title={t.hospNoQualityTitle}>
              {t.hospNoQualityBody}
            </EmptyState>
          )}
        </section>
        <section id="sources" className="section" style={{ paddingInline: 0 }}>
          <div className="section-heading">
            <p className="eyebrow">{t.hospDataSourcesNav}</p>
            <h2>{t.hospWhereInfoComesFrom}</h2>
          </div>
          <SourceAttribution
            quality
            updated={overall?.reporting_period_end ?? undefined}
            messages={t}
          />
          {priceSources.map((source) => (
            <SourceAttribution
              key={source.url}
              updated={source.updated}
              url={source.url}
              context={source.context}
              messages={t}
            />
          ))}
        </section>
        <PricingDisclaimer messages={t} />
      </main>
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return (
      <main>
        <h1>{t.hospInfoUnavailableTitle}</h1>
        <p className="error" role="alert">
          {t.hospInfoUnavailableBody}
        </p>
      </main>
    );
  }
}

import { notFound } from "next/navigation";
import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, Procedure, type ProcedureComparison } from "../../../lib/api";
import {
  CoverageNotice,
  PriceRange,
  PricingDisclaimer,
  SourceAttribution,
} from "../../components/ui";
import { launchRegion } from "../../../lib/brand";
import { localePath } from "../../../lib/i18n";
import { requestLocale, requestMessages } from "../../../lib/i18n-server";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const item = await apiGet<Procedure>(
      `/api/v1/procedures/${encodeURIComponent(slug)}`,
    );
    return {
      title: `${item.consumer_name} prices`,
      description: `Learn about ${item.consumer_name.toLowerCase()} and compare available hospital-published prices in ${launchRegion.name}.`,
      alternates: { canonical: `/procedures/${item.slug}` },
    };
  } catch {
    return { title: "Procedure information" };
  }
}

export default async function ProcedureDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const locale = await requestLocale();
  const t = await requestMessages();
  let item: Procedure;
  let comparison: ProcedureComparison | null = null;
  try {
    item = await apiGet<Procedure>(
      `/api/v1/procedures/${encodeURIComponent(slug)}`,
    );
  } catch {
    notFound();
  }
  try {
    comparison = await apiGet<ProcedureComparison>(
      `/api/v1/procedures/${encodeURIComponent(slug)}/comparison?state=${launchRegion.state}`,
    );
  } catch {}
  const priced =
    comparison?.items.filter((price) => price.price_available) ?? [];
  const cashMins = priced
    .map((price) => price.cash_price_min)
    .filter((value): value is string => value !== null);
  const cashMaxes = priced
    .map((price) => price.cash_price_max)
    .filter((value): value is string => value !== null);
  const locationsWithInsuranceRates = priced.filter(
    (price) => (price.distinct_payer_count ?? 0) > 0,
  ).length;
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "MedicalProcedure",
    name: item.consumer_name,
    description: item.short_description,
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
        <Link href={localePath(locale, "/procedures")}>{t.procedures}</Link>
        <span>/</span>
        <span>{item.consumer_name}</span>
      </nav>
      <p className="eyebrow">{item.category.name}</p>
      <h1>{item.consumer_name}</h1>
      <p className="lede">{item.long_description}</p>
      <div className="feature-grid">
        <section className="card">
          <h2>{t.procTypicalSetting}</h2>
          <p>{item.service_setting.replaceAll("_", " ")}</p>
        </section>
        <section className="card">
          <h2>{t.procWhatIncluded}</h2>
          <p>{item.billing_notice}</p>
        </section>
        <section className="card">
          <h2>{t.procWhatSeparate}</h2>
          <p>{t.procWhatSeparateBody}</p>
        </section>
      </div>
      <section
        className="price-overview"
        aria-labelledby="price-overview-heading"
      >
        <div className="section-heading">
          <p className="eyebrow">{t.procPriceOverview}</p>
          <h2 id="price-overview-heading">
            {t.procPublishedRangesIn.replace("{region}", launchRegion.name)}
          </h2>
        </div>
        <div className="price-overview-grid">
          <article>
            <span>{t.procCashRangeLabel}</span>
            <strong>
              <PriceRange
                min={
                  cashMins.length
                    ? String(Math.min(...cashMins.map(Number)))
                    : null
                }
                max={
                  cashMaxes.length
                    ? String(Math.max(...cashMaxes.map(Number)))
                    : null
                }
                messages={t}
              />
            </strong>
          </article>
          <article>
            <span>{t.procLocationsWithInsurance}</span>
            <strong>{locationsWithInsuranceRates}</strong>
            <small>{t.procChoosePayerHint}</small>
          </article>
          <article>
            <span>{t.procHospitalsWithPrices}</span>
            <strong>{comparison?.facilities_with_prices ?? 0}</strong>
          </article>
        </div>
        <p className="field-help">{t.procCashRangeNote}</p>
      </section>
      <section className="section" style={{ paddingInline: 0 }}>
        <div className="section-heading">
          <p className="eyebrow">{t.procNearbyComparisons}</p>
          <h2>{t.procPublishedAvailability}</h2>
        </div>
        <CoverageNotice messages={t}>
          {t.procAvailabilityNotice
            .replace(
              "{withPrices}",
              String(comparison?.facilities_with_prices ?? 0),
            )
            .replace("{active}", String(comparison?.active_facilities ?? 0))}
        </CoverageNotice>
        <Link
          className="button"
          href={localePath(locale, `/procedures/${item.slug}/prices`)}
        >
          {t.procCompareFacilities}
        </Link>
      </section>
      <section className="card">
        <h2>{t.procQualityConsiderations}</h2>
        <p>{t.procQualityConsiderationsBody}</p>
        <p>
          {t.procRelatedTerms}{" "}
          {item.aliases.join(", ") || t.procNoneListed}
        </p>
      </section>
      <SourceAttribution quality messages={t} />
      <PricingDisclaimer messages={t} />
      <p className="muted">{t.procEducationalNote}</p>
    </main>
  );
}

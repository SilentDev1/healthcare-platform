import Link from "next/link";
import { AskEntry } from "./components/AskEntry";
import { CareSearch } from "./components/CareSearch";
import { ComparisonFacilityCard, CoverageNotice } from "./components/ui";
import { InlineComparePanel } from "./components/CompareSelect";
import { apiGet } from "../lib/api";
import type { ProcedureComparison } from "../lib/api";
import { localePath, type Messages } from "../lib/i18n";
import { requestLocale, requestMessages } from "../lib/i18n-server";

interface Coverage {
  nh_facilities: number;
  facilities_with_publishable_prices: number;
  publishable_procedures: number;
}
const popular: { q: string; key: keyof Messages }[] = [
  { q: "MRI", key: "popularMri" },
  { q: "CT scan", key: "popularCtScan" },
  { q: "colonoscopy", key: "popularColonoscopy" },
  { q: "mammogram", key: "popularMammogram" },
  { q: "knee replacement", key: "popularKneeReplacement" },
  { q: "hip replacement", key: "popularHipReplacement" },
  { q: "childbirth", key: "popularChildbirth" },
  { q: "lab tests", key: "popularLabTests" },
];

export default async function Home() {
  const locale = await requestLocale();
  const t = await requestMessages();
  let coverage: Coverage | null = null;
  let featured: ProcedureComparison | null = null;
  try {
    [coverage, featured] = await Promise.all([
      apiGet<Coverage>("/api/v1/pricing/coverage"),
      apiGet<ProcedureComparison>(
        "/api/v1/procedures/mri-knee-without-contrast/comparison?state=NH",
      ),
    ]);
  } catch {}
  const featuredItems =
    featured?.items?.filter((item) => item.price_available).slice(0, 4) ?? [];
  return (
    <>
      <main className="hero product-hero">
        <div className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">{t.eyebrow}</p>
            <h1>
              {t.heroTitle} <span>{t.heroAccent}</span>
            </h1>
            <p className="lede">{t.heroBody}</p>
            <p className="hero-assurance">
              <strong>{t.free}</strong> <i aria-hidden="true">•</i>{" "}
              {t.noAccount} <i aria-hidden="true">•</i> {t.publishedData}
            </p>
          </div>
        </div>
        <div className="hero-search-panel">
          <CareSearch showInsurance locale={locale} />
          <div className="popular">
            <strong>{t.popular}</strong>
            <div className="popular-links">
              {popular.map(({ q, key }) => (
                <Link
                  className="chip"
                  key={q}
                  href={`${localePath(locale, "/search")}?q=${encodeURIComponent(q)}`}
                >
                  {t[key]}
                </Link>
              ))}
            </div>
          </div>
          <AskEntry locale={locale} variant="home" />
        </div>
      </main>
      {featured && featuredItems.length > 0 && (
        <section className="section featured-marketplace">
          <div className="marketplace-section-heading">
            <div>
              <p className="eyebrow">{t.homeFeaturedEyebrow}</p>
              <h2>{featured.procedure_name}</h2>
              <p>{t.homeFeaturedIntro}</p>
            </div>
            <Link
              className="button secondary"
              href={localePath(
                locale,
                "/procedures/mri-knee-without-contrast/prices",
              )}
            >
              {t.homeViewAllMatching}
            </Link>
          </div>
          <div className="marketplace-results-layout">
            <section
              className="result-list"
              aria-label={t.homeFeaturedPricesAria}
            >
              {featuredItems.map((item) => (
                <ComparisonFacilityCard
                  key={`${item.facility_id}-${item.facility_location_id}`}
                  item={item}
                  procedureName={featured.procedure_name}
                  procedureSlug={featured.procedure_slug}
                  messages={t}
                  locale={locale}
                />
              ))}
            </section>
            <InlineComparePanel
              procedureSlug={featured.procedure_slug}
              procedureName={featured.procedure_name}
              items={featuredItems}
              locale={locale}
            />
          </div>
        </section>
      )}
      <section className="section product-intro">
        <div className="section-heading">
          <p className="eyebrow">{t.howItWorks}</p>
          <h2>{t.homeHowItWorksHeading}</h2>
        </div>
        <div className="feature-grid steps product-steps">
          {[
            [t.homeStepSearchTitle, t.homeStepSearchBody],
            [t.homeStepCompareTitle, t.homeStepCompareBody],
            [t.homeStepVerifyTitle, t.homeStepVerifyBody],
          ].map(([title, body]) => (
            <article className="card feature-card" key={title}>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="section compact-trust">
        <div>
          <p className="eyebrow">{t.homeDataEyebrow}</p>
          <h2>{t.homeDataHeading}</h2>
          <p>{t.homeDataBody}</p>
        </div>
        <CoverageNotice messages={t}>
          {coverage
            ? t.homeCoverageSummary
                .replace(
                  "{withPrices}",
                  String(coverage.facilities_with_publishable_prices),
                )
                .replace("{total}", String(coverage.nh_facilities))
                .replace("{procedures}", String(coverage.publishable_procedures))
            : t.homeCoverageFallback}
        </CoverageNotice>
        <Link
          className="button secondary"
          href={localePath(locale, "/about-data")}
        >
          {t.homeViewCoverageMethodology}
        </Link>
      </section>
    </>
  );
}

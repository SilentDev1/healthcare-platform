import Link from "next/link";
import { CareSearch } from "./components/CareSearch";
import { ComparisonFacilityCard, CoverageNotice } from "./components/ui";
import { InlineComparePanel } from "./components/CompareSelect";
import { apiGet } from "../lib/api";
import type { ProcedureComparison } from "../lib/api";
import { localePath } from "../lib/i18n";
import { requestLocale, requestMessages } from "../lib/i18n-server";

interface Coverage {
  nh_facilities: number;
  facilities_with_publishable_prices: number;
  publishable_procedures: number;
}
const popular = [
  "MRI",
  "CT scan",
  "colonoscopy",
  "mammogram",
  "knee replacement",
  "hip replacement",
  "childbirth",
  "lab tests",
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
              {popular.map((term) => (
                <Link
                  className="chip"
                  key={term}
                  href={`${localePath(locale, "/search")}?q=${encodeURIComponent(term)}`}
                >
                  {term}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </main>
      {featured && featuredItems.length > 0 && (
        <section className="section featured-marketplace">
          <div className="marketplace-section-heading">
            <div>
              <p className="eyebrow">Real published prices</p>
              <h2>{featured.procedure_name}</h2>
              <p>
                Select up to three New Hampshire hospitals to compare their
                published prices side by side.
              </p>
            </div>
            <Link
              className="button secondary"
              href={localePath(
                locale,
                "/procedures/mri-knee-without-contrast/prices",
              )}
            >
              View all matching hospitals
            </Link>
          </div>
          <div className="marketplace-results-layout">
            <section className="result-list" aria-label="Featured prices">
              {featuredItems.map((item) => (
                <ComparisonFacilityCard
                  key={`${item.facility_id}-${item.facility_location_id}`}
                  item={item}
                  procedureName={featured.procedure_name}
                  procedureSlug={featured.procedure_slug}
                  messages={t}
                />
              ))}
            </section>
            <InlineComparePanel
              procedureSlug={featured.procedure_slug}
              procedureName={featured.procedure_name}
              items={featuredItems}
            />
          </div>
        </section>
      )}
      <section className="section product-intro">
        <div className="section-heading">
          <p className="eyebrow">How it works</p>
          <h2>Search, compare, then verify</h2>
        </div>
        <div className="feature-grid steps product-steps">
          {[
            [
              "Search",
              "Use everyday language, like “knee MRI” or “mammogram.”",
            ],
            [
              "Compare",
              "Review published prices, locations, and service settings.",
            ],
            [
              "Verify",
              "Confirm your benefits and expected charges with the provider and insurer.",
            ],
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
          <p className="eyebrow">Real published data</p>
          <h2>Prices with sources and limitations attached</h2>
          <p>
            Hospital files provide pricing. CMS Care Compare provides applicable
            quality information. Missing data stays visibly missing.
          </p>
        </div>
        <CoverageNotice>
          {coverage
            ? `Published prices are currently available for ${coverage.facilities_with_publishable_prices} of ${coverage.nh_facilities} active hospitals in the launch region, covering ${coverage.publishable_procedures} procedures.`
            : "Coverage is incomplete and varies by hospital and procedure. Availability is always shown with each result."}
        </CoverageNotice>
        <Link
          className="button secondary"
          href={localePath(locale, "/about-data")}
        >
          View coverage and methodology
        </Link>
      </section>
    </>
  );
}

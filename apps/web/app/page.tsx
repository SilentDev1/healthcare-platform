import Link from "next/link";
import { AskEntry } from "./components/AskEntry";
import { NewEnglandMap } from "./components/NewEnglandMap";
import { ComparisonFacilityCard, CoverageNotice } from "./components/ui";
import { InlineComparePanel } from "./components/CompareSelect";
import { apiGet } from "../lib/api";
import type { ProcedureComparison } from "../lib/api";
import { localePath } from "../lib/i18n";
import { askMessages } from "../lib/ask-i18n";
import { homeMessages } from "../lib/home-i18n";
import { requestLocale, requestMessages } from "../lib/i18n-server";

interface Coverage {
  nh_facilities: number;
  facilities_with_publishable_prices: number;
  publishable_procedures: number;
}
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
  const ask = askMessages[locale] ?? askMessages.en;
  const home = homeMessages[locale] ?? homeMessages.en;
  return (
    <>
      <main className="hero product-hero ne-hero">
        <div className="ne-hero-inner">
          <div className="ne-hero-left">
            <p className="eyebrow ne-eyebrow">{home.eyebrow}</p>
            <h1 className="ne-headline">
              {t.heroTitle} <span>{t.heroAccent}</span>
            </h1>
            <p className="lede ne-lede">{t.heroBody}</p>

            {/* Primary interaction: Ask Carevero (a friendly interface over verified data). */}
            <AskEntry locale={locale} variant="home" />

            {/* Secondary, but clearly visible: the existing deterministic price search. */}
            <div className="ne-manual">
              <span className="ne-manual-prompt">{ask.homeManualPrompt}</span>
              <Link
                className="button secondary ne-manual-cta"
                href={localePath(locale, "/search")}
              >
                {ask.homeManualCta} →
              </Link>
            </div>

            <ul className="ne-trust" aria-label={t.publishedData}>
              <li>
                <span className="ne-trust-check" aria-hidden="true">
                  ✓
                </span>{" "}
                {t.free}
              </li>
              <li>
                <span className="ne-trust-check" aria-hidden="true">
                  ✓
                </span>{" "}
                {t.noAccount}
              </li>
              <li>
                <span className="ne-trust-check" aria-hidden="true">
                  ✓
                </span>{" "}
                {t.publishedData}
              </li>
            </ul>
          </div>

          <div className="ne-hero-right">
            <NewEnglandMap locale={locale} t={t} />
          </div>
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

import Link from "next/link";
import { AskEntry } from "./components/AskEntry";
import { ComparisonFacilityCard, CoverageNotice } from "./components/ui";
import { InlineComparePanel } from "./components/CompareSelect";
import { apiGet } from "../lib/api";
import type { ProcedureComparison } from "../lib/api";
import { localePath } from "../lib/i18n";
import { askMessages } from "../lib/ask-i18n";
import { homeMessages } from "../lib/home-i18n";
import { requestLocale, requestMessages } from "../lib/i18n-server";
import { ExperienceTrigger } from "./components/GlobalExperience";

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
              <ExperienceTrigger
                kind="search"
                className="button secondary ne-manual-cta"
              >
                {ask.homeManualCta} →
              </ExperienceTrigger>
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
        </div>

        {/* Expansion card overlays the New England map baked into the hero image.
            Honest status: NH is live, other states are "soon" — no live-MA claim,
            no hardcoded coverage numbers. */}
        <aside className="ne-expand-card" aria-label={home.expandTitle}>
          <span className="ne-expand-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="22" height="22">
              <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.6" />
              <path
                d="M3 12h18M12 3c2.5 2.6 2.5 15.4 0 18M12 3c-2.5 2.6-2.5 15.4 0 18"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
              />
            </svg>
          </span>
          <div className="ne-expand-text">
            <p className="ne-expand-title">{home.expandTitle}</p>
            <p className="ne-expand-body">{home.expandBody}</p>
          </div>
        </aside>
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
            ? t.homeCoverageSummary.replace(
                "{procedures}",
                String(coverage.publishable_procedures),
              )
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

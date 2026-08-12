import Link from "next/link";
import type { Metadata } from "next";
import {
  apiGet,
  type ProcedureComparison,
  type ProcedureComparisonItem,
} from "../../lib/api";
import {
  PriceRange,
  PricingDisclaimer,
  QualityRating,
  SourceAttribution,
} from "../components/ui";
import { launchRegion } from "../../lib/brand";
import { ShareComparison } from "../components/ShareComparison";
import { formatCashExplanation, localePath } from "../../lib/i18n";
import { requestLocale, requestMessages } from "../../lib/i18n-server";

export const metadata: Metadata = {
  title: "Compare hospital prices",
  robots: { index: false, follow: true },
};

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{
    items?: string;
    procedure?: string;
    payer?: string;
    plan?: string;
  }>;
}) {
  const locale = await requestLocale();
  const t = await requestMessages();
  const values = await searchParams;
  const procedure = values.procedure ?? "";
  const payer = values.payer ?? "";
  const plan = values.plan ?? "";
  const selected = (values.items ?? "").split(",").filter(Boolean).slice(0, 3);
  if (!procedure || selected.length < 2) {
    return (
      <main className="narrow">
        <p className="eyebrow">{t.cmpSideBySide}</p>
        <h1>{t.cmpChooseTwoOrThreeTitle}</h1>
        <p className="lede">{t.cmpStartFromProcedure}</p>
        <Link className="button" href={localePath(locale, "/procedures")}>
          {t.cmpFindProcedure}
        </Link>
      </main>
    );
  }

  let data: ProcedureComparison;
  let payerName = "";
  let planName = "";
  try {
    const [comparison, payers, plans] = await Promise.all([
      apiGet<ProcedureComparison>(
        `/api/v1/procedures/${encodeURIComponent(procedure)}/comparison?state=${launchRegion.state}${payer ? `&payer=${encodeURIComponent(payer)}` : ""}${plan ? `&plan=${encodeURIComponent(plan)}` : ""}`,
      ),
      payer
        ? apiGet<Array<{ slug: string; name: string }>>(
            "/api/v1/pricing/payers",
          )
        : Promise.resolve([]),
      plan
        ? apiGet<Array<{ id: string; name: string }>>(
            `/api/v1/pricing/plans?payer=${encodeURIComponent(payer)}`,
          )
        : Promise.resolve([]),
    ]);
    data = comparison;
    payerName = payers.find((item) => item.slug === payer)?.name ?? payer;
    planName = plans.find((item) => item.id === plan)?.name ?? plan;
  } catch {
    return (
      <main>
        <h1>{t.cmpUnavailableTitle}</h1>
        <p className="error" role="alert">
          {t.cmpUnavailableBody}
        </p>
      </main>
    );
  }
  const byKey = new Map(
    data.items.map((item) => [
      `${item.facility_id}~${item.facility_location_id}`,
      item,
    ]),
  );
  const items = selected
    .map((key) => byKey.get(key))
    .filter((item): item is ProcedureComparisonItem => Boolean(item));
  if (items.length < 2) {
    return (
      <main className="narrow">
        <h1>{t.cmpSelectionsExpiredTitle}</h1>
        <p>{t.cmpSelectionsExpiredBody}</p>
        <Link
          className="button"
          href={localePath(locale, `/procedures/${procedure}/prices`)}
        >
          {t.cmpReturnToResults}
        </Link>
      </main>
    );
  }

  const row = (
    label: string,
    render: (item: ProcedureComparisonItem) => React.ReactNode,
    cellClass?: (item: ProcedureComparisonItem) => string | undefined,
  ) => (
    <tr>
      <th scope="row">{label}</th>
      {items.map((item) => (
        <td
          className={cellClass?.(item)}
          data-label={label}
          key={item.facility_location_id}
        >
          {render(item)}
        </td>
      ))}
    </tr>
  );
  return (
    <main>
      <nav className="breadcrumbs" aria-label={t.breadcrumb}>
        <Link href={localePath(locale, "/")}>{t.home}</Link>
        <span>/</span>
        <Link href={localePath(locale, `/procedures/${procedure}/prices`)}>
          {data.procedure_name}
        </Link>
        <span>/</span>
        <span>{t.cmpBreadcrumbCompare}</span>
      </nav>
      <p className="eyebrow">{t.cmpSideBySide}</p>
      <h1>{t.cmpCompareProcedure.replace("{procedure}", data.procedure_name)}</h1>
      <p className="lede">{t.cmpLede}</p>
      <ShareComparison locale={locale} />
      <div className="comparison-key" role="note">
        <strong>{t.cmpNegotiatedContextLabel}</strong>{" "}
        {payer
          ? t.cmpOnlyRatesFor.replace(
              "{payer}",
              `${payerName}${planName ? ` · ${planName}` : ""}`,
            )
          : t.cmpNoInsuranceSelected}{" "}
        {t.cmpDoesNotGuarantee}
      </div>
      <div className="table-wrap compare-wrap">
        <table className="compare-table">
          <thead>
            <tr>
              <th>{t.cmpMeasure}</th>
              {items.map((item) => (
                <th scope="col" key={item.facility_location_id}>
                  <span className="compare-location-name">
                    {item.location_name ?? item.facility_name}
                  </span>
                  {item.location_name && <small>{item.facility_name}</small>}
                  <Link
                    href={localePath(locale, `/hospitals/${item.facility_id}`)}
                  >
                    {t.viewDetails}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {row(
              t.location,
              (item) => `${item.city}, ${item.state} ${item.postal_code}`,
            )}
            {row(t.cmpRowCmsOverall, (item) => (
              <QualityRating value={item.cms_overall_rating} messages={t} />
            ))}
            {row(t.publishedCashPrice, (item) => {
              const explanation = formatCashExplanation(
                t,
                item.cash_price_reason_codes,
                item.cash_price_value_count ?? 0,
              );
              return (
                <>
                  <PriceRange
                    min={item.cash_price_min}
                    max={item.cash_price_max}
                    messages={t}
                  />
                  {explanation && <small>{explanation}</small>}
                </>
              );
            })}
            {row(
              payer ? t.matchingRates : t.cmpPublishedInsuranceRates,
              (item) =>
                payer ? (
                  <>
                    <PriceRange
                      min={item.negotiated_price_min}
                      max={item.negotiated_price_max}
                      messages={t}
                    />
                    <small>
                      {t.cmpMatchingRecords.replace(
                        "{count}",
                        String(item.matching_negotiated_rate_count ?? 0),
                      )}
                    </small>
                  </>
                ) : item.distinct_payer_count ? (
                  t.cmpPayersPublish.replace(
                    "{count}",
                    String(item.distinct_payer_count),
                  )
                ) : (
                  t.cmpNoNormalizedPayerRates
                ),
            )}
            {row(t.serviceSetting, (item) =>
              item.service_settings.length
                ? item.service_settings.join(", ").replaceAll("_", " ")
                : t.notAvailable,
            )}
            {row(t.facilityType, (item) => item.facility_type ?? t.cmpNotListed)}
            {row(t.cmpPriceCoverage, (item) =>
              item.price_available
                ? t.cmpSummaries.replace(
                    "{count}",
                    String(item.summary_count),
                  )
                : t.priceNotAvailable,
            )}
            {row(t.cmpQualityMeasuresRow, (item) => (
              <Link
                href={localePath(
                  locale,
                  `/hospitals/${item.facility_id}#quality`,
                )}
              >
                {t.cmpReviewCmsMeasures}
              </Link>
            ))}
            {row(t.cmpSourceAndFreshness, (item) =>
              item.price_available ? (
                <SourceAttribution
                  updated={item.latest_updated ?? undefined}
                  url={item.source_url ?? undefined}
                  messages={t}
                />
              ) : (
                t.cmpNoPublishableSource
              ),
            )}
            {row(t.cmpImportantNotes, (item) =>
              item.price_available
                ? t.cmpPublishedRateNote
                : t.cmpMayOfferNote,
            )}
          </tbody>
        </table>
      </div>
      <PricingDisclaimer messages={t} />
    </main>
  );
}

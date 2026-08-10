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

export const metadata: Metadata = {
  title: "Compare hospital prices",
  robots: { index: false, follow: true },
};

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ items?: string; procedure?: string; payer?: string }>;
}) {
  const values = await searchParams;
  const procedure = values.procedure ?? "";
  const payer = values.payer ?? "";
  const selected = (values.items ?? "").split(",").filter(Boolean).slice(0, 3);
  if (!procedure || selected.length < 2) {
    return (
      <main className="narrow">
        <p className="eyebrow">Side-by-side comparison</p>
        <h1>Choose two or three service locations</h1>
        <p className="lede">
          Start from a procedure price page so every price in the comparison
          refers to the same service.
        </p>
        <Link className="button" href="/procedures">
          Find a procedure
        </Link>
      </main>
    );
  }

  let data: ProcedureComparison;
  let payerName = "";
  try {
    const [comparison, payers] = await Promise.all([
      apiGet<ProcedureComparison>(
        `/api/v1/procedures/${encodeURIComponent(procedure)}/comparison?state=${launchRegion.state}${payer ? `&payer=${encodeURIComponent(payer)}` : ""}`,
      ),
      payer
        ? apiGet<Array<{ slug: string; name: string }>>(
            "/api/v1/pricing/payers",
          )
        : Promise.resolve([]),
    ]);
    data = comparison;
    payerName = payers.find((item) => item.slug === payer)?.name ?? payer;
  } catch {
    return (
      <main>
        <h1>Comparison unavailable</h1>
        <p className="error" role="alert">
          We couldn’t load these published prices right now.
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
        <h1>Comparison selections expired</h1>
        <p>Select the hospitals again from the procedure results page.</p>
        <Link className="button" href={`/procedures/${procedure}/prices`}>
          Return to results
        </Link>
      </main>
    );
  }

  const settingSignature = (item: ProcedureComparisonItem) =>
    [...item.service_settings].sort().join("|");
  const cashPricesAreComparable =
    items.every((item) => item.cash_price_min !== null) &&
    items.every(
      (item) => settingSignature(item) === settingSignature(items[0]),
    );
  const lowestComparableCash = cashPricesAreComparable
    ? Math.min(...items.map((item) => Number(item.cash_price_min)))
    : null;

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
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span>/</span>
        <Link href={`/procedures/${procedure}/prices`}>
          {data.procedure_name}
        </Link>
        <span>/</span>
        <span>Compare</span>
      </nav>
      <p className="eyebrow">Side-by-side comparison</p>
      <h1>Compare {data.procedure_name}</h1>
      <p className="lede">
        Review published differences without treating price or a single quality
        measure as a “best hospital” ranking.
      </p>
      <ShareComparison />
      <div className="comparison-key" role="note">
        <strong>Negotiated-price context:</strong>{" "}
        {payer
          ? `Only negotiated rates published for the selected payer (${payerName}) are included.`
          : "Negotiated ranges combine available published payers and plans."}{" "}
        This does not guarantee network participation or coverage.
      </div>
      <div className="table-wrap compare-wrap">
        <table className="compare-table">
          <thead>
            <tr>
              <th>Measure</th>
              {items.map((item) => (
                <th scope="col" key={item.facility_location_id}>
                  <span className="compare-location-name">
                    {item.location_name ?? item.facility_name}
                  </span>
                  {item.location_name && <small>{item.facility_name}</small>}
                  <Link href={`/hospitals/${item.facility_id}`}>
                    View details
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {row(
              "Location",
              (item) => `${item.city}, ${item.state} ${item.postal_code}`,
            )}
            {row("CMS overall rating", (item) => (
              <QualityRating value={item.cms_overall_rating} />
            ))}
            {row(
              "Published cash price",
              (item) => (
                <>
                  <PriceRange
                    min={item.cash_price_min}
                    max={item.cash_price_max}
                  />
                  {lowestComparableCash !== null &&
                    Number(item.cash_price_min) === lowestComparableCash && (
                      <span className="lowest-price-label">
                        Lowest published comparable price
                      </span>
                    )}
                </>
              ),
              (item) =>
                lowestComparableCash !== null &&
                Number(item.cash_price_min) === lowestComparableCash
                  ? "highlight"
                  : undefined,
            )}
            {row(
              payer
                ? "Published negotiated range for selected payer"
                : "Published negotiated range across available payers",
              (item) => (
                <PriceRange
                  min={item.negotiated_price_min}
                  max={item.negotiated_price_max}
                />
              ),
            )}
            {row("Service setting", (item) =>
              item.service_settings.length
                ? item.service_settings.join(", ").replaceAll("_", " ")
                : "Not available",
            )}
            {row("Facility type", (item) => item.facility_type ?? "Not listed")}
            {row("Price coverage", (item) =>
              item.price_available
                ? `${item.summary_count} publishable rate summaries`
                : "Price not currently available",
            )}
            {row("Quality measures", (item) => (
              <Link href={`/hospitals/${item.facility_id}#quality`}>
                Review CMS measures
              </Link>
            ))}
            {row("Source and freshness", (item) =>
              item.price_available ? (
                <SourceAttribution
                  updated={item.latest_updated ?? undefined}
                  url={item.source_url ?? undefined}
                />
              ) : (
                "No publishable source for this procedure"
              ),
            )}
            {row("Important notes", (item) =>
              item.price_available
                ? "Published hospital rate; separately billed services may apply."
                : "The hospital may offer this service even though no price is publishable.",
            )}
          </tbody>
        </table>
      </div>
      <PricingDisclaimer />
    </main>
  );
}

import Link from "next/link";
import {
  apiGet,
  type Facility,
  type PricePage,
  type QualityPage,
} from "../../lib/api";
import {
  PriceRange,
  PricingDisclaimer,
  QualityRating,
  SourceAttribution,
} from "../components/ui";
type Item = { facility: Facility; quality: QualityPage; prices: PricePage };
export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ ids?: string }>;
}) {
  const ids =
    (await searchParams).ids?.split(",").filter(Boolean).slice(0, 3) ?? [];
  const results = await Promise.allSettled(
    ids.map(async (id) => ({
      facility: await apiGet<Facility>(`/api/v1/facilities/${id}`),
      quality: await apiGet<QualityPage>(
        `/api/v1/facilities/${id}/quality?page_size=100`,
      ),
      prices: await apiGet<PricePage>(
        `/api/v1/facilities/${id}/prices?page_size=25`,
      ),
    })),
  );
  const items = results
    .filter((r): r is PromiseFulfilledResult<Item> => r.status === "fulfilled")
    .map((r) => r.value);
  if (items.length < 2)
    return (
      <main>
        <h1>Compare hospitals</h1>
        <p>
          Select two or three facilities from a procedure price results page to
          compare them side by side.
        </p>
        <Link className="button" href="/procedures">
          Find a procedure
        </Link>
      </main>
    );
  const row = (label: string, render: (item: Item) => React.ReactNode) => (
    <tr>
      <th scope="row">{label}</th>
      {items.map((item) => (
        <td data-label={label} key={item.facility.id}>
          {render(item)}
        </td>
      ))}
    </tr>
  );
  return (
    <main>
      <nav className="breadcrumbs">
        <Link href="/">Home</Link>
        <span>/</span>
        <span>Compare</span>
      </nav>
      <p className="eyebrow">Side-by-side comparison</p>
      <h1>Compare hospitals</h1>
      <p className="lede">
        Review published facts and differences. Lower price does not mean better
        clinical care.
      </p>
      <div className="table-wrap">
        <table className="compare-table">
          <thead>
            <tr>
              <th>Measure</th>
              {items.map((i) => (
                <th scope="col" key={i.facility.id}>
                  {i.facility.display_name}
                  <br />
                  <Link href={`/hospitals/${i.facility.id}`}>View details</Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {row(
              "Location",
              (i) =>
                `${i.facility.locations[0]?.city ?? "—"}, ${i.facility.locations[0]?.state ?? ""}`,
            )}
            {row(
              "Facility type",
              (i) => i.facility.facility_type ?? "Not listed",
            )}
            {row("CMS overall rating", (i) => (
              <QualityRating
                value={
                  i.quality.items.find(
                    (q) => q.cms_measure_id === "OVERALL_RATING",
                  )?.score
                }
              />
            ))}
            {row("Published cash prices", (i) =>
              i.prices.items.length ? (
                <PriceRange
                  min={i.prices.items[0].cash_price_min}
                  max={i.prices.items[0].cash_price_max}
                />
              ) : (
                "Not currently available"
              ),
            )}
            {row("Negotiated price range", (i) =>
              i.prices.items.length ? (
                <PriceRange
                  min={i.prices.items[0].negotiated_price_min}
                  max={i.prices.items[0].negotiated_price_max}
                />
              ) : (
                "Not currently available"
              ),
            )}
            {row(
              "Price coverage",
              (i) => `${i.prices.total} publishable summaries`,
            )}
            {row(
              "Service setting",
              (i) =>
                i.prices.items[0]?.service_setting?.replaceAll("_", " ") ??
                "Not available",
            )}
            {row("Source updated", (i) =>
              i.prices.items[0] ? (
                <SourceAttribution
                  updated={i.prices.items[0].last_updated}
                  url={i.prices.items[0].source_url}
                />
              ) : (
                "No publishable source"
              ),
            )}
          </tbody>
        </table>
      </div>
      <PricingDisclaimer />
    </main>
  );
}

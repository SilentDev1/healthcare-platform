import Link from "next/link";
import {
  apiGet,
  type Procedure,
  type ProcedureComparison,
  type ProcedureComparisonItem,
} from "../../../../lib/api";
import {
  ComparisonFacilityCard,
  CoverageNotice,
  EmptyState,
  ErrorState,
  FilterPanel,
  PricingDisclaimer,
} from "../../../components/ui";
import { launchRegion } from "../../../../lib/brand";
import { CompareTray } from "../../../components/CompareSelect";

interface Filters {
  location?: string;
  setting?: string;
  payer?: string;
  facility_type?: string;
  availability?: string;
  rating?: string;
  sort?: string;
}

function sortItems(items: ProcedureComparisonItem[], sort: string | undefined) {
  return [...items].sort((left, right) => {
    if (sort === "cash")
      return (
        Number(left.cash_price_min ?? Infinity) -
        Number(right.cash_price_min ?? Infinity)
      );
    if (sort === "rating")
      return (
        Number(right.cms_overall_rating ?? -1) -
        Number(left.cms_overall_rating ?? -1)
      );
    if (sort === "name")
      return left.facility_name.localeCompare(right.facility_name);
    return (
      Number(right.price_available) - Number(left.price_available) ||
      left.facility_name.localeCompare(right.facility_name)
    );
  });
}

export default async function ProcedurePrices({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Filters>;
}) {
  const { slug } = await params;
  const filters = await searchParams;
  const query = new URLSearchParams({ state: launchRegion.state });
  if (filters.setting) query.set("setting", filters.setting);
  if (filters.payer) query.set("payer", filters.payer);
  if (filters.location) {
    if (/^\d{5}$/.test(filters.location))
      query.set("postal_code", filters.location);
    else query.set("city", filters.location);
  }
  try {
    const [data, procedure, payers] = await Promise.all([
      apiGet<ProcedureComparison>(
        `/api/v1/procedures/${encodeURIComponent(slug)}/comparison?${query}`,
      ),
      apiGet<Procedure>(`/api/v1/procedures/${encodeURIComponent(slug)}`),
      apiGet<Array<{ slug: string; name: string }>>("/api/v1/pricing/payers"),
    ]);
    let items = data.items.filter((item) => {
      if (filters.availability === "available" && !item.price_available)
        return false;
      if (filters.availability === "unavailable" && item.price_available)
        return false;
      if (
        filters.facility_type &&
        item.facility_type?.toLowerCase() !==
          filters.facility_type.toLowerCase()
      )
        return false;
      if (
        filters.rating &&
        Number(item.cms_overall_rating ?? 0) < Number(filters.rating)
      )
        return false;
      return true;
    });
    items = sortItems(items, filters.sort);
    const facilityTypes = Array.from(
      new Set(data.items.map((item) => item.facility_type).filter(Boolean)),
    ).sort() as string[];
    const payerName = filters.payer
      ? payers.find((payer) => payer.slug === filters.payer)?.name
      : undefined;
    const activeFilterCount = Object.entries(filters).filter(
      ([key, value]) => key !== "sort" && Boolean(value),
    ).length;

    const filterForm = (
      <form className="filter-form">
        <div className="filter-group">
          <label htmlFor="location">City or ZIP</label>
          <input
            id="location"
            name="location"
            defaultValue={filters.location ?? ""}
            placeholder="Any location"
          />
        </div>
        <div className="filter-group">
          <label htmlFor="availability">Price availability</label>
          <select
            id="availability"
            name="availability"
            defaultValue={filters.availability ?? ""}
          >
            <option value="">All hospitals</option>
            <option value="available">Published price available</option>
            <option value="unavailable">Price not available</option>
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="setting">Service setting</label>
          <select
            id="setting"
            name="setting"
            defaultValue={filters.setting ?? ""}
          >
            <option value="">All settings</option>
            <option value="outpatient">Outpatient</option>
            <option value="inpatient">Inpatient</option>
            <option value="emergency_department">Emergency department</option>
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="payer">Insurance (published rates)</label>
          <select id="payer" name="payer" defaultValue={filters.payer ?? ""}>
            <option value="">All available payers</option>
            {payers.map((payer) => (
              <option key={payer.slug} value={payer.slug}>
                {payer.name}
              </option>
            ))}
          </select>
          <p className="field-help">
            A published negotiated rate does not guarantee network
            participation.
          </p>
        </div>
        <div className="filter-group">
          <label htmlFor="rating">Minimum CMS rating</label>
          <select id="rating" name="rating" defaultValue={filters.rating ?? ""}>
            <option value="">Any rating</option>
            <option value="3">3+ stars</option>
            <option value="4">4+ stars</option>
            <option value="5">5 stars</option>
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="facility_type">Facility type</label>
          <select
            id="facility_type"
            name="facility_type"
            defaultValue={filters.facility_type ?? ""}
          >
            <option value="">All facility types</option>
            {facilityTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        {filters.sort && (
          <input type="hidden" name="sort" value={filters.sort} />
        )}
        <button className="button" type="submit">
          Apply filters
        </button>
        <Link className="text-link" href={`/procedures/${slug}/prices`}>
          Clear filters
        </Link>
      </form>
    );

    return (
      <main>
        <nav className="breadcrumbs" aria-label="Breadcrumb">
          <Link href="/">Home</Link>
          <span>/</span>
          <Link href="/procedures">Procedures</Link>
          <span>/</span>
          <Link href={`/procedures/${slug}`}>{procedure.consumer_name}</Link>
          <span>/</span>
          <span>Compare prices</span>
        </nav>
        <div className="page-heading comparison-heading">
          <p className="eyebrow">Compare service locations</p>
          <h1>{procedure.consumer_name}</h1>
          <p className="lede">
            Published hospital prices in {launchRegion.name}. These are not
            personalized estimates, and lower price does not mean better care.
          </p>
        </div>
        <CoverageNotice>
          {filters.payer && data.facilities_with_prices === 0
            ? `No published negotiated rate found for ${payerName ?? "this payer"}. This does not mean the payer is not accepted, the hospital is out of network, or the service is not covered.`
            : `Published prices are available from ${data.facilities_with_prices} of ${data.active_facilities} active hospitals for this procedure. All matching hospitals remain visible, including those without a publishable price.`}
        </CoverageNotice>
        <div className="toolbar comparison-toolbar">
          <strong>
            {items.length} service location{items.length === 1 ? "" : "s"}
            {activeFilterCount
              ? ` · ${activeFilterCount} active filter${activeFilterCount === 1 ? "" : "s"}`
              : ""}
          </strong>
          <form className="sort-form">
            {Object.entries(filters)
              .filter(([key, value]) => key !== "sort" && value)
              .map(([key, value]) => (
                <input key={key} type="hidden" name={key} value={value} />
              ))}
            <label htmlFor="sort">Sort</label>
            <select
              id="sort"
              name="sort"
              defaultValue={filters.sort ?? "recommended"}
            >
              <option value="recommended">Price availability, then name</option>
              <option value="cash">Lowest published cash price</option>
              <option value="rating">Highest CMS rating</option>
              <option value="name">Hospital name</option>
            </select>
            <button className="button secondary">Apply</button>
          </form>
        </div>
        <div className="results-layout">
          <FilterPanel>{filterForm}</FilterPanel>
          <section className="result-list" aria-label="Facility results">
            {items.length === 0 ? (
              <EmptyState title="No hospitals match these filters">
                <p>
                  Try removing a filter. A missing result does not mean the
                  service is unavailable, not accepted, or not covered.
                </p>
                <div className="card-actions">
                  <Link
                    className="button secondary"
                    href={`/procedures/${slug}/prices`}
                  >
                    Clear all filters
                  </Link>
                  {filters.payer && (
                    <Link
                      className="button secondary"
                      href={`/procedures/${slug}/prices?availability=${filters.availability ?? ""}`}
                    >
                      Clear payer
                    </Link>
                  )}
                </div>
              </EmptyState>
            ) : (
              items.map((item) => (
                <ComparisonFacilityCard
                  key={`${item.facility_id}-${item.facility_location_id}`}
                  item={item}
                  procedureName={procedure.consumer_name}
                  procedureSlug={slug}
                  payerName={payerName}
                />
              ))
            )}
          </section>
        </div>
        <PricingDisclaimer />
        <CompareTray procedureSlug={slug} payer={filters.payer} />
      </main>
    );
  } catch {
    return (
      <main>
        <ErrorState retryHref={`/procedures/${slug}/prices`} />
      </main>
    );
  }
}

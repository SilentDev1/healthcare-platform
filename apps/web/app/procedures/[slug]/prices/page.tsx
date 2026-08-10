import Link from "next/link";
import { apiGet, type PricePage, type Procedure } from "../../../../lib/api";
import { CompareSelect } from "../../../components/CompareSelect";
import {
  CoverageNotice,
  EmptyState,
  ErrorState,
  FacilityPriceCard,
  PricingDisclaimer,
} from "../../../components/ui";

export default async function ProcedurePrices({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{
    setting?: string;
    payer?: string;
    city?: string;
    sort?: string;
  }>;
}) {
  const { slug } = await params;
  const filters = await searchParams;
  const query = new URLSearchParams({ state: "NH", page_size: "50" });
  if (filters.setting) query.set("setting", filters.setting);
  if (filters.payer) query.set("payer", filters.payer);
  if (filters.city) query.set("city", filters.city);
  try {
    const [data, procedure, payers] = await Promise.all([
      apiGet<PricePage>(
        `/api/v1/procedures/${encodeURIComponent(slug)}/prices?${query}`,
      ),
      apiGet<Procedure>(`/api/v1/procedures/${encodeURIComponent(slug)}`),
      apiGet<Array<{ slug: string; name: string }>>("/api/v1/pricing/payers"),
    ]);
    const items = [...data.items].sort((a, b) =>
      filters.sort === "cash"
        ? Number(a.cash_price_min ?? Infinity) -
          Number(b.cash_price_min ?? Infinity)
        : filters.sort === "name"
          ? a.facility_name.localeCompare(b.facility_name)
          : 0,
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
          <span>Prices</span>
        </nav>
        <div className="page-heading">
          <p className="eyebrow">Compare facilities</p>
          <h1>{procedure.consumer_name}</h1>
          <p className="lede">
            Published prices from hospital transparency files. These are not
            personalized estimates.
          </p>
        </div>
        <CoverageNotice>
          Prices are available at{" "}
          {new Set(items.map((i) => i.facility_id)).size} facilities for this
          procedure. Coverage varies by price type and service setting.
        </CoverageNotice>
        <div className="toolbar">
          <strong>
            {items.length} published result{items.length === 1 ? "" : "s"}
          </strong>
          <div className="toolbar-group">
            <label htmlFor="sort">Sort</label>
            <form>
              <select
                id="sort"
                name="sort"
                defaultValue={filters.sort ?? "recommended"}
              >
                <option value="recommended">Recommended</option>
                <option value="cash">Lowest published cash price</option>
                <option value="name">Hospital name</option>
              </select>
              <button className="button secondary">Apply</button>
            </form>
          </div>
        </div>
        <div className="results-layout">
          <aside className="filters" aria-label="Filters">
            <h2>Filter results</h2>
            <form>
              <div className="filter-group">
                <label htmlFor="city">City</label>
                <input
                  id="city"
                  name="city"
                  defaultValue={filters.city ?? ""}
                  placeholder="Any city"
                />
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
                  <option value="emergency_department">
                    Emergency department
                  </option>
                </select>
              </div>
              <div className="filter-group">
                <label htmlFor="payer">Insurance (published rates)</label>
                <select
                  id="payer"
                  name="payer"
                  defaultValue={filters.payer ?? ""}
                >
                  <option value="">All available payers</option>
                  {payers.map((p) => (
                    <option key={p.slug} value={p.slug}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <p className="muted">
                  A published rate does not guarantee your plan or network
                  participation.
                </p>
              </div>
              <button className="button">Apply filters</button>
            </form>
          </aside>
          <section className="result-list" aria-label="Facility results">
            {items.length === 0 ? (
              <EmptyState title="No publishable prices match these filters">
                Try removing a filter. This does not mean nearby hospitals do
                not provide this service.
              </EmptyState>
            ) : (
              items.map((item) => (
                <div key={item.id}>
                  <FacilityPriceCard item={item} compare={false} />
                  <div className="card-actions">
                    <CompareSelect
                      id={item.facility_id}
                      name={item.facility_name}
                    />
                  </div>
                </div>
              ))
            )}
          </section>
        </div>
        <PricingDisclaimer />
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

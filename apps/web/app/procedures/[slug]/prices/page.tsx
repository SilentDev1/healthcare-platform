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
import { requestLocale, requestMessages } from "../../../../lib/i18n-server";
import {
  CompareTray,
  InlineComparePanel,
} from "../../../components/CompareSelect";
import { PopularSearches } from "../../../components/PopularSearches";

interface Filters {
  location?: string;
  radius?: string;
  setting?: string;
  payer?: string;
  plan?: string;
  facility_type?: string;
  availability?: string;
  rating?: string;
  sort?: string;
}

function sortItems(items: ProcedureComparisonItem[], sort: string | undefined) {
  return [...items].sort((left, right) => {
    if (sort === "distance") {
      const leftDistance = left.distance_miles ?? Number.POSITIVE_INFINITY;
      const rightDistance = right.distance_miles ?? Number.POSITIVE_INFINITY;
      return (
        leftDistance - rightDistance ||
        left.facility_name.localeCompare(right.facility_name)
      );
    }
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
  const messages = await requestMessages();
  const locale = await requestLocale();
  const query = new URLSearchParams({ state: launchRegion.state });
  if (filters.setting) query.set("setting", filters.setting);
  if (filters.payer) query.set("payer", filters.payer);
  if (filters.plan) query.set("plan", filters.plan);
  // Location is the distance origin (not a hard filter): all matching hospitals
  // stay visible; radius filtering is applied by the API from real coordinates.
  if (filters.location) {
    if (/^\d{5}$/.test(filters.location.trim()))
      query.set("origin_zip", filters.location.trim());
    else query.set("origin_city", filters.location.trim());
  }
  if (filters.radius) query.set("radius_miles", filters.radius);
  try {
    const [data, procedure, payers, plans] = await Promise.all([
      apiGet<ProcedureComparison>(
        `/api/v1/procedures/${encodeURIComponent(slug)}/comparison?${query}`,
      ),
      apiGet<Procedure>(`/api/v1/procedures/${encodeURIComponent(slug)}`),
      apiGet<Array<{ slug: string; name: string }>>("/api/v1/pricing/payers"),
      filters.payer
        ? apiGet<Array<{ id: string; name: string; payer_slug: string }>>(
            `/api/v1/pricing/plans?payer=${encodeURIComponent(filters.payer)}`,
          )
        : Promise.resolve([]),
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
    const planName = filters.plan
      ? plans.find((plan) => plan.id === filters.plan)?.name
      : undefined;
    const activeFilterCount = Object.entries(filters).filter(
      ([key, value]) => key !== "sort" && Boolean(value),
    ).length;

    const filterForm = (
      <form className="filter-form">
        <div className="filter-group">
          <label htmlFor="location">{messages.yourLocation}</label>
          <input
            id="location"
            name="location"
            defaultValue={filters.location ?? ""}
            placeholder={messages.searchLocationPlaceholder}
          />
          <p className="field-help">{messages.enterLocationForDistance}</p>
        </div>
        <div className="filter-group">
          <label htmlFor="radius">{messages.distanceRadius}</label>
          <select id="radius" name="radius" defaultValue={filters.radius ?? ""}>
            <option value="">{messages.anyDistance}</option>
            <option value="10">10 {messages.milesUnit}</option>
            <option value="25">25 {messages.milesUnit}</option>
            <option value="50">50 {messages.milesUnit}</option>
            <option value="100">100 {messages.milesUnit}</option>
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="availability">{messages.priceAvailability}</label>
          <select
            id="availability"
            name="availability"
            defaultValue={filters.availability ?? ""}
          >
            <option value="">{messages.availabilityAll}</option>
            <option value="available">{messages.availabilityAvailable}</option>
            <option value="unavailable">
              {messages.availabilityUnavailable}
            </option>
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="setting">{messages.serviceSetting}</label>
          <select
            id="setting"
            name="setting"
            defaultValue={filters.setting ?? ""}
          >
            <option value="">{messages.settingAll}</option>
            <option value="outpatient">{messages.settingOutpatient}</option>
            <option value="inpatient">{messages.settingInpatient}</option>
            <option value="emergency_department">
              {messages.settingEmergency}
            </option>
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="payer">{messages.insurance}</label>
          <select id="payer" name="payer" defaultValue={filters.payer ?? ""}>
            <option value="">{messages.allAvailablePayers}</option>
            {payers.map((payer) => (
              <option key={payer.slug} value={payer.slug}>
                {payer.name}
              </option>
            ))}
          </select>
          <p className="field-help">{messages.networkNotice}</p>
        </div>
        <div className="filter-group">
          <label htmlFor="plan">{messages.planOptional}</label>
          <select
            id="plan"
            name="plan"
            defaultValue={filters.plan ?? ""}
            disabled={!filters.payer}
          >
            <option value="">{messages.allPublishedPlans}</option>
            {plans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name}
              </option>
            ))}
          </select>
          <p className="field-help">{messages.planHelp}</p>
        </div>
        <div className="filter-group">
          <label htmlFor="rating">{messages.minimumCmsRating}</label>
          <select id="rating" name="rating" defaultValue={filters.rating ?? ""}>
            <option value="">{messages.ratingAny}</option>
            <option value="3">{messages.ratingThreePlus}</option>
            <option value="4">{messages.ratingFourPlus}</option>
            <option value="5">{messages.ratingFive}</option>
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="facility_type">{messages.facilityType}</label>
          <select
            id="facility_type"
            name="facility_type"
            defaultValue={filters.facility_type ?? ""}
          >
            <option value="">{messages.facilityTypeAll}</option>
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
          {messages.applyFilters}
        </button>
        <Link className="text-link" href={`/procedures/${slug}/prices`}>
          {messages.clearFilters}
        </Link>
      </form>
    );

    return (
      <main>
        <PopularSearches
          locale={locale}
          heading={messages.popular}
          viewAllLabel={messages.viewAllProcedures}
        />
        <nav className="breadcrumbs" aria-label={messages.breadcrumb}>
          <Link href="/">{messages.home}</Link>
          <span>/</span>
          <Link href="/procedures">{messages.procedures}</Link>
          <span>/</span>
          <Link href={`/procedures/${slug}`}>{procedure.consumer_name}</Link>
          <span>/</span>
          <span>{messages.comparePrices}</span>
        </nav>
        <div className="page-heading comparison-heading">
          <p className="eyebrow">{messages.compareServiceLocations}</p>
          <h1>{procedure.consumer_name}</h1>
          <p className="lede">
            {messages.ledeSummary.replace("{region}", launchRegion.name)}
          </p>
        </div>
        <dl
          className="decision-context"
          aria-label={messages.comparisonContext}
        >
          <div>
            <dt>{messages.location}</dt>
            <dd>{filters.location || launchRegion.name}</dd>
          </div>
          <div>
            <dt>{messages.coverage}</dt>
            <dd>
              {payerName
                ? `${payerName}${planName ? ` · ${planName}` : ""}`
                : `${messages.selfPay} · ${messages.chooseInsurance}`}
            </dd>
          </div>
        </dl>
        <CoverageNotice messages={messages}>
          {filters.payer && data.facilities_with_prices === 0
            ? messages.coverageNoRateForPayer.replace(
                "{payer}",
                payerName ?? messages.thisPayer,
              )
            : messages.coveragePublishedSummary
                .replace("{withPrices}", String(data.facilities_with_prices))
                .replace("{active}", String(data.active_facilities))}
        </CoverageNotice>
        <div className="toolbar comparison-toolbar">
          <strong>
            {(items.length === 1
              ? messages.serviceLocationCountOne
              : messages.serviceLocationCountOther
            ).replace("{count}", String(items.length))}
            {activeFilterCount
              ? ` · ${(activeFilterCount === 1
                  ? messages.activeFilterCountOne
                  : messages.activeFilterCountOther
                ).replace("{count}", String(activeFilterCount))}`
              : ""}
          </strong>
          <form className="sort-form">
            {Object.entries(filters)
              .filter(([key, value]) => key !== "sort" && value)
              .map(([key, value]) => (
                <input key={key} type="hidden" name={key} value={value} />
              ))}
            <label htmlFor="sort">{messages.sortLabel}</label>
            <select
              id="sort"
              name="sort"
              defaultValue={filters.sort ?? "recommended"}
            >
              <option value="recommended">{messages.sortRecommended}</option>
              <option value="distance">{messages.nearestFirst}</option>
              <option value="cash">{messages.sortLowestCash}</option>
              <option value="rating">{messages.sortHighestRating}</option>
              <option value="name">{messages.sortHospitalName}</option>
            </select>
            <button className="button secondary">{messages.apply}</button>
          </form>
        </div>
        <FilterPanel messages={messages}>{filterForm}</FilterPanel>
        <div className="marketplace-results-layout">
          <section
            className="result-list"
            aria-label={messages.facilityResults}
          >
            {items.length === 0 ? (
              <EmptyState title={messages.noHospitalsMatch}>
                <p>{messages.emptyStateHelp}</p>
                <div className="card-actions">
                  <Link
                    className="button secondary"
                    href={`/procedures/${slug}/prices`}
                  >
                    {messages.clearAllFilters}
                  </Link>
                  {filters.payer && (
                    <Link
                      className="button secondary"
                      href={`/procedures/${slug}/prices?availability=${filters.availability ?? ""}`}
                    >
                      {messages.clearPayer}
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
                  planName={planName}
                  planId={filters.plan}
                  messages={messages}
                  locale={locale}
                />
              ))
            )}
          </section>
          <InlineComparePanel
            procedureSlug={slug}
            procedureName={procedure.consumer_name}
            items={items}
            payer={filters.payer}
            plan={filters.plan}
            locale={locale}
          />
        </div>
        <PricingDisclaimer messages={messages} />
        <CompareTray
          procedureSlug={slug}
          payer={filters.payer}
          plan={filters.plan}
          locale={locale}
        />
      </main>
    );
  } catch {
    return (
      <main>
        <ErrorState
          retryHref={`/procedures/${slug}/prices`}
          messages={messages}
        />
      </main>
    );
  }
}

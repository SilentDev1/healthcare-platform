import Link from "next/link";
import {
  apiGet,
  type ProcedureComparison,
  type ProcedureComparisonItem,
} from "../../lib/api";
import {
  ComparisonFacilityCard,
  EmptyState,
  ErrorState,
  PricingDisclaimer,
} from "./ui";
import { CompareTray } from "./CompareSelect";
import { launchRegion } from "../../lib/brand";
import { localePath, type Locale, type Messages } from "../../lib/i18n";
import { experienceMessages } from "../../lib/experience-i18n";

export interface ProcedureResultsFilters {
  location?: string;
  radius?: string;
  setting?: string;
  payer?: string;
  plan?: string;
  facility_type?: string;
  availability?: string;
  rating?: string;
  sort?: string;
  /** "self" = self-pay/uninsured mode: lead with published cash prices. */
  pay?: string;
  view?: string;
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

/**
 * The shared hospital-shopping experience for a procedure: location/insurance/
 * sort filters, the actual matching facility/service-location result cards
 * (with verified imagery, comparability-safe prices, distance, and savings),
 * the side-by-side compare panel, and the mobile compare tray.
 *
 * Rendered on BOTH the procedure detail page (`/procedures/[slug]`) and the
 * dedicated results page (`/procedures/[slug]/prices`) so the user never has to
 * leave a page to discover which hospitals published a price. State-neutral:
 * `location`/`radius`/`payer`/`setting` drive the query, not a hardcoded state.
 * `basePath` is the current page path so "clear"/empty-state links stay on it.
 */
export async function ProcedureResults({
  slug,
  procedureName,
  filters,
  locale,
  messages,
  basePath,
}: {
  slug: string;
  procedureName: string;
  filters: ProcedureResultsFilters;
  locale: Locale;
  messages: Messages;
  basePath: string;
}) {
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

  const clearHref = localePath(locale, basePath);

  let data: ProcedureComparison;
  let payers: Array<{ slug: string; name: string }>;
  let plans: Array<{ id: string; name: string }>;
  try {
    [data, payers, plans] = await Promise.all([
      apiGet<ProcedureComparison>(
        `/api/v1/procedures/${encodeURIComponent(slug)}/comparison?${query}`,
      ),
      apiGet<Array<{ slug: string; name: string }>>("/api/v1/pricing/payers"),
      filters.payer
        ? apiGet<Array<{ id: string; name: string }>>(
            `/api/v1/pricing/plans?payer=${encodeURIComponent(filters.payer)}`,
          )
        : Promise.resolve([]),
    ]);
  } catch {
    return <ErrorState retryHref={clearHref} messages={messages} />;
  }

  // Default to showing priced facilities first — Carevero is a price-comparison
  // product, so consumers should first see facilities with actual prices.
  const effectiveAvailability = filters.availability ?? "available";

  let items = data.items.filter((item) => {
    if (effectiveAvailability === "available" && !item.price_available)
      return false;
    if (effectiveAvailability === "unavailable" && item.price_available)
      return false;
    if (
      filters.facility_type &&
      item.facility_type?.toLowerCase() !== filters.facility_type.toLowerCase()
    )
      return false;
    if (
      filters.rating &&
      Number(item.cms_overall_rating ?? 0) < Number(filters.rating)
    )
      return false;
    return true;
  });
  // Self-pay / uninsured mode: default to cash-lowest ordering (an explicit sort
  // still wins). This only reorders — it never hides providers and never relabels
  // a negotiated rate as a cash price.
  const selfPay = filters.pay === "self";
  const effectiveSort = selfPay && !filters.sort ? "cash" : filters.sort;
  items = sortItems(items, effectiveSort);
  const buildResultsHref = (overrides: Record<string, string | undefined>) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...filters, ...overrides })) {
      if (value) params.set(key, String(value));
    }
    const qs = params.toString();
    return localePath(locale, qs ? `${basePath}?${qs}` : basePath);
  };
  const facilityTypes = Array.from(
    new Set(data.items.map((item) => item.facility_type).filter(Boolean)),
  ).sort() as string[];
  const payerName = filters.payer
    ? payers.find((payer) => payer.slug === filters.payer)?.name
    : undefined;
  const planName = filters.plan
    ? plans.find((plan) => plan.id === filters.plan)?.name
    : undefined;
  const chipLabels: Record<string, string | undefined> = {
    location: filters.location,
    facility_type: filters.facility_type,
    pay: filters.pay === "self" ? messages.selfPay : undefined,
    payer: payerName,
    plan: planName,
    availability:
      filters.availability === "unavailable"
        ? messages.availabilityUnavailable
        : filters.availability === "available"
          ? messages.availabilityAvailable
          : undefined,
    setting: filters.setting?.replaceAll("_", " "),
    radius: filters.radius
      ? `${filters.radius} ${messages.milesUnit}`
      : undefined,
    rating: filters.rating ? `${filters.rating}+ CMS` : undefined,
  };
  const activeChips = Object.entries(chipLabels).filter(
    (entry): entry is [string, string] => Boolean(entry[1]),
  );
  const activeFilterCount = activeChips.length;

  const filterForm = (
    <form className="filter-form persistent-filter-form">
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
        <label htmlFor="availability">{messages.priceAvailability}</label>
        <select
          id="availability"
          name="availability"
          defaultValue={filters.availability ?? "available"}
        >
          <option value="available">{messages.availabilityAvailable}</option>
          <option value="">{messages.availabilityAll}</option>
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
      {filters.sort && <input type="hidden" name="sort" value={filters.sort} />}
      {filters.pay && <input type="hidden" name="pay" value={filters.pay} />}
      <button className="button" type="submit">
        {messages.applyFilters}
      </button>
      <Link className="text-link" href={clearHref}>
        {messages.clearFilters}
      </Link>
    </form>
  );

  const hospitalsWithPricesLabel =
    items.length === 1
      ? experienceMessages[locale].providerOne
      : experienceMessages[locale].providerMany.replace(
          "{count}",
          String(items.length),
        );
  const matchingLocationsLabel =
    items.length === 1
      ? experienceMessages[locale].providerOne
      : experienceMessages[locale].providerMany.replace(
          "{count}",
          String(items.length),
        );

  return (
    <>
      <div className="section-heading" style={{ marginBottom: "0.6rem" }}>
        <p className="eyebrow">{messages.pricesNearYou}</p>
        <h2>{hospitalsWithPricesLabel}</h2>
      </div>
      <div className={`selfpay-banner${selfPay ? " is-active" : ""}`}>
        <div>
          <strong>{messages.selfPayTitle}</strong>{" "}
          <span>{selfPay ? messages.selfPayBody : messages.selfPayPrompt}</span>
        </div>
        {selfPay ? (
          <Link
            className="text-link"
            href={buildResultsHref({ pay: undefined })}
          >
            {messages.selfPayShowAll}
          </Link>
        ) : (
          <Link
            className="button secondary"
            href={buildResultsHref({ pay: "self" })}
          >
            {messages.selfPayShowCash}
          </Link>
        )}
      </div>
      <p className="results-count">
        <span className="results-secondary">{matchingLocationsLabel}</span>
        {activeFilterCount
          ? ` · ${(activeFilterCount === 1
              ? messages.activeFilterCountOne
              : messages.activeFilterCountOther
            ).replace("{count}", String(activeFilterCount))}`
          : ""}
      </p>
      <div className="results-controls sticky-results-controls">
        {filterForm}
        <form className="results-sort-form">
          {Object.entries(filters)
            .filter(
              ([key, value]) => key !== "sort" && key !== "radius" && value,
            )
            .map(([key, value]) => (
              <input key={key} type="hidden" name={key} value={value} />
            ))}
          <label className="control-field">
            <span>{messages.distanceRadius}</span>
            <select name="radius" defaultValue={filters.radius ?? ""}>
              <option value="">{messages.anyDistance}</option>
              <option value="10">10 {messages.milesUnit}</option>
              <option value="25">25 {messages.milesUnit}</option>
              <option value="50">50 {messages.milesUnit}</option>
              <option value="100">100 {messages.milesUnit}</option>
            </select>
          </label>
          <label className="control-field">
            <span>{messages.sortLabel}</span>
            <select name="sort" defaultValue={effectiveSort ?? "recommended"}>
              <option value="recommended">{messages.sortRecommended}</option>
              <option value="distance">{messages.nearestFirst}</option>
              <option value="cash">{messages.sortLowestCash}</option>
              <option value="rating">{messages.sortHighestRating}</option>
              <option value="name">{messages.sortHospitalName}</option>
            </select>
          </label>
          <button className="button secondary">{messages.apply}</button>
        </form>
        {activeChips.length ? (
          <div
            className="active-filter-row"
            aria-label={messages.filterResultsSummary}
          >
            {activeChips.map(([key, label]) => (
              <Link
                key={key}
                className="active-filter-chip"
                href={buildResultsHref({ [key]: undefined })}
                aria-label={`${messages.clearFilters}: ${label}`}
              >
                {label} <span aria-hidden="true">×</span>
              </Link>
            ))}
            <Link className="clear-filter-chips" href={clearHref}>
              {messages.clearAllFilters}
            </Link>
          </div>
        ) : null}
      </div>
      <div className="marketplace-results-layout single-column-results">
        <section className="result-list" aria-label={messages.facilityResults}>
          {items.length === 0 ? (
            <EmptyState title={messages.noHospitalsMatch}>
              <p>{messages.emptyStateHelp}</p>
              <div className="card-actions">
                <Link className="button secondary" href={clearHref}>
                  {messages.clearAllFilters}
                </Link>
              </div>
            </EmptyState>
          ) : (
            items
              .slice(0, filters.view === "all" ? items.length : 5)
              .map((item) => (
                <ComparisonFacilityCard
                  key={`${item.facility_id}-${item.facility_location_id}`}
                  item={item}
                  procedureName={procedureName}
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
      </div>
      {items.length > 5 && filters.view !== "all" ? (
        <div className="see-all-results">
          <Link
            className="button secondary"
            href={buildResultsHref({ view: "all" })}
          >
            {experienceMessages[locale].seeAll.replace(
              "{count}",
              String(items.length),
            )}
          </Link>
        </div>
      ) : null}
      <PricingDisclaimer messages={messages} />
      <CompareTray
        procedureSlug={slug}
        payer={filters.payer}
        plan={filters.plan}
        locale={locale}
      />
    </>
  );
}

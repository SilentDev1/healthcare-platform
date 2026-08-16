import Link from "next/link";
import type { Metadata } from "next";
import { apiGet, type FacilityDirectory } from "../../lib/api";
import { FacilityImage } from "../components/FacilityImage";
import { FilterPanel } from "../components/ui";
import { capabilityLabel, localePath, type Locale, type Messages } from "../../lib/i18n";
import { requestLocale, requestMessages } from "../../lib/i18n-server";

export const metadata: Metadata = {
  title: "Hospitals",
  description:
    "Search and browse hospitals by state, city, pricing availability, and facility type.",
  alternates: { canonical: "/hospitals" },
};

interface Filters {
  state?: string;
  city?: string;
  search?: string;
  pricing?: string;
  type?: string;
  capability?: string;
  sort?: string;
  page?: string;
}

const PAGE_SIZE = 24;

/** Hospital-only fields (CMS quality) must never render for non-hospital locations. */
function isHospital(facility: {
  capabilities: string[];
  organization_type?: string | null;
  cms_certification_number: string | null;
}): boolean {
  return (
    facility.capabilities.includes("hospital") ||
    facility.organization_type === "hospital_system" ||
    facility.cms_certification_number !== null
  );
}

/** Localize a US state name from its code, falling back to the API-supplied name. */
function stateName(code: string | null, name: string, t: Messages): string {
  if (!code) return name;
  const key = `state${code.toUpperCase()}` as keyof Messages;
  const localized = t[key];
  return typeof localized === "string" ? localized : name;
}

function pricingSummary(count: number, t: Messages): string {
  if (count <= 0) return t.hospDirNoPricingYet;
  const template =
    count === 1 ? t.hospDirProceduresPublishedOne : t.hospDirProceduresPublished;
  return template.replace("{count}", String(count));
}

export default async function Hospitals({
  searchParams,
}: {
  searchParams: Promise<Filters>;
}) {
  const locale = await requestLocale();
  const t = await requestMessages();
  const filters = await searchParams;
  const page = Math.max(1, Number(filters.page) || 1);

  const query = new URLSearchParams();
  query.set("page", String(page));
  query.set("page_size", String(PAGE_SIZE));
  if (filters.state) query.set("state", filters.state);
  if (filters.city) query.set("city", filters.city);
  if (filters.search) query.set("search", filters.search);
  if (filters.pricing) query.set("pricing_status", filters.pricing);
  if (filters.type) query.set("facility_type", filters.type);
  if (filters.capability) query.set("capability", filters.capability);
  if (filters.sort) query.set("sort", filters.sort);

  let data: FacilityDirectory;
  try {
    data = await apiGet<FacilityDirectory>(`/api/v1/facilities/directory?${query}`);
  } catch {
    return (
      <main>
        <h1>{t.hospDirUnavailableTitle}</h1>
        <p className="error">{t.hospDirUnavailable}</p>
      </main>
    );
  }

  const selectedStateName = filters.state
    ? stateName(
        filters.state,
        data.states.find((s) => s.code === filters.state?.toUpperCase())?.name ??
          filters.state,
        t,
      )
    : null;
  const countLabel = selectedStateName
    ? t.hospDirCountIn
        .replace("{count}", String(data.total))
        .replace("{state}", selectedStateName)
    : data.total_states > 1
      ? t.hospDirCountAcross
          .replace("{count}", String(data.total))
          .replace("{states}", String(data.total_states))
      : t.hospDirCountAll.replace("{count}", String(data.total));

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const pageHref = (nextPage: number) => {
    const params = new URLSearchParams();
    if (filters.state) params.set("state", filters.state);
    if (filters.city) params.set("city", filters.city);
    if (filters.search) params.set("search", filters.search);
    if (filters.pricing) params.set("pricing", filters.pricing);
    if (filters.type) params.set("type", filters.type);
    if (filters.capability) params.set("capability", filters.capability);
    if (filters.sort) params.set("sort", filters.sort);
    if (nextPage > 1) params.set("page", String(nextPage));
    const qs = params.toString();
    return localePath(locale, `/hospitals${qs ? `?${qs}` : ""}`);
  };

  const filterForm = (
    <form className="hospdir-filter-form" method="get">
      <div className="filter-group">
        <label htmlFor="state">{t.hospDirStateLabel}</label>
        <select id="state" name="state" defaultValue={filters.state ?? ""}>
          <option value="">{t.hospDirAllStates}</option>
          {data.states.map((s) => (
            <option key={s.code} value={s.code}>
              {stateName(s.code, s.name, t)} ({s.facility_count})
            </option>
          ))}
        </select>
      </div>
      <div className="filter-group">
        <label htmlFor="pricing">{t.priceAvailability}</label>
        <select id="pricing" name="pricing" defaultValue={filters.pricing ?? ""}>
          <option value="">{t.availabilityAll}</option>
          <option value="pricing_available">{t.mapPricingAvailable}</option>
          <option value="limited_pricing">{t.mapLimitedPricing}</option>
          <option value="pricing_not_available_yet">{t.mapNotAvailableYet}</option>
        </select>
      </div>
      {data.capabilities.length > 0 ? (
        <div className="filter-group">
          <label htmlFor="capability">{t.providerType}</label>
          <select
            id="capability"
            name="capability"
            defaultValue={filters.capability ?? ""}
          >
            <option value="">{t.providerTypeAll}</option>
            {data.capabilities.map((option) => (
              <option key={option.capability} value={option.capability}>
                {capabilityLabel(option.capability, locale)} ({option.location_count})
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <div className="filter-group">
        <label htmlFor="type">{t.facilityType}</label>
        <select id="type" name="type" defaultValue={filters.type ?? ""}>
          <option value="">{t.facilityTypeAll}</option>
          {data.facility_types.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>
      <div className="filter-group">
        <label htmlFor="sort">{t.sortLabel}</label>
        <select id="sort" name="sort" defaultValue={filters.sort ?? "name"}>
          <option value="name">{t.sortHospitalName}</option>
          <option value="city">{t.hospDirSortCity}</option>
          <option value="pricing">{t.hospDirSortPricing}</option>
        </select>
      </div>
      {filters.search ? (
        <input type="hidden" name="search" value={filters.search} />
      ) : null}
      <button className="button" type="submit">
        {t.applyFilters}
      </button>
      <Link className="text-link" href={localePath(locale, "/hospitals")}>
        {t.clearAllFilters}
      </Link>
    </form>
  );

  return (
    <main>
      <nav className="breadcrumbs" aria-label={t.breadcrumb}>
        <Link href={localePath(locale, "/")}>{t.home}</Link>
        <span>/</span>
        <span>{t.hospitals}</span>
      </nav>
      <p className="eyebrow">{t.hospDirEyebrow}</p>
      <h1>{t.hospDirTitle}</h1>
      <p className="lede">{t.hospDirLede}</p>

      {/* Search + filters (search is its own always-visible field) */}
      <form className="hospdir-search" method="get" role="search">
        {filters.state ? (
          <input type="hidden" name="state" value={filters.state} />
        ) : null}
        {filters.pricing ? (
          <input type="hidden" name="pricing" value={filters.pricing} />
        ) : null}
        {filters.type ? (
          <input type="hidden" name="type" value={filters.type} />
        ) : null}
        {filters.capability ? (
          <input type="hidden" name="capability" value={filters.capability} />
        ) : null}
        {filters.sort ? (
          <input type="hidden" name="sort" value={filters.sort} />
        ) : null}
        <label className="sr-only" htmlFor="hospdir-search-input">
          {t.hospDirSearch}
        </label>
        <input
          id="hospdir-search-input"
          type="search"
          name="search"
          defaultValue={filters.search ?? ""}
          placeholder={t.hospDirSearchPlaceholder}
          autoComplete="off"
        />
        <button className="button" type="submit">
          {t.hospDirSearch}
        </button>
      </form>

      <div className="results-controls">
        <FilterPanel messages={t}>{filterForm}</FilterPanel>
        <p className="results-count hospdir-count">
          <strong>{countLabel}</strong>
        </p>
      </div>

      {data.items.length === 0 ? (
        <section className="state-card">
          <span className="state-icon" aria-hidden="true">
            ○
          </span>
          <h2>{t.hospDirNoResults}</h2>
          <div className="state-body">
            <p>{t.hospDirNoResultsHelp}</p>
            <Link className="button secondary" href={localePath(locale, "/hospitals")}>
              {t.clearAllFilters}
            </Link>
          </div>
        </section>
      ) : (
        <div className="hospdir-grid">
          {data.items.map((facility) => (
            <article className="hospdir-card" key={facility.id}>
              <FacilityImage
                name={facility.display_name}
                imageUrl={facility.image_url}
                imageAlt={
                  facility.image_url
                    ? (facility.image_alt ??
                      t.imageAltPhotoOf.replace(
                        "{hospital}",
                        facility.display_name,
                      ))
                    : undefined
                }
                attribution={facility.image_attribution ?? undefined}
                placeholderLabel={t.imageNoPhoto}
                variant="card"
                className="hospdir-card-media"
              />
              <div className="hospdir-card-body">
                <h2>
                  <Link href={localePath(locale, `/hospitals/${facility.id}`)}>
                    {facility.display_name}
                  </Link>
                </h2>
                {facility.organization_name &&
                facility.organization_name !== facility.display_name ? (
                  <p className="hospdir-card-org">{facility.organization_name}</p>
                ) : null}
                <p className="hospdir-card-loc">
                  {facility.city ? `${facility.city}, ` : ""}
                  {stateName(facility.state, facility.state ?? "", t)}
                </p>
                {facility.capabilities.length > 0 ? (
                  <p className="hospdir-card-caps">
                    {facility.capabilities.map((capability) => (
                      <span className="badge neutral" key={capability}>
                        {capabilityLabel(capability, locale)}
                      </span>
                    ))}
                  </p>
                ) : facility.facility_type ? (
                  <span className="badge neutral">{facility.facility_type}</span>
                ) : null}
                <p className="hospdir-card-pricing">
                  {facility.price_available
                    ? pricingSummary(facility.published_procedure_count, t)
                    : t.priceNotAvailableShort}
                </p>
                {/* CMS hospital quality is HOSPITAL-ONLY; never shown for labs/urgent care/etc. */}
                {isHospital(facility) &&
                facility.cms_overall_rating &&
                /^[1-5]$/.test(facility.cms_overall_rating) ? (
                  <p className="hospdir-card-cms">
                    <span aria-hidden="true">★</span> {t.hospDirCmsOverall}:{" "}
                    {facility.cms_overall_rating}/5
                  </p>
                ) : null}
                <Link
                  className="button secondary"
                  href={localePath(locale, `/hospitals/${facility.id}`)}
                >
                  {t.hospDirViewHospital}
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}

      {totalPages > 1 ? (
        <nav className="hospdir-pagination" aria-label={t.hospitals}>
          {page > 1 ? (
            <Link className="button secondary" href={pageHref(page - 1)}>
              ← {t.hospDirPrev}
            </Link>
          ) : (
            <span className="button secondary disabled" aria-disabled="true">
              ← {t.hospDirPrev}
            </span>
          )}
          <span className="hospdir-page-of">
            {t.hospDirPageOf
              .replace("{page}", String(page))
              .replace("{total}", String(totalPages))}
          </span>
          {page < totalPages ? (
            <Link className="button secondary" href={pageHref(page + 1)}>
              {t.hospDirNext} →
            </Link>
          ) : (
            <span className="button secondary disabled" aria-disabled="true">
              {t.hospDirNext} →
            </span>
          )}
        </nav>
      ) : null}
    </main>
  );
}

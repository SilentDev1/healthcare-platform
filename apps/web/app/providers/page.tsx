import Link from "next/link";
import type { Metadata } from "next";
import { apiGet, type FacilityDirectory } from "../../lib/api";
import { FacilityImage } from "../components/FacilityImage";
import { DirectoryControls } from "../components/DirectoryControls";
import { DirectoryMap } from "../components/DirectoryMap";
import { capabilityLabel, localePath, type Messages } from "../../lib/i18n";
import { directoryMessages } from "../../lib/directory-i18n";
import { launchRegion } from "../../lib/brand";
import { requestLocale, requestMessages } from "../../lib/i18n-server";

export const metadata: Metadata = {
  title: "Providers",
  description:
    "Find healthcare providers — hospitals, labs, urgent care, imaging, surgery centers, physical therapy and more — by type, region, and published-price availability.",
  alternates: { canonical: "/providers" },
};

interface Filters {
  state?: string;
  region?: string;
  q?: string;
  has?: string;
  capability?: string;
  sort?: string;
  view?: string;
  page?: string;
  size?: string;
}

const PAGE_SIZES = [12, 24, 48];
const DEFAULT_SIZE = 24;

/** Hospital-only fields (CMS quality) must never render for non-hospital locations. */
function isHospital(f: {
  capabilities: string[];
  organization_type?: string | null;
  cms_certification_number: string | null;
}): boolean {
  return (
    f.capabilities.includes("hospital") ||
    f.organization_type === "hospital_system" ||
    f.cms_certification_number !== null
  );
}

function stateName(code: string | null, name: string, t: Messages): string {
  if (!code) return name;
  const key = `state${code.toUpperCase()}` as keyof Messages;
  const v = t[key];
  return typeof v === "string" ? v : name;
}

export default async function Providers({
  searchParams,
}: {
  searchParams: Promise<Filters>;
}) {
  const locale = await requestLocale();
  const t = await requestMessages();
  const d = directoryMessages[locale] ?? directoryMessages.en;
  const filters = await searchParams;

  const page = Math.max(1, Number(filters.page) || 1);
  const size = PAGE_SIZES.includes(Number(filters.size))
    ? Number(filters.size)
    : DEFAULT_SIZE;
  const state = (filters.state || launchRegion.state).toUpperCase();
  const view = ["list", "grid", "map"].includes(filters.view ?? "")
    ? (filters.view as "list" | "grid" | "map")
    : "list";

  const query = new URLSearchParams();
  query.set("page", String(page));
  query.set("page_size", String(size));
  query.set("state", state);
  if (filters.region) query.set("region", filters.region);
  if (filters.q) query.set("search", filters.q);
  if (filters.capability) query.set("capability", filters.capability);
  if (filters.sort === "name_desc") query.set("sort", "name_desc");
  // Provider-neutral price-availability filter (default Any never hides providers).
  if (filters.has === "yes") query.set("price_available", "true");
  else if (filters.has === "no") query.set("price_available", "false");

  let data: FacilityDirectory;
  try {
    data = await apiGet<FacilityDirectory>(`/api/v1/facilities/directory?${query}`);
  } catch {
    return (
      <main>
        <h1>{d.unavailableTitle}</h1>
        <p className="error">{d.unavailable}</p>
      </main>
    );
  }

  const stateOptions = data.states.map((s) => ({
    value: s.code,
    label: `${stateName(s.code, s.name, t)} (${s.facility_count})`,
  }));
  const regionOptions = (data.regions ?? []).map((r) => ({
    value: r.region,
    label: `${r.region} (${r.location_count})`,
  }));
  const allCount =
    data.states.find((s) => s.code === state)?.facility_count ?? data.total;
  // Most-common provider types become the primary quick-filter chips; the rest fall
  // under "More". Sorted by real location counts (never a hardcoded list).
  const capabilitiesByCount = [...data.capabilities].sort(
    (a, b) => b.location_count - a.location_count,
  );

  const total = data.total;
  const totalPages = Math.max(1, Math.ceil(total / size));
  const from = total === 0 ? 0 : (page - 1) * size + 1;
  const to = Math.min(page * size, total);
  const typeLabel = filters.capability
    ? capabilityLabel(filters.capability, locale)
    : "";
  const countLabel = filters.capability
    ? d.showingTyped
        .replace("{from}", String(from))
        .replace("{to}", String(to))
        .replace("{total}", String(total))
        .replace("{type}", typeLabel)
    : d.showing
        .replace("{from}", String(from))
        .replace("{to}", String(to))
        .replace("{total}", String(total));

  const hrefWith = (over: Partial<Filters>): string => {
    const p = new URLSearchParams();
    const merged: Filters = { ...filters, ...over };
    if (merged.state && merged.state.toUpperCase() !== launchRegion.state)
      p.set("state", merged.state);
    if (merged.region) p.set("region", merged.region);
    if (merged.q) p.set("q", merged.q);
    if (merged.capability) p.set("capability", merged.capability);
    if (merged.sort && merged.sort !== "name") p.set("sort", merged.sort);
    if (merged.has) p.set("has", merged.has);
    if (merged.view && merged.view !== "list") p.set("view", merged.view);
    if (merged.size && Number(merged.size) !== DEFAULT_SIZE)
      p.set("size", String(merged.size));
    if (merged.page && Number(merged.page) > 1) p.set("page", String(merged.page));
    const qs = p.toString();
    return localePath(locale, `/providers${qs ? `?${qs}` : ""}`);
  };

  const priceLine = (f: FacilityDirectory["items"][number]) => {
    if (!f.price_available) return d.priceNotAvailable;
    const tpl =
      f.published_procedure_count === 1 ? d.publishedPricesOne : d.publishedPrices;
    return tpl.replace("{count}", String(f.published_procedure_count));
  };
  const capBadges = (f: FacilityDirectory["items"][number]) =>
    f.capabilities.map((c) => (
      <span className="badge neutral" key={c}>
        {capabilityLabel(c, locale)}
      </span>
    ));
  const cms = (f: FacilityDirectory["items"][number]) =>
    isHospital(f) && f.cms_overall_rating && /^[1-5]$/.test(f.cms_overall_rating) ? (
      <span className="pd-cms">
        <span aria-hidden="true">★</span> {d.cmsOverall}: {f.cms_overall_rating}/5
      </span>
    ) : null;

  // Compact page-number window around the current page.
  const pageWindow: number[] = [];
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, start + 4);
  for (let i = start; i <= end; i += 1) pageWindow.push(i);

  return (
    <main className="pd-main">
      <nav className="breadcrumbs" aria-label={d.eyebrow}>
        <Link href={localePath(locale, "/")}>{t.home}</Link>
        <span>/</span>
        <span>{d.navLabel}</span>
      </nav>

      <header className="pd-header">
        <p className="eyebrow">{d.eyebrow}</p>
        <h1>{d.title}</h1>
        <p className="lede">{d.lede}</p>
        <ul className="pd-trust" aria-label={d.verifiedData}>
          <li>
            <span aria-hidden="true">✓</span> {d.free}
          </li>
          <li>
            <span aria-hidden="true">✓</span> {d.noAccount}
          </li>
          <li>
            <span aria-hidden="true">✓</span> {d.verifiedData}
          </li>
        </ul>
      </header>

      <DirectoryControls
        locale={locale}
        t={d}
        current={{
          q: filters.q ?? "",
          capability: filters.capability ?? "",
          region: filters.region ?? "",
          has: filters.has ?? "",
          sort: filters.sort === "name_desc" ? "name_desc" : "name",
          state,
          view,
          size: String(size),
        }}
        allCount={allCount}
        states={stateOptions}
        regions={regionOptions}
        capabilities={capabilitiesByCount}
        quickCount={total}
      />

      <div className="pd-resultbar">
        <p className="pd-count">
          <strong>{countLabel}</strong>
        </p>
        {view !== "map" ? (
          <p className="pd-perpage">
            {PAGE_SIZES.map((n) => (
              <Link
                key={n}
                className={`pd-perpage-opt${n === size ? " pd-perpage-on" : ""}`}
                href={hrefWith({ size: String(n), page: "1" })}
              >
                {d.perPage.replace("{count}", String(n))}
              </Link>
            ))}
          </p>
        ) : null}
      </div>

      {view === "map" ? (
        <DirectoryMap
          locale={locale}
          t={d}
          state={state}
          capability={filters.capability ?? ""}
          region={filters.region ?? ""}
          center={launchRegion.mapCenter}
          zoom={launchRegion.mapZoom}
          detailBase="/providers"
        />
      ) : data.items.length === 0 ? (
        <section className="state-card">
          <span className="state-icon" aria-hidden="true">
            ○
          </span>
          <h2>{d.noResults}</h2>
          <div className="state-body">
            <p>{d.noResultsHelp}</p>
            <Link className="button secondary" href={localePath(locale, "/providers")}>
              {d.clear}
            </Link>
          </div>
        </section>
      ) : view === "grid" ? (
        <div className="pd-grid">
          {data.items.map((f) => (
            <article className="pd-card" key={f.id}>
              <FacilityImage
                name={f.display_name}
                imageUrl={f.image_url}
                imageAlt={f.image_url ? (f.image_alt ?? undefined) : undefined}
                attribution={f.image_attribution ?? undefined}
                placeholderLabel={d.verifiedData}
                variant="card"
                className="pd-card-media"
              />
              <div className="pd-card-body">
                <h2 className="pd-card-name">
                  <Link href={localePath(locale, `/providers/${f.id}`)}>
                    {f.display_name}
                  </Link>
                </h2>
                {f.organization_name && f.organization_name !== f.display_name ? (
                  <p className="pd-card-org">{f.organization_name}</p>
                ) : null}
                <p className="pd-card-loc">
                  {f.city ? `${f.city}, ` : ""}
                  {stateName(f.state, f.state ?? "", t)}
                </p>
                <p className="pd-card-caps">{capBadges(f)}</p>
                <p className="pd-card-price">{priceLine(f)}</p>
                {cms(f)}
                <Link
                  className="button secondary pd-card-cta"
                  href={localePath(locale, `/providers/${f.id}`)}
                >
                  {d.viewProvider} →
                </Link>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <ul className="pd-list">
          {data.items.map((f) => (
            <li className="pd-item" key={f.id}>
              <FacilityImage
                name={f.display_name}
                imageUrl={f.image_url}
                imageAlt={f.image_url ? (f.image_alt ?? undefined) : undefined}
                attribution={f.image_attribution ?? undefined}
                placeholderLabel={d.verifiedData}
                variant="thumb"
                className="pd-item-media"
              />
              <div className="pd-item-body">
                <Link className="pd-item-name" href={localePath(locale, `/providers/${f.id}`)}>
                  {f.display_name}
                </Link>
                {f.organization_name && f.organization_name !== f.display_name ? (
                  <span className="pd-item-org">{f.organization_name}</span>
                ) : null}
                <span className="pd-item-loc">
                  {f.city ? `${f.city}, ` : ""}
                  {stateName(f.state, f.state ?? "", t)}
                </span>
              </div>
              <div className="pd-item-caps">{capBadges(f)}</div>
              <div className="pd-item-price">
                <span>{priceLine(f)}</span>
                {cms(f)}
              </div>
              <Link className="pd-item-cta" href={localePath(locale, `/providers/${f.id}`)}>
                {d.viewProvider} →
              </Link>
            </li>
          ))}
        </ul>
      )}

      {view !== "map" && totalPages > 1 ? (
        <nav className="pd-pagination" aria-label={d.paginationLabel}>
          {page > 1 ? (
            <Link className="pd-page pd-page-prev" href={hrefWith({ page: String(page - 1) })}>
              ← {d.prev}
            </Link>
          ) : (
            <span className="pd-page pd-page-prev pd-disabled" aria-disabled="true">
              ← {d.prev}
            </span>
          )}
          {start > 1 ? <span className="pd-page-gap">…</span> : null}
          {pageWindow.map((n) => (
            <Link
              key={n}
              className={`pd-page${n === page ? " pd-page-on" : ""}`}
              aria-current={n === page ? "page" : undefined}
              href={hrefWith({ page: String(n) })}
            >
              {n}
            </Link>
          ))}
          {end < totalPages ? <span className="pd-page-gap">…</span> : null}
          {page < totalPages ? (
            <Link className="pd-page pd-page-next" href={hrefWith({ page: String(page + 1) })}>
              {d.next} →
            </Link>
          ) : (
            <span className="pd-page pd-page-next pd-disabled" aria-disabled="true">
              {d.next} →
            </span>
          )}
        </nav>
      ) : null}
    </main>
  );
}

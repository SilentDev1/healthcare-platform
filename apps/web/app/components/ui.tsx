import Link from "next/link";
import type { PriceSummary, ProcedureComparisonItem } from "../../lib/api";
import { CompareSelect } from "./CompareSelect";

export function Money({ value }: { value: string | null }) {
  const amount = value === null ? Number.NaN : Number(value);
  if (!Number.isFinite(amount) || amount < 0)
    return <span className="muted">Not available</span>;
  return (
    <>
      {new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(amount)}
    </>
  );
}

export function PriceRange({
  min,
  max,
}: {
  min: string | null;
  max: string | null;
}) {
  if (min === null && max === null)
    return <span className="price-missing">Price not currently available</span>;
  if (min === max || max === null) return <Money value={min} />;
  return (
    <>
      <Money value={min} />–<Money value={max} />
    </>
  );
}

export function QualityRating({ value }: { value?: string | null }) {
  const rating = value && /^[1-5](?:\.0+)?$/.test(value) ? Number(value) : null;
  return (
    <span
      className="quality-rating"
      aria-label={
        rating
          ? `CMS overall rating: ${rating} out of 5`
          : "CMS overall rating not available"
      }
    >
      <span aria-hidden="true">★</span>{" "}
      {rating ? `${rating}/5 CMS` : "CMS rating unavailable"}
    </span>
  );
}

export function CoverageNotice({ children }: { children: React.ReactNode }) {
  return (
    <aside className="notice coverage-notice">
      <span aria-hidden="true">ⓘ</span>
      <div>
        <strong>Coverage transparency</strong>
        <p>{children}</p>
      </div>
    </aside>
  );
}

export function PricingDisclaimer() {
  return (
    <details className="disclosure">
      <summary>Important price information</summary>
      <p>
        Published prices come from hospital transparency files. Your final bill
        may differ. Professional fees, anesthesia, pathology, labs, medications,
        implants, and other services may be billed separately. Insurance cost
        depends on your deductible, coinsurance, copay, network, authorization,
        and actual services received.
      </p>
    </details>
  );
}

export function SourceAttribution({
  updated,
  url,
  quality = false,
  showLink = true,
  context,
}: {
  updated?: string;
  url?: string;
  quality?: boolean;
  showLink?: boolean;
  context?: string;
}) {
  return (
    <div className="source-attribution">
      <span>
        <strong>Data source:</strong>{" "}
        {quality ? "CMS Care Compare" : "Hospital machine-readable file"}
        {context ? ` · ${context}` : ""}
      </span>
      {updated && (
        <span>
          <strong>Last updated:</strong>{" "}
          {new Date(updated).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            timeZone: "UTC",
          })}
        </span>
      )}
      {url && showLink && (
        <a href={url} target="_blank" rel="noreferrer">
          View official source file (external)
        </a>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="state-card">
      <span className="state-icon" aria-hidden="true">
        ○
      </span>
      <h2>{title}</h2>
      <div className="state-body">{children}</div>
    </section>
  );
}

export function ErrorState({ retryHref }: { retryHref?: string }) {
  return (
    <section className="state-card error" role="alert">
      <h2>We couldn’t load this information</h2>
      <p>Please try again. No missing prices will be estimated or filled in.</p>
      {retryHref && (
        <Link className="button secondary" href={retryHref}>
          Try again
        </Link>
      )}
    </section>
  );
}

export function LoadingSkeleton() {
  return (
    <div className="skeleton-grid" aria-label="Loading">
      <div />
      <div />
      <div />
    </div>
  );
}

export function FacilityPriceCard({
  item,
  compare = true,
}: {
  item: PriceSummary;
  compare?: boolean;
}) {
  return (
    <article className="facility-card">
      <div className="facility-card-top">
        <div>
          <span className="badge neutral">
            {item.service_setting?.replaceAll("_", " ") || "Setting not listed"}
          </span>
          <h2>{item.facility_name}</h2>
          <p className="location">
            {item.city ?? "Location available on facility page"}
          </p>
        </div>
        <span className="verified">
          <span aria-hidden="true">✓</span> Published source
        </span>
      </div>
      <div className="price-grid">
        <div>
          <span>Published cash price</span>
          <strong>
            <PriceRange min={item.cash_price_min} max={item.cash_price_max} />
          </strong>
        </div>
        <div>
          <span>Published negotiated range</span>
          <strong>
            <PriceRange
              min={item.negotiated_price_min}
              max={item.negotiated_price_max}
            />
          </strong>
        </div>
      </div>
      {item.payer_name && (
        <p className="payer-note">
          Published rate available for {item.payer_name}
          {item.plan_name ? ` · ${item.plan_name}` : ""}. This does not
          guarantee network participation.
        </p>
      )}
      <SourceAttribution updated={item.last_updated} url={item.source_url} />
      <div className="card-actions">
        <Link className="button" href={`/hospitals/${item.facility_id}`}>
          View details
        </Link>
        {compare && (
          <Link
            className="button secondary"
            href={`/compare?ids=${item.facility_id}`}
          >
            Compare
          </Link>
        )}
      </div>
    </article>
  );
}

export function ComparisonFacilityCard({
  item,
  procedureSlug,
  payerName,
}: {
  item: ProcedureComparisonItem;
  procedureSlug: string;
  payerName?: string;
}) {
  const locationLabel = item.location_name
    ? `${item.location_name} · ${item.city}, ${item.state}`
    : `${item.city}, ${item.state}`;
  return (
    <article
      className={`facility-card ${item.price_available ? "" : "no-price"}`}
    >
      <div className="facility-card-top">
        <div>
          <span className="badge neutral">
            {item.location_type.replaceAll("_", " ")}
          </span>
          <h2>{item.facility_name}</h2>
          <p className="location">{locationLabel}</p>
        </div>
        {item.price_available ? (
          <span className="verified">
            <span aria-hidden="true">✓</span> Verified published source
          </span>
        ) : (
          <span className="badge unavailable">No published price</span>
        )}
      </div>
      <div className="facility-facts" aria-label="Facility facts">
        <QualityRating value={item.cms_overall_rating} />
        <span>{item.facility_type ?? "Hospital"}</span>
        <span>
          {item.service_settings.length
            ? item.service_settings.join(", ").replaceAll("_", " ")
            : "Service setting unavailable"}
        </span>
      </div>
      {item.price_available ? (
        <div className="price-grid">
          <div>
            <span>Published cash price</span>
            <strong>
              <PriceRange min={item.cash_price_min} max={item.cash_price_max} />
            </strong>
          </div>
          <div>
            <span>
              Published negotiated range
              {payerName ? ` · ${payerName}` : " · across available payers"}
            </span>
            <strong>
              <PriceRange
                min={item.negotiated_price_min}
                max={item.negotiated_price_max}
              />
            </strong>
          </div>
        </div>
      ) : (
        <div className="no-price-message">
          <strong>Price not currently available</strong>
          <p>
            This hospital remains visible because missing data is different from
            the service being unavailable.
          </p>
        </div>
      )}
      {item.price_available && (
        <SourceAttribution
          updated={item.latest_updated ?? undefined}
          url={item.source_url ?? undefined}
        />
      )}
      <div className="card-actions">
        <Link className="button" href={`/hospitals/${item.facility_id}`}>
          View details
        </Link>
        <CompareSelect
          facilityId={item.facility_id}
          locationId={item.facility_location_id}
          name={locationLabel}
          procedureSlug={procedureSlug}
        />
      </div>
    </article>
  );
}

export function FilterPanel({ children }: { children: React.ReactNode }) {
  return (
    <details className="filters responsive-filters">
      <summary>Filter results</summary>
      <div className="responsive-filter-body">{children}</div>
    </details>
  );
}

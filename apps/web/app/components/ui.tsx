import Link from "next/link";
import type { PriceSummary, ProcedureComparisonItem } from "../../lib/api";
import type { Messages } from "../../lib/i18n";
import { CompareSelect } from "./CompareSelect";
import { FacilityImage } from "./FacilityImage";

function moneyWhole(value: string | number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

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
          <strong>{quality ? "Source updated:" : "Carevero refresh:"}</strong>{" "}
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

export function ErrorState({
  retryHref,
  onRetry,
}: {
  retryHref?: string;
  onRetry?: () => void;
}) {
  return (
    <section className="state-card error" role="alert">
      <h2>We couldn’t load this information</h2>
      <p>Please try again. No missing prices will be estimated or filled in.</p>
      {onRetry ? (
        <button className="button secondary" type="button" onClick={onRetry}>
          Try again
        </button>
      ) : retryHref ? (
        <Link className="button secondary" href={retryHref}>
          Try again
        </Link>
      ) : null}
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
          <span>Published insurance pricing</span>
          {item.payer_name ? (
            <strong>
              <PriceRange
                min={item.negotiated_price_min}
                max={item.negotiated_price_max}
              />
            </strong>
          ) : (
            <strong>
              {item.negotiated_price_min !== null
                ? "Rates available — choose a payer"
                : "No normalized payer rates published"}
            </strong>
          )}
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
  procedureName,
  procedureSlug,
  payerName,
  planName,
  planId,
  messages,
}: {
  item: ProcedureComparisonItem;
  procedureName: string;
  procedureSlug: string;
  payerName?: string;
  planName?: string;
  planId?: string;
  messages?: Messages;
}) {
  const locationLabel = item.location_name
    ? `${item.location_name} · ${item.city}, ${item.state}`
    : `${item.city}, ${item.state}`;
  const distanceLabel =
    typeof item.distance_miles === "number"
      ? `${item.distance_miles} ${messages?.milesUnit ?? "miles"}`
      : null;
  const difference = item.published_price_difference
    ? Number(item.published_price_difference)
    : null;
  const detailQuery = new URLSearchParams();
  if (payerName && item.published_payers?.length) {
    const selected = item.published_payers.find(
      (publishedPayer) => publishedPayer.name === payerName,
    );
    if (selected) detailQuery.set("payer", selected.slug);
  }
  if (planId) detailQuery.set("plan", planId);
  const detailHref = `/procedures/${procedureSlug}/prices/${item.facility_location_id}${detailQuery.size ? `?${detailQuery}` : ""}`;
  return (
    <article
      className={`facility-card facility-card-media-layout ${item.price_available ? "" : "no-price"}`}
    >
      <FacilityImage
        name={item.facility_name}
        variant="card"
        className="facility-card-media"
      />
      <div className="facility-card-body">
        <div className="facility-card-top">
          <div>
            <span className="badge neutral">
              {item.location_type.replaceAll("_", " ")}
            </span>
            <h2>{item.facility_name}</h2>
            <p className="location">
              {locationLabel}
              {distanceLabel && (
                <span className="facility-distance"> · {distanceLabel}</span>
              )}
            </p>
            <p className="card-procedure">
              Comparing: <strong>{procedureName}</strong>
            </p>
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
              <span>
                {item.cash_price_value_count && item.cash_price_value_count > 1
                  ? "Published cash prices"
                  : "Published cash price"}
              </span>
              <strong>
                <PriceRange
                  min={item.cash_price_min}
                  max={item.cash_price_max}
                />
              </strong>
              {item.is_lowest_comparable_cash ? (
                <span className="savings-badge lowest">
                  {messages?.lowestCashShown ??
                    "Lowest published cash price shown"}
                </span>
              ) : difference && difference > 0 ? (
                <span
                  className="savings-badge"
                  title={messages?.comparedWithLowest ?? undefined}
                >
                  {messages?.priceDifference ?? "Published-price difference"}: +
                  {moneyWhole(difference)}
                </span>
              ) : null}
              {item.lower_priced_nearby_option && (
                <small className="nearby-lower">
                  {messages?.nearbyLower ?? "Nearby lower published cash price"}
                  : {item.lower_priced_nearby_option.facility_name} · −
                  {moneyWhole(
                    item.lower_priced_nearby_option
                      .published_price_difference ?? 0,
                  )}
                  {typeof item.lower_priced_nearby_option.distance_miles ===
                  "number"
                    ? ` · ${item.lower_priced_nearby_option.distance_miles} ${messages?.milesUnit ?? "miles"}`
                    : ""}
                </small>
              )}
              {item.cash_price_explanation && (
                <small className="price-context">
                  {item.cash_price_explanation}
                </small>
              )}
              <Link className="price-detail-link" href={detailHref}>
                View price details
              </Link>
            </div>
            <div>
              {payerName ? (
                <>
                  <span className="selected-insurance-label">
                    Your selected insurance
                  </span>
                  <strong className="insurance-name">
                    {payerName}
                    {planName ? ` · ${planName}` : ""}
                  </strong>
                  <span>Published matching negotiated rates</span>
                  <strong>
                    <PriceRange
                      min={item.negotiated_price_min}
                      max={item.negotiated_price_max}
                    />
                  </strong>
                  <small className="price-context">
                    {item.matching_negotiated_rate_count ?? 0} matching
                    published rate records
                  </small>
                </>
              ) : (
                <>
                  <span>Published negotiated rates available</span>
                  <strong className="payer-availability">
                    {item.distinct_payer_count
                      ? `${item.distinct_payer_count} payer${item.distinct_payer_count === 1 ? "" : "s"}`
                      : "No normalized payer rates"}
                  </strong>
                  {!!item.published_payers?.length && (
                    <small className="price-context">
                      {item.published_payers
                        .slice(0, 4)
                        .map((publishedPayer) => publishedPayer.name)
                        .join(" · ")}
                      {item.published_payers.length > 4
                        ? ` · +${item.published_payers.length - 4} more`
                        : ""}
                    </small>
                  )}
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="no-price-message">
            <strong>Price not currently available</strong>
            <p>
              This hospital remains visible because missing data is different
              from the service being unavailable.
            </p>
          </div>
        )}
        {item.price_available && (
          <>
            <details className="price-details">
              <summary>Price details and source</summary>
              <dl>
                <div>
                  <dt>Procedure</dt>
                  <dd>{procedureName}</dd>
                </div>
                <div>
                  <dt>Service setting</dt>
                  <dd>
                    {item.service_settings.length
                      ? item.service_settings.join(", ").replaceAll("_", " ")
                      : "Not published"}
                  </dd>
                </div>
                <div>
                  <dt>Published summary groups</dt>
                  <dd>{item.summary_count}</dd>
                </div>
                <div>
                  <dt>Price-data completeness</dt>
                  <dd>
                    {item.data_completeness === "high_data_completeness"
                      ? "High data completeness"
                      : item.data_completeness === "some_details_unavailable"
                        ? "Some details unavailable"
                        : "Limited pricing detail"}
                  </dd>
                </div>
                <div>
                  <dt>All published negotiated rates</dt>
                  <dd>
                    <PriceRange
                      min={item.all_published_negotiated_min ?? null}
                      max={item.all_published_negotiated_max ?? null}
                    />
                  </dd>
                </div>
              </dl>
              <p>
                Published prices may not equal your final out-of-pocket cost. A
                published rate does not verify network participation or
                coverage. Separately billed professional services may apply.
              </p>
              <Link className="text-link" href={detailHref}>
                View all price and source details
              </Link>
            </details>
            <SourceAttribution
              updated={item.latest_updated ?? undefined}
              url={item.source_url ?? undefined}
            />
          </>
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
      </div>
    </article>
  );
}

export function FilterPanel({ children }: { children: React.ReactNode }) {
  return (
    <details className="filters responsive-filters">
      <summary>
        <span>Filter results</span>
        <small>Location, price availability, setting, payer, and rating</small>
      </summary>
      <div className="responsive-filter-body">{children}</div>
    </details>
  );
}

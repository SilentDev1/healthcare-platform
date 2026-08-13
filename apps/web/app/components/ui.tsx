import Link from "next/link";
import type { ProcedureComparisonItem } from "../../lib/api";
import { formatCashExplanation, type Locale, type Messages } from "../../lib/i18n";
import { CompareSelect } from "./CompareSelect";
import { FacilityImage } from "./FacilityImage";

function moneyWhole(value: string | number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export function Money({
  value,
  messages,
}: {
  value: string | null;
  messages?: Messages;
}) {
  const amount = value === null ? Number.NaN : Number(value);
  if (!Number.isFinite(amount) || amount < 0)
    return (
      <span className="muted">{messages?.notAvailable ?? "Not available"}</span>
    );
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
  messages,
}: {
  min: string | null;
  max: string | null;
  messages?: Messages;
}) {
  if (min === null && max === null)
    return (
      <span className="price-missing">
        {messages?.priceNotAvailable ?? "Price not currently available"}
      </span>
    );
  if (min === max || max === null)
    return <Money value={min} messages={messages} />;
  return (
    <>
      <Money value={min} messages={messages} />–
      <Money value={max} messages={messages} />
    </>
  );
}

export function QualityRating({
  value,
  messages,
}: {
  value?: string | null;
  messages?: Messages;
}) {
  const rating = value && /^[1-5](?:\.0+)?$/.test(value) ? Number(value) : null;
  return (
    <span
      className="quality-rating"
      aria-label={
        rating
          ? (
              messages?.cmsRatingAria ?? "CMS overall rating: {rating} out of 5"
            ).replace("{rating}", String(rating))
          : (messages?.cmsRatingAriaUnavailable ??
            "CMS overall rating not available")
      }
    >
      <span aria-hidden="true">★</span>{" "}
      {rating
        ? (messages?.cmsRatingValue ?? "{rating}/5 CMS").replace(
            "{rating}",
            String(rating),
          )
        : (messages?.cmsRatingUnavailable ?? "CMS rating unavailable")}
    </span>
  );
}

export function CoverageNotice({
  children,
  messages,
}: {
  children: React.ReactNode;
  messages?: Messages;
}) {
  return (
    <aside className="notice coverage-notice">
      <span aria-hidden="true">ⓘ</span>
      <div>
        <strong>
          {messages?.priceCoverage ?? "Price coverage"}
        </strong>
        <p>{children}</p>
      </div>
    </aside>
  );
}

export function PricingDisclaimer({ messages }: { messages?: Messages }) {
  return (
    <details className="disclosure">
      <summary>
        {messages?.importantPriceInfo ?? "Important price information"}
      </summary>
      <p>
        {messages?.pricingDisclaimerBody ??
          "Published prices come from hospital transparency files. Your final bill may differ. Professional fees, anesthesia, pathology, labs, medications, implants, and other services may be billed separately. Insurance cost depends on your deductible, coinsurance, copay, network, authorization, and actual services received."}
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
  messages,
}: {
  updated?: string;
  url?: string;
  quality?: boolean;
  showLink?: boolean;
  context?: string;
  messages?: Messages;
}) {
  return (
    <div className="source-attribution">
      <span>
        <strong>{messages?.dataSource ?? "Data source:"}</strong>{" "}
        {quality
          ? (messages?.sourceCmsCareCompare ?? "CMS Care Compare")
          : (messages?.sourceHospitalFile ?? "Hospital machine-readable file")}
        {context ? ` · ${context}` : ""}
      </span>
      {updated && (
        <span>
          <strong>
            {quality
              ? (messages?.sourceUpdated ?? "Source updated:")
              : (messages?.careveroRefresh ?? "Carevero refresh:")}
          </strong>{" "}
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
          {messages?.viewSourceFile ?? "View official source file (external)"}
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
  messages,
}: {
  retryHref?: string;
  onRetry?: () => void;
  messages?: Messages;
}) {
  const tryAgain = messages?.tryAgain ?? "Try again";
  return (
    <section className="state-card error" role="alert">
      <h2>{messages?.errorTitle ?? "We couldn’t load this information"}</h2>
      <p>
        {messages?.errorBody ??
          "Please try again. No missing prices will be estimated or filled in."}
      </p>
      {onRetry ? (
        <button className="button secondary" type="button" onClick={onRetry}>
          {tryAgain}
        </button>
      ) : retryHref ? (
        <Link className="button secondary" href={retryHref}>
          {tryAgain}
        </Link>
      ) : null}
    </section>
  );
}

export function LoadingSkeleton({ messages }: { messages?: Messages }) {
  return (
    <div className="skeleton-grid" aria-label={messages?.loading ?? "Loading"}>
      <div />
      <div />
      <div />
    </div>
  );
}

export function ComparisonFacilityCard({
  item,
  procedureSlug,
  payerName,
  planName,
  planId,
  messages,
  locale,
}: {
  item: ProcedureComparisonItem;
  procedureName?: string;
  procedureSlug: string;
  payerName?: string;
  planName?: string;
  planId?: string;
  messages?: Messages;
  locale?: Locale;
}) {
  const locationLabel = item.location_name
    ? `${item.location_name} · ${item.city}, ${item.state}`
    : `${item.city}, ${item.state}`;
  const distanceLabel =
    typeof item.distance_miles === "number"
      ? `${item.distance_miles} ${messages?.milesUnit ?? "miles"}`
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
  const cashExplanation = messages
    ? formatCashExplanation(
        messages,
        item.cash_price_reason_codes,
        item.cash_price_value_count ?? 0,
      )
    : (item.cash_price_explanation ?? null);
  const cashLabel =
    item.cash_price_value_count && item.cash_price_value_count > 1
      ? (messages?.publishedCashPrices ?? "Published cash prices")
      : (messages?.publishedCashPrice ?? "Published cash price");
  const settingLabel = item.service_settings.length
    ? item.service_settings.join(", ").replaceAll("_", " ")
    : null;
  return (
    <article className={`rcard ${item.price_available ? "" : "rcard-noprice"}`}>
      <FacilityImage
        name={item.facility_name}
        imageUrl={item.image_url}
        imageAlt={
          item.image_url
            ? (item.image_alt ??
              (messages?.imageAltPhotoOf ?? "Photo of {hospital}").replace(
                "{hospital}",
                item.facility_name,
              ))
            : undefined
        }
        attribution={item.image_attribution ?? undefined}
        placeholderLabel={messages?.imageNoPhoto}
        variant="card"
        className="rcard-photo"
      />
      <div className="rcard-body">
      <div className="rcard-info">
        <h3 className="rcard-name">{item.facility_name}</h3>
        <p className="rcard-meta">
          {locationLabel}
          {distanceLabel && (
            <span className="rcard-distance"> · {distanceLabel}</span>
          )}
        </p>
        <div className="rcard-tags">
          <QualityRating value={item.cms_overall_rating} messages={messages} />
          <span className="rcard-type">
            {item.facility_type ?? (messages?.facilityTypeHospital ?? "Hospital")}
            {settingLabel ? ` · ${settingLabel}` : ""}
          </span>
        </div>
      </div>

      <div className="rcard-price">
        {item.price_available ? (
          <>
            <span className="rcard-price-label">{cashLabel}</span>
            <strong className="rcard-price-value">
              <PriceRange
                min={item.cash_price_min}
                max={item.cash_price_max}
                messages={messages}
              />
            </strong>
            {item.lower_priced_nearby_option ? (
              <span
                className="savings-badge nearby"
                title={messages?.comparedWithLowest ?? undefined}
              >
                <span aria-hidden="true">↓ </span>
                {moneyWhole(
                  item.lower_priced_nearby_option.published_price_difference ??
                    0,
                )}{" "}
                {messages?.lowerNearbySuffix ?? "lower published price nearby"}{" "}
                · {item.lower_priced_nearby_option.facility_name}
                {typeof item.lower_priced_nearby_option.distance_miles ===
                "number"
                  ? ` · ${item.lower_priced_nearby_option.distance_miles} ${messages?.milesUnit ?? "miles"}`
                  : ""}
              </span>
            ) : item.is_lowest_comparable_cash ? (
              <span className="savings-badge lowest">
                {messages?.lowestNearby ??
                  "Lowest comparable published price nearby"}
              </span>
            ) : null}
            {item.additional_published_prices &&
            item.additional_published_prices.length > 0 ? (
              <details className="component-note">
                <summary>
                  {messages?.additionalPublishedPrices ??
                    "Additional published prices"}{" "}
                  ({item.additional_published_prices.length})
                </summary>
                <p>
                  {messages?.componentRangeNote ??
                    "This hospital publishes multiple prices for this service. They may represent different billing components and are not a single price range."}
                </p>
                <ul>
                  {item.additional_published_prices.map((component, index) => (
                    <li key={index}>
                      {moneyWhole(component.amount_min)}
                      {component.amount_min !== component.amount_max
                        ? `–${moneyWhole(component.amount_max)}`
                        : ""}{" "}
                      · {component.service_setting.replaceAll("_", " ")} ·{" "}
                      {component.billing_scope.replaceAll("_", " ")}
                    </li>
                  ))}
                </ul>
              </details>
            ) : cashExplanation ? (
              <small className="price-context">{cashExplanation}</small>
            ) : null}
            <div className="rcard-insurance">
              {payerName ? (
                <>
                  <span className="rcard-insurance-name">
                    {payerName}
                    {planName ? ` · ${planName}` : ""}
                  </span>{" "}
                  <PriceRange
                    min={item.negotiated_price_min}
                    max={item.negotiated_price_max}
                    messages={messages}
                  />{" "}
                  <span className="rcard-insurance-note">
                    ·{" "}
                    {(
                      messages?.matchingRateRecords ??
                      "{count} matching published rate records"
                    ).replace(
                      "{count}",
                      String(item.matching_negotiated_rate_count ?? 0),
                    )}
                  </span>
                </>
              ) : (
                <>
                  <span className="rcard-insurance-count">
                    {item.distinct_payer_count
                      ? item.distinct_payer_count === 1
                        ? (messages?.oneCompanyPublishesRates ??
                          "1 company publishes rates")
                        : `${item.distinct_payer_count} ${messages?.companiesPublishRates ?? "companies publish rates"}`
                      : (messages?.noInsurancePrices ??
                        "No published insurance prices")}
                  </span>
                  {!!item.published_payers?.length && (
                    <span className="rcard-insurance-note">
                      {item.published_payers
                        .slice(0, 3)
                        .map((publishedPayer) => publishedPayer.name)
                        .join(" · ")}
                      {item.published_payers.length > 3
                        ? ` · +${item.published_payers.length - 3} more`
                        : ""}
                    </span>
                  )}
                </>
              )}
            </div>
            <Link className="rcard-detail" href={detailHref}>
              {messages?.priceDetails ?? "View price details"}
            </Link>
          </>
        ) : (
          <div className="rcard-nopricebox">
            <strong>
              {messages?.unpricedCardTitle ??
                "No published price available for this procedure"}
            </strong>
            <p>
              {messages?.unpricedCardBody ??
                "Carevero has not found a currently publishable price for this procedure at this location."}
            </p>
          </div>
        )}
      </div>
      </div>

      <div className="rcard-actions">
        <Link
          className="button secondary"
          href={`/hospitals/${item.facility_id}`}
        >
          {messages?.viewDetails ?? "View details"}
        </Link>
        <CompareSelect
          facilityId={item.facility_id}
          locationId={item.facility_location_id}
          name={locationLabel}
          procedureSlug={procedureSlug}
          locale={locale}
        />
      </div>
    </article>
  );
}

export function FilterPanel({
  children,
  messages,
}: {
  children: React.ReactNode;
  messages?: Messages;
}) {
  return (
    <details className="filters responsive-filters">
      <summary>
        <span>{messages?.filterResultsSummary ?? "Filter results"}</span>
        <small>
          {messages?.filterResultsHint ??
            "Location, price availability, setting, payer, and rating"}
        </small>
      </summary>
      <div className="responsive-filter-body">{children}</div>
    </details>
  );
}

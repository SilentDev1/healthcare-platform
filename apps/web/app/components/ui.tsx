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
          {messages?.coverageTransparency ?? "Coverage transparency"}
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
  procedureName,
  procedureSlug,
  payerName,
  planName,
  planId,
  messages,
  locale,
}: {
  item: ProcedureComparisonItem;
  procedureName: string;
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
  return (
    <article
      className={`facility-card facility-card-media-layout ${item.price_available ? "" : "no-price"}`}
    >
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
          </div>
          {item.price_available ? (
            <span className="verified">
              <span aria-hidden="true">✓</span>{" "}
              {messages?.verifiedPublishedSource ?? "Verified published source"}
            </span>
          ) : (
            <span className="badge unavailable">
              {messages?.noPublishedPrice ?? "No published price"}
            </span>
          )}
        </div>
        <div
          className="facility-facts"
          aria-label={messages?.facilityFacts ?? "Facility facts"}
        >
          <QualityRating value={item.cms_overall_rating} messages={messages} />
          <span>{item.facility_type ?? "Hospital"}</span>
          <span>
            {item.service_settings.length
              ? item.service_settings.join(", ").replaceAll("_", " ")
              : (messages?.serviceSettingUnavailable ??
                "Service setting unavailable")}
          </span>
        </div>
        {item.price_available ? (
          <div className="price-grid">
            <div>
              <span>
                {item.cash_price_value_count && item.cash_price_value_count > 1
                  ? (messages?.publishedCashPrices ?? "Published cash prices")
                  : (messages?.publishedCashPrice ?? "Published cash price")}
              </span>
              <strong>
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
                    item.lower_priced_nearby_option
                      .published_price_difference ?? 0,
                  )}{" "}
                  {messages?.lowerNearbySuffix ??
                    "lower published price nearby"}{" "}
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
                    {item.additional_published_prices.map(
                      (component, index) => (
                        <li key={index}>
                          {moneyWhole(component.amount_min)}
                          {component.amount_min !== component.amount_max
                            ? `–${moneyWhole(component.amount_max)}`
                            : ""}{" "}
                          · {component.service_setting.replaceAll("_", " ")} ·{" "}
                          {component.billing_scope.replaceAll("_", " ")}
                        </li>
                      ),
                    )}
                  </ul>
                </details>
              ) : cashExplanation ? (
                <small className="price-context">{cashExplanation}</small>
              ) : null}
              <Link className="price-detail-link" href={detailHref}>
                {messages?.priceDetails ?? "View price details"}
              </Link>
            </div>
            <div>
              {payerName ? (
                <>
                  <span className="selected-insurance-label">
                    {messages?.yourSelectedInsurance ??
                      "Your selected insurance"}
                  </span>
                  <strong className="insurance-name">
                    {payerName}
                    {planName ? ` · ${planName}` : ""}
                  </strong>
                  <span>
                    {messages?.matchingRates ??
                      "Published matching negotiated rates"}
                  </span>
                  <strong>
                    <PriceRange
                      min={item.negotiated_price_min}
                      max={item.negotiated_price_max}
                      messages={messages}
                    />
                  </strong>
                  <small className="price-context">
                    {(
                      messages?.matchingRateRecords ??
                      "{count} matching published rate records"
                    ).replace(
                      "{count}",
                      String(item.matching_negotiated_rate_count ?? 0),
                    )}
                  </small>
                </>
              ) : (
                <>
                  <span>{messages?.insurancePrices ?? "Insurance prices"}</span>
                  <strong className="payer-availability">
                    {item.distinct_payer_count
                      ? item.distinct_payer_count === 1
                        ? (messages?.oneCompanyPublishesRates ??
                          "1 company publishes rates")
                        : `${item.distinct_payer_count} ${messages?.companiesPublishRates ?? "companies publish rates"}`
                      : (messages?.noInsurancePrices ??
                        "No published insurance prices")}
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
            <strong>
              {messages?.priceNotAvailable ?? "Price not currently available"}
            </strong>
            <p>
              {messages?.noPriceExplanation ??
                "This hospital remains visible because missing data is different from the service being unavailable."}
            </p>
          </div>
        )}
        {item.price_available && (
          <>
            <details className="price-details">
              <summary>
                {messages?.priceDetailsAndSource ?? "Price details and source"}
              </summary>
              <dl>
                <div>
                  <dt>{messages?.procedure ?? "Procedure"}</dt>
                  <dd>{procedureName}</dd>
                </div>
                <div>
                  <dt>{messages?.serviceSetting ?? "Service setting"}</dt>
                  <dd>
                    {item.service_settings.length
                      ? item.service_settings.join(", ").replaceAll("_", " ")
                      : (messages?.notPublished ?? "Not published")}
                  </dd>
                </div>
                <div>
                  <dt>
                    {messages?.publishedSummaryGroups ??
                      "Published summary groups"}
                  </dt>
                  <dd>{item.summary_count}</dd>
                </div>
                <div>
                  <dt>
                    {messages?.priceDataCompleteness ??
                      "Price-data completeness"}
                  </dt>
                  <dd>
                    {item.data_completeness === "high_data_completeness"
                      ? (messages?.highDataCompleteness ??
                        "High data completeness")
                      : item.data_completeness === "some_details_unavailable"
                        ? (messages?.someDetailsUnavailable ??
                          "Some details unavailable")
                        : (messages?.limitedPricingDetail ??
                          "Limited pricing detail")}
                  </dd>
                </div>
                <div>
                  <dt>
                    {messages?.allPublishedNegotiatedRates ??
                      "All published negotiated rates"}
                  </dt>
                  <dd>
                    <PriceRange
                      min={item.all_published_negotiated_min ?? null}
                      max={item.all_published_negotiated_max ?? null}
                      messages={messages}
                    />
                  </dd>
                </div>
              </dl>
              <p>
                {messages?.priceDetailsDisclaimer ??
                  "Published prices may not equal your final out-of-pocket cost. A published rate does not verify network participation or coverage. Separately billed professional services may apply."}
              </p>
              <Link className="text-link" href={detailHref}>
                {messages?.viewAllPriceDetails ??
                  "View all price and source details"}
              </Link>
            </details>
            <SourceAttribution
              updated={item.latest_updated ?? undefined}
              url={item.source_url ?? undefined}
              messages={messages}
            />
          </>
        )}
        <div className="card-actions">
          <Link className="button" href={`/hospitals/${item.facility_id}`}>
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

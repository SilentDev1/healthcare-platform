import Link from "next/link";
import type { Metadata } from "next";
import {
  apiGet,
  type ConsumerPriceDetail,
  type ConsumerPriceDetailRecord,
} from "../../../../../lib/api";
import { Money, PricingDisclaimer } from "../../../../components/ui";

export const metadata: Metadata = {
  title: "Published price details",
  robots: { index: false, follow: true },
};

function formatDate(value: string | null) {
  if (!value) return "Not supplied by the hospital";
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function RateRecord({ record }: { record: ConsumerPriceDetailRecord }) {
  return (
    <article className="rate-detail-card">
      <div>
        <span className="badge neutral">
          {record.semantic_type.replaceAll("_", " ")}
        </span>
        <h3>
          <Money value={record.amount} />
        </h3>
        {record.payer_name && (
          <p>
            <strong>{record.payer_name}</strong>
            {record.plan_name
              ? ` · ${record.plan_name}`
              : " · plan not specified"}
          </p>
        )}
      </div>
      <dl className="rate-detail-facts">
        <div>
          <dt>Hospital description</dt>
          <dd>{record.original_description}</dd>
        </div>
        <div>
          <dt>Billing code</dt>
          <dd>
            {record.billing_codes.length
              ? record.billing_codes
                  .map((code) => `${code.system ?? "Code"} ${code.code ?? ""}`)
                  .join(", ")
              : "Not supplied"}
          </dd>
        </div>
        <div>
          <dt>Service details</dt>
          <dd>
            {record.service_variant.replaceAll("_", " ")} ·{" "}
            {record.service_setting.replaceAll("_", " ")} ·{" "}
            {record.component_scope.replaceAll("_", " ")}
            {record.negotiated_rate_type
              ? ` · ${record.negotiated_rate_type.replaceAll("_", " ")}`
              : ""}
          </dd>
        </div>
      </dl>
      <details>
        <summary>Source and freshness</summary>
        <p>
          Hospital source-file date:{" "}
          {record.source_file_date
            ? formatDate(record.source_file_date)
            : record.source_file_last_modified ||
              "Not supplied by the hospital"}
        </p>
        <p>Carevero download date: {formatDate(record.downloaded_at)}</p>
        <p>Carevero import date: {formatDate(record.imported_at)}</p>
        <p>
          Carevero projection refresh:{" "}
          {formatDate(record.carevero_refresh_date)}
        </p>
        <p>Source record: {record.source_row_identity}</p>
        <p>
          Source checksum (SHA-256):{" "}
          <code>{record.source_checksum_sha256}</code>
        </p>
        <a href={record.source_url} target="_blank" rel="noreferrer">
          View official hospital source file (external)
        </a>
      </details>
    </article>
  );
}

export default async function PriceDetailsPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string; locationId: string }>;
  searchParams: Promise<{ payer?: string; plan?: string }>;
}) {
  const { slug, locationId } = await params;
  const filters = await searchParams;
  const query = new URLSearchParams();
  if (filters.payer) query.set("payer", filters.payer);
  if (filters.plan) query.set("plan", filters.plan);
  const data = await apiGet<ConsumerPriceDetail>(
    `/api/v1/procedures/${encodeURIComponent(slug)}/locations/${encodeURIComponent(locationId)}/price-details${query.size ? `?${query}` : ""}`,
  );
  const cash = data.records.filter(
    (record) => record.semantic_type === "cash_self_pay",
  );
  const negotiated = data.records.filter((record) =>
    record.semantic_type.startsWith("negotiated_"),
  );
  const referenceRates = data.records.filter(
    (record) => !cash.includes(record) && !negotiated.includes(record),
  );
  const payerGroups = new Map<string, ConsumerPriceDetailRecord[]>();
  for (const record of negotiated) {
    const name = record.payer_name ?? "Payer name unavailable";
    payerGroups.set(name, [...(payerGroups.get(name) ?? []), record]);
  }

  return (
    <main>
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href={`/procedures/${slug}/prices`}>Compare prices</Link>
        <span>/</span>
        <span>Price details</span>
      </nav>
      <div className="page-heading">
        <p className="eyebrow">Hospital-published source records</p>
        <h1>{data.procedure_name}</h1>
        <p className="lede">
          {data.facility_name}
          {data.location_name ? ` · ${data.location_name}` : ""}
        </p>
      </div>
      <aside className="notice coverage-notice">
        <span aria-hidden="true">ⓘ</span>
        <div>
          <strong>What does this price mean?</strong>
          <p>{data.disclaimer}</p>
        </div>
      </aside>
      {data.records_truncated && (
        <p className="notice" role="status">
          This view shows the first 2,000 matching published records. Narrow by
          insurer or plan to review a smaller comparable set.
        </p>
      )}

      <section className="price-detail-section">
        <h2>Published cash / self-pay prices</h2>
        {cash.length ? (
          cash.map((record) => (
            <RateRecord
              key={`${record.source_row_identity}-cash`}
              record={record}
            />
          ))
        ) : (
          <p>Cash price not published.</p>
        )}
      </section>

      <section className="price-detail-section">
        <h2>Published insurance rates</h2>
        {payerGroups.size ? (
          [...payerGroups.entries()].map(([payerName, records]) => (
            <details
              className="payer-rate-group"
              key={payerName}
              open={payerGroups.size === 1}
            >
              <summary>
                {payerName} · {records.length} published rate
                {records.length === 1 ? "" : "s"}
              </summary>
              <div className="rate-detail-list">
                {records.map((record, index) => (
                  <RateRecord
                    key={`${record.source_row_identity}-${record.plan_id ?? "payer"}-${record.amount}-${index}`}
                    record={record}
                  />
                ))}
              </div>
            </details>
          ))
        ) : (
          <p>No matching normalized insurance rates are published.</p>
        )}
        <p className="field-help">
          A published rate does not confirm that the hospital is in network or
          that your plan covers this service. Confirm benefits with the insurer.
        </p>
      </section>

      {!!referenceRates.length && (
        <details className="price-detail-section">
          <summary>Hospital reference charges and de-identified bounds</summary>
          <p>
            These are not cash prices or plan-specific rates and are shown only
            as secondary source context.
          </p>
          <div className="rate-detail-list">
            {referenceRates.map((record, index) => (
              <RateRecord
                key={`${record.source_row_identity}-${record.semantic_type}-${index}`}
                record={record}
              />
            ))}
          </div>
        </details>
      )}
      <PricingDisclaimer />
    </main>
  );
}

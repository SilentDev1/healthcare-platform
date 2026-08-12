import Link from "next/link";
import type { Metadata } from "next";
import {
  apiGet,
  type ConsumerPriceDetail,
  type ConsumerPriceDetailRecord,
} from "../../../../../lib/api";
import { Money, PricingDisclaimer } from "../../../../components/ui";
import { localePath, type Messages } from "../../../../../lib/i18n";
import {
  requestLocale,
  requestMessages,
} from "../../../../../lib/i18n-server";

export const metadata: Metadata = {
  title: "Published price details",
  robots: { index: false, follow: true },
};

function formatDate(value: string | null, notSupplied: string) {
  if (!value) return notSupplied;
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function RateRecord({
  record,
  t,
}: {
  record: ConsumerPriceDetailRecord;
  t: Messages;
}) {
  return (
    <article className="rate-detail-card">
      <div>
        <span className="badge neutral">
          {record.semantic_type.replaceAll("_", " ")}
        </span>
        <h3>
          <Money value={record.amount} messages={t} />
        </h3>
        {record.payer_name && (
          <p>
            <strong>{record.payer_name}</strong>
            {record.plan_name
              ? ` · ${record.plan_name}`
              : ` · ${t.pdPlanNotSpecified}`}
          </p>
        )}
      </div>
      <dl className="rate-detail-facts">
        <div>
          <dt>{t.pdHospitalDescription}</dt>
          <dd>{record.original_description}</dd>
        </div>
        <div>
          <dt>{t.pdBillingCode}</dt>
          <dd>
            {record.billing_codes.length
              ? record.billing_codes
                  .map(
                    (code) =>
                      `${code.system ?? t.pdCodeFallback} ${code.code ?? ""}`,
                  )
                  .join(", ")
              : t.pdNotSupplied}
          </dd>
        </div>
        <div>
          <dt>{t.pdServiceDetails}</dt>
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
        <summary>{t.pdSourceAndFreshness}</summary>
        <p>
          {t.pdHospitalSourceFileDate}{" "}
          {record.source_file_date
            ? formatDate(record.source_file_date, t.pdNotSuppliedByHospital)
            : record.source_file_last_modified || t.pdNotSuppliedByHospital}
        </p>
        <p>
          {t.pdCareveroDownloadDate}{" "}
          {formatDate(record.downloaded_at, t.pdNotSuppliedByHospital)}
        </p>
        <p>
          {t.pdCareveroImportDate}{" "}
          {formatDate(record.imported_at, t.pdNotSuppliedByHospital)}
        </p>
        <p>
          {t.pdCareveroProjectionRefresh}{" "}
          {formatDate(record.carevero_refresh_date, t.pdNotSuppliedByHospital)}
        </p>
        <p>
          {t.pdSourceRecord} {record.source_row_identity}
        </p>
        <p>
          {t.pdSourceChecksum} <code>{record.source_checksum_sha256}</code>
        </p>
        <a href={record.source_url} target="_blank" rel="noreferrer">
          {t.pdViewOfficialHospitalSourceFile}
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
  const locale = await requestLocale();
  const t = await requestMessages();
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
    const name = record.payer_name ?? t.pdPayerNameUnavailable;
    payerGroups.set(name, [...(payerGroups.get(name) ?? []), record]);
  }

  return (
    <main>
      <nav className="breadcrumbs" aria-label={t.breadcrumb}>
        <Link href={localePath(locale, `/procedures/${slug}/prices`)}>
          {t.comparePrices}
        </Link>
        <span>/</span>
        <span>{t.pdBreadcrumbPriceDetails}</span>
      </nav>
      <div className="page-heading">
        <p className="eyebrow">{t.pdHospitalPublishedSourceRecords}</p>
        <h1>{data.procedure_name}</h1>
        <p className="lede">
          {data.facility_name}
          {data.location_name ? ` · ${data.location_name}` : ""}
        </p>
      </div>
      <aside className="notice coverage-notice">
        <span aria-hidden="true">ⓘ</span>
        <div>
          <strong>{t.pdWhatDoesPriceMean}</strong>
          <p>{data.disclaimer}</p>
        </div>
      </aside>
      {data.records_truncated && (
        <p className="notice" role="status">
          {t.pdRecordsTruncated}
        </p>
      )}

      <section className="price-detail-section">
        <h2>{t.pdPublishedCashSelfPay}</h2>
        {cash.length ? (
          cash.map((record) => (
            <RateRecord
              key={`${record.source_row_identity}-cash`}
              record={record}
              t={t}
            />
          ))
        ) : (
          <p>{t.pdCashNotPublished}</p>
        )}
      </section>

      <section className="price-detail-section">
        <h2>{t.pdPublishedInsuranceRates}</h2>
        {payerGroups.size ? (
          [...payerGroups.entries()].map(([payerName, records]) => (
            <details
              className="payer-rate-group"
              key={payerName}
              open={payerGroups.size === 1}
            >
              <summary>
                {payerName} ·{" "}
                {(records.length === 1
                  ? t.pdPublishedRateCountOne
                  : t.pdPublishedRateCountOther
                ).replace("{count}", String(records.length))}
              </summary>
              <div className="rate-detail-list">
                {records.map((record, index) => (
                  <RateRecord
                    key={`${record.source_row_identity}-${record.plan_id ?? "payer"}-${record.amount}-${index}`}
                    record={record}
                    t={t}
                  />
                ))}
              </div>
            </details>
          ))
        ) : (
          <p>{t.pdNoMatchingInsurance}</p>
        )}
        <p className="field-help">{t.pdRateNoConfirmNetwork}</p>
      </section>

      {!!referenceRates.length && (
        <details className="price-detail-section">
          <summary>{t.pdReferenceChargesSummary}</summary>
          <p>{t.pdReferenceChargesBody}</p>
          <div className="rate-detail-list">
            {referenceRates.map((record, index) => (
              <RateRecord
                key={`${record.source_row_identity}-${record.semantic_type}-${index}`}
                record={record}
                t={t}
              />
            ))}
          </div>
        </details>
      )}
      <PricingDisclaimer messages={t} />
    </main>
  );
}

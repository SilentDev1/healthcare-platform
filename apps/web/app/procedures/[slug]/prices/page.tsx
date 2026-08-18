import Link from "next/link";
import { apiGet, type Procedure, type DtcOptions as DtcOptionsData } from "../../../../lib/api";
import { ErrorState } from "../../../components/ui";
import { DtcOptions } from "../../../components/DtcOptions";
import {
  ProcedureResults,
  type ProcedureResultsFilters,
} from "../../../components/ProcedureResults";
import { launchRegion } from "../../../../lib/brand";
import { askMessages } from "../../../../lib/ask-i18n";
import { localePath } from "../../../../lib/i18n";
import { requestLocale, requestMessages } from "../../../../lib/i18n-server";
import { PopularSearches } from "../../../components/PopularSearches";
import { ExperienceTrigger } from "../../../components/GlobalExperience";

export default async function ProcedurePrices({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<ProcedureResultsFilters>;
}) {
  const { slug } = await params;
  const filters = await searchParams;
  const messages = await requestMessages();
  const locale = await requestLocale();
  const basePath = `/procedures/${slug}/prices`;

  let procedure: Procedure;
  try {
    procedure = await apiGet<Procedure>(
      `/api/v1/procedures/${encodeURIComponent(slug)}`,
    );
  } catch {
    return (
      <main>
        <ErrorState retryHref={localePath(locale, basePath)} messages={messages} />
      </main>
    );
  }

  // Verified national DTC self-pay options (a SEPARATE surface from the per-location
  // comparison). Fetched server-side; degrades to nothing if the endpoint is empty
  // or unavailable — never blocks the comparison.
  let dtc: DtcOptionsData | null = null;
  try {
    const fetched = await apiGet<DtcOptionsData>(
      `/api/v1/procedures/${encodeURIComponent(slug)}/dtc-options`,
    );
    if (fetched.options?.length) dtc = fetched;
  } catch {
    dtc = null;
  }
  const selfPayFirst = filters.pay === "self";
  const paymentHref = (pay?: string) => {
    const next = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) if (value && key !== "pay") next.set(key, value);
    if (pay) next.set("pay", pay);
    return localePath(locale, `${basePath}${next.size ? `?${next}` : ""}`);
  };
  const dtcSection = dtc ? (
    <DtcOptions data={dtc} messages={messages} locale={locale} />
  ) : null;

  return (
    <main>
      <PopularSearches
        locale={locale}
        heading={messages.popular}
        viewAllLabel={messages.viewAllProcedures}
      />
      <nav className="breadcrumbs" aria-label={messages.breadcrumb}>
        <Link href={localePath(locale, "/")}>{messages.home}</Link>
        <span>/</span>
        <Link href={localePath(locale, "/procedures")}>
          {messages.procedures}
        </Link>
        <span>/</span>
        <Link href={localePath(locale, `/procedures/${slug}`)}>
          {procedure.consumer_name}
        </Link>
        <span>/</span>
        <span>{messages.comparePrices}</span>
      </nav>
      <div style={{ margin: "0.25rem 0 0.75rem" }}>
        <ExperienceTrigger kind="ask" query={`${procedure.consumer_name} prices in NH`} className="ask-inline-entry">
          ✨ {askMessages[locale].navLabel}
        </ExperienceTrigger>
      </div>
      <div className="page-heading comparison-heading">
        <h1>{procedure.consumer_name}</h1>
        <p className="lede">{procedure.short_description || messages.ledeSummary.replace("{region}", launchRegion.name)}</p>
      </div>
      <section className="payment-mode" aria-labelledby="payment-mode-heading"><h2 id="payment-mode-heading">{messages.coverage}</h2><div><Link className={selfPayFirst ? "is-active" : ""} href={paymentHref("self")}>{messages.selfPay} / {messages.selfPayTitle}</Link><Link className={!selfPayFirst ? "is-active" : ""} href={paymentHref()}>{messages.chooseInsurance}</Link></div><p>{filters.location || launchRegion.name}</p></section>
      {selfPayFirst ? dtcSection : null}
      <ProcedureResults
        slug={slug}
        procedureName={procedure.consumer_name}
        filters={filters}
        locale={locale}
        messages={messages}
        basePath={basePath}
      />
      {selfPayFirst ? null : dtcSection}
    </main>
  );
}

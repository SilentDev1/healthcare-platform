import Link from "next/link";
import { apiGet, type Procedure } from "../../../../lib/api";
import { ErrorState } from "../../../components/ui";
import {
  ProcedureResults,
  type ProcedureResultsFilters,
} from "../../../components/ProcedureResults";
import { launchRegion } from "../../../../lib/brand";
import { localePath } from "../../../../lib/i18n";
import { requestLocale, requestMessages } from "../../../../lib/i18n-server";
import { PopularSearches } from "../../../components/PopularSearches";

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

  const payerName = undefined;
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
      <div className="page-heading comparison-heading">
        <p className="eyebrow">{messages.compareServiceLocations}</p>
        <h1>{procedure.consumer_name}</h1>
        <p className="lede">
          {messages.ledeSummary.replace("{region}", launchRegion.name)}
        </p>
      </div>
      <dl className="decision-context" aria-label={messages.comparisonContext}>
        <div>
          <dt>{messages.location}</dt>
          <dd>{filters.location || launchRegion.name}</dd>
        </div>
        <div>
          <dt>{messages.coverage}</dt>
          <dd>
            {payerName ?? `${messages.selfPay} · ${messages.chooseInsurance}`}
          </dd>
        </div>
      </dl>
      <ProcedureResults
        slug={slug}
        procedureName={procedure.consumer_name}
        filters={filters}
        locale={locale}
        messages={messages}
        basePath={basePath}
      />
    </main>
  );
}

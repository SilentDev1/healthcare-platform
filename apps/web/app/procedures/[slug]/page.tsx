import { notFound } from "next/navigation";
import Link from "next/link";
import { apiGet, Procedure, type ProcedureComparison } from "../../../lib/api";
import {
  CoverageNotice,
  PriceRange,
  PricingDisclaimer,
  SourceAttribution,
} from "../../components/ui";
import { launchRegion } from "../../../lib/brand";

export default async function ProcedureDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let item: Procedure;
  let comparison: ProcedureComparison | null = null;
  try {
    item = await apiGet<Procedure>(
      `/api/v1/procedures/${encodeURIComponent(slug)}`,
    );
  } catch {
    notFound();
  }
  try {
    comparison = await apiGet<ProcedureComparison>(
      `/api/v1/procedures/${encodeURIComponent(slug)}/comparison?state=${launchRegion.state}`,
    );
  } catch {}
  const priced =
    comparison?.items.filter((price) => price.price_available) ?? [];
  const cashMins = priced
    .map((price) => price.cash_price_min)
    .filter((value): value is string => value !== null);
  const cashMaxes = priced
    .map((price) => price.cash_price_max)
    .filter((value): value is string => value !== null);
  const negotiatedMins = priced
    .map((price) => price.negotiated_price_min)
    .filter((value): value is string => value !== null);
  const negotiatedMaxes = priced
    .map((price) => price.negotiated_price_max)
    .filter((value): value is string => value !== null);
  return (
    <main>
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span>/</span>
        <Link href="/procedures">Procedures</Link>
        <span>/</span>
        <span>{item.consumer_name}</span>
      </nav>
      <p className="eyebrow">{item.category.name}</p>
      <h1>{item.consumer_name}</h1>
      <p className="lede">{item.long_description}</p>
      <div className="feature-grid">
        <section className="card">
          <h2>Typical setting</h2>
          <p>{item.service_setting.replaceAll("_", " ")}</p>
        </section>
        <section className="card">
          <h2>What the price may include</h2>
          <p>{item.billing_notice}</p>
        </section>
        <section className="card">
          <h2>What may be separate</h2>
          <p>
            Professional fees, anesthesia, pathology, labs, medications,
            implants, or related services can be billed separately.
          </p>
        </section>
      </div>
      <section
        className="price-overview"
        aria-labelledby="price-overview-heading"
      >
        <div className="section-heading">
          <p className="eyebrow">Price overview</p>
          <h2 id="price-overview-heading">
            Published ranges in {launchRegion.name}
          </h2>
        </div>
        <div className="price-overview-grid">
          <article>
            <span>Cash price range</span>
            <strong>
              <PriceRange
                min={
                  cashMins.length
                    ? String(Math.min(...cashMins.map(Number)))
                    : null
                }
                max={
                  cashMaxes.length
                    ? String(Math.max(...cashMaxes.map(Number)))
                    : null
                }
              />
            </strong>
          </article>
          <article>
            <span>Negotiated price range</span>
            <strong>
              <PriceRange
                min={
                  negotiatedMins.length
                    ? String(Math.min(...negotiatedMins.map(Number)))
                    : null
                }
                max={
                  negotiatedMaxes.length
                    ? String(Math.max(...negotiatedMaxes.map(Number)))
                    : null
                }
              />
            </strong>
          </article>
          <article>
            <span>Hospitals with prices</span>
            <strong>{comparison?.facilities_with_prices ?? 0}</strong>
          </article>
        </div>
      </section>
      <section className="section" style={{ paddingInline: 0 }}>
        <div className="section-heading">
          <p className="eyebrow">Nearby comparisons</p>
          <h2>Published price availability</h2>
        </div>
        <CoverageNotice>
          This procedure currently has published prices from{" "}
          {comparison?.facilities_with_prices ?? 0} of{" "}
          {comparison?.active_facilities ?? "the"} active hospitals in the
          launch region. Hospitals without a publishable price remain visible in
          comparison results.
        </CoverageNotice>
        <Link className="button" href={`/procedures/${item.slug}/prices`}>
          Compare facilities
        </Link>
      </section>
      <section className="card">
        <h2>Quality considerations</h2>
        <p>
          CMS quality measures can add context, but no single measure determines
          which facility is right for you. Discuss clinical needs with a
          qualified healthcare professional.
        </p>
        <p>Related terms: {item.aliases.join(", ") || "None listed"}</p>
      </section>
      <SourceAttribution quality />
      <PricingDisclaimer />
      <p className="muted">
        This is general educational information, not individualized medical
        advice.
      </p>
    </main>
  );
}

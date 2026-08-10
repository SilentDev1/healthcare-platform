import { notFound } from "next/navigation";
import Link from "next/link";
import { apiGet, Procedure, type PricePage } from "../../../lib/api";
import {
  CoverageNotice,
  PricingDisclaimer,
  SourceAttribution,
} from "../../components/ui";

export default async function ProcedureDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let item: Procedure;
  let prices: PricePage = { items: [], total: 0, page: 1, page_size: 6 };
  try {
    item = await apiGet<Procedure>(
      `/api/v1/procedures/${encodeURIComponent(slug)}`,
    );
  } catch {
    notFound();
  }
  try {
    prices = await apiGet<PricePage>(
      `/api/v1/procedures/${encodeURIComponent(slug)}/prices?state=NH&page_size=6`,
    );
  } catch {}
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
      <section className="section" style={{ paddingInline: 0 }}>
        <div className="section-heading">
          <p className="eyebrow">Nearby comparisons</p>
          <h2>Published price availability</h2>
        </div>
        <CoverageNotice>
          This procedure currently has {prices.total} publishable price{" "}
          {prices.total === 1 ? "summary" : "summaries"}. Hospitals without a
          publishable price remain visible in the hospital directory.
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

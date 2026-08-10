import Link from "next/link";
import { CareSearch } from "./components/CareSearch";
import { CoverageNotice } from "./components/ui";
import { apiGet } from "../lib/api";

interface Coverage {
  nh_facilities: number;
  facilities_with_publishable_prices: number;
  publishable_procedures: number;
}
const popular = [
  "MRI",
  "CT scan",
  "colonoscopy",
  "mammogram",
  "knee replacement",
  "hip replacement",
  "childbirth",
  "lab tests",
];

export default async function Home() {
  let coverage: Coverage | null = null;
  try {
    coverage = await apiGet<Coverage>("/api/v1/pricing/coverage");
  } catch {}
  return (
    <>
      <main className="hero">
        <div className="hero-inner">
          <p className="eyebrow">Clear information for confident choices</p>
          <h1>Compare healthcare costs near you</h1>
          <p className="lede">
            Explore published hospital prices and CMS quality information in one
            straightforward place.
          </p>
          <CareSearch showInsurance />
          <div className="popular">
            <span>Popular:</span>
            {popular.map((term) => (
              <Link
                className="chip"
                key={term}
                href={`/search?q=${encodeURIComponent(term)}`}
              >
                {term}
              </Link>
            ))}
          </div>
        </div>
      </main>
      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">How it works</p>
          <h2>A clearer path to comparing care</h2>
          <p>No billing-code knowledge required.</p>
        </div>
        <div className="feature-grid steps">
          {[
            [
              "Search for care",
              "Use everyday language, like “knee MRI” or “mammogram.”",
            ],
            [
              "Compare facilities",
              "Review published prices, locations, and service settings.",
            ],
            [
              "Review quality",
              "Use CMS measures as context—not as a single best-hospital score.",
            ],
            [
              "Verify your choice",
              "Confirm your benefits and expected charges with the provider and insurer.",
            ],
          ].map(([title, body]) => (
            <article className="card feature-card" key={title}>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </section>
      <div className="trust-strip">
        <section className="section">
          <div>
            <h2>Know where the information comes from</h2>
            <p>
              Hospital machine-readable files for prices. CMS Care Compare for
              quality.
            </p>
          </div>
          <Link className="button secondary" href="/procedures">
            Explore procedures
          </Link>
        </section>
      </div>
      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">Built for trust</p>
          <h2>Real published data, with gaps shown clearly</h2>
        </div>
        <div className="feature-grid">
          {[
            [
              "Public pricing data",
              "We show reviewed, publishable hospital data—not generated estimates.",
            ],
            [
              "Quality in context",
              "CMS measures are presented without declaring a “best” hospital.",
            ],
            [
              "Source dates included",
              "Meaningful price views identify their source and latest update.",
            ],
          ].map(([title, body]) => (
            <article className="card feature-card" key={title}>
              <span className="icon" aria-hidden="true">
                ✓
              </span>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
        <CoverageNotice>
          {coverage
            ? `Published prices are currently available for ${coverage.facilities_with_publishable_prices} of ${coverage.nh_facilities} active hospitals in the launch region, covering ${coverage.publishable_procedures} procedures.`
            : "Coverage is incomplete and varies by hospital and procedure. Availability is always shown with each result."}
        </CoverageNotice>
      </section>
    </>
  );
}

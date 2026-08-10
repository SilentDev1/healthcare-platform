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
      <main className="hero product-hero">
        <div className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Clear information for confident choices</p>
            <h1>
              Compare healthcare <span>prices</span> near you.
            </h1>
            <p className="lede">
              Compare published prices for procedures and services at New
              Hampshire hospitals. Review pricing, location, and available CMS
              quality information before choosing care.
            </p>
            <p className="hero-assurance">
              <strong>Free to use</strong> <i aria-hidden="true">•</i> No
              account required <i aria-hidden="true">•</i> Published hospital
              data
            </p>
          </div>
          <div
            className="coverage-visual"
            aria-label="New Hampshire launch region"
          >
            <div className="region-label">
              <span>New Hampshire</span>
              <strong>Carevero launch region</strong>
            </div>
            <span className="map-marker marker-one" aria-hidden="true">
              +
            </span>
            <span className="map-marker marker-two" aria-hidden="true">
              +
            </span>
            <span className="map-marker marker-three" aria-hidden="true">
              +
            </span>
            <div className="trust-card trust-card-top">
              <span aria-hidden="true">✓</span>
              <div>
                <strong>Published pricing</strong>
                <small>Hospital machine-readable files</small>
              </div>
            </div>
            <div className="trust-card trust-card-bottom">
              <span aria-hidden="true">○</span>
              <div>
                <strong>No account required</strong>
                <small>Search and compare anonymously</small>
              </div>
            </div>
          </div>
        </div>
        <div className="hero-search-panel">
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
      <section className="section product-intro">
        <div className="section-heading">
          <p className="eyebrow">How it works</p>
          <h2>Search, compare, then verify</h2>
        </div>
        <div className="feature-grid steps product-steps">
          {[
            [
              "Search",
              "Use everyday language, like “knee MRI” or “mammogram.”",
            ],
            [
              "Compare",
              "Review published prices, locations, and service settings.",
            ],
            [
              "Verify",
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
      <section className="section compact-trust">
        <div>
          <p className="eyebrow">Real published data</p>
          <h2>Prices with sources and limitations attached</h2>
          <p>
            Hospital files provide pricing. CMS Care Compare provides applicable
            quality information. Missing data stays visibly missing.
          </p>
        </div>
        <CoverageNotice>
          {coverage
            ? `Published prices are currently available for ${coverage.facilities_with_publishable_prices} of ${coverage.nh_facilities} active hospitals in the launch region, covering ${coverage.publishable_procedures} procedures.`
            : "Coverage is incomplete and varies by hospital and procedure. Availability is always shown with each result."}
        </CoverageNotice>
        <Link className="button secondary" href="/about-data">
          View coverage and methodology
        </Link>
      </section>
    </>
  );
}

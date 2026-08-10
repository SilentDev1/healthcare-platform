import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "Learn how to search, compare hospital-published prices, review CMS quality information, and verify your choice with Carevero.",
  alternates: { canonical: "/how-it-works" },
};

export default function HowItWorksPage() {
  return (
    <main className="narrow">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span>/</span>
        <span>How it works</span>
      </nav>
      <p className="eyebrow">Simple, anonymous comparison</p>
      <h1>How Carevero works</h1>
      <p className="lede">
        Search and compare without an account. You do not need medical billing
        codes.
      </p>
      <ol className="process-list">
        <li>
          <strong>Search for care.</strong> Use a familiar term such as “knee
          MRI,” plus an optional city, ZIP, or payer.
        </li>
        <li>
          <strong>Review service locations.</strong> Compare published cash and
          negotiated prices, CMS ratings, and coverage gaps.
        </li>
        <li>
          <strong>Compare like with like.</strong> Choose two or three physical
          locations for the same procedure.
        </li>
        <li>
          <strong>Verify before care.</strong> Contact the hospital and insurer
          to confirm network status, benefits, and what may be billed
          separately.
        </li>
      </ol>
      <Link className="button" href="/search">
        Search Carevero
      </Link>
    </main>
  );
}

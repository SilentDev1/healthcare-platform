import type { Metadata } from "next";
import Link from "next/link";
import { PricingDisclaimer } from "../components/ui";

export const metadata: Metadata = {
  title: "About the data",
  description:
    "How Carevero uses hospital-published prices and CMS quality information, including important coverage limitations.",
  alternates: { canonical: "/about-data" },
};

export default function AboutDataPage() {
  return (
    <main className="narrow">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span>/</span>
        <span>About the data</span>
      </nav>
      <p className="eyebrow">Transparency first</p>
      <h1>About Carevero’s data</h1>
      <p className="lede">
        Carevero organizes hospital-published price files and CMS quality data
        so they are easier to compare. We do not generate or predict prices.
      </p>
      <section>
        <h2>Where prices come from</h2>
        <p>
          Hospitals publish machine-readable price files. Carevero reviews and
          normalizes eligible records, connects them to a procedure and physical
          service location, and links displayed prices back to the official
          source file.
        </p>
      </section>
      <section>
        <h2>What negotiated rates mean</h2>
        <p>
          A published negotiated rate is a rate listed for a payer or plan. It
          does not guarantee that you are in network, covered, or eligible for
          that rate. Confirm benefits and expected costs with the hospital and
          insurer.
        </p>
      </section>
      <section>
        <h2>Coverage and updates</h2>
        <p>
          Coverage varies by hospital, procedure, payer, and location. Missing
          pricing does not mean a service is unavailable. Carevero shows the
          last update alongside published prices and keeps hospitals visible
          when their pricing cannot be published safely.
        </p>
      </section>
      <section>
        <h2>Quality information</h2>
        <p>
          Quality measures come from CMS Care Compare. They provide context but
          are not a recommendation and cannot predict an individual outcome.
        </p>
      </section>
      <PricingDisclaimer />
    </main>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { PricingDisclaimer } from "../components/ui";
import { localePath } from "../../lib/i18n";
import { requestLocale, requestMessages } from "../../lib/i18n-server";

export const metadata: Metadata = {
  title: "About the data",
  description:
    "How Carevero uses hospital-published prices and CMS quality information, including important coverage limitations.",
  alternates: { canonical: "/about-data" },
};

export default async function AboutDataPage() {
  const locale = await requestLocale();
  const t = await requestMessages();
  return (
    <main className="narrow">
      <nav className="breadcrumbs" aria-label={t.breadcrumb}>
        <Link href={localePath(locale, "/")}>{t.home}</Link>
        <span>/</span>
        <span>{t.aboutData}</span>
      </nav>
      <p className="eyebrow">{t.adEyebrow}</p>
      <h1>{t.adTitle}</h1>
      <p className="lede">{t.adLede}</p>
      <section>
        <h2>{t.adSourcesHeading}</h2>
        <p>{t.adSourcesBody}</p>
      </section>
      <section>
        <h2>{t.adNegotiatedHeading}</h2>
        <p>{t.adNegotiatedBody}</p>
      </section>
      <section>
        <h2>{t.adCoverageHeading}</h2>
        <p>{t.adCoverageBody}</p>
      </section>
      <section>
        <h2>{t.adQualityHeading}</h2>
        <p>{t.adQualityBody}</p>
      </section>
      <PricingDisclaimer messages={t} />
    </main>
  );
}

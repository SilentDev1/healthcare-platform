import type { Metadata } from "next";
import Link from "next/link";
import { localePath } from "../../lib/i18n";
import { requestLocale, requestMessages } from "../../lib/i18n-server";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "Learn how to search, compare hospital-published prices, review CMS quality information, and verify your choice with Carevero.",
  alternates: { canonical: "/how-it-works" },
};

export default async function HowItWorksPage() {
  const locale = await requestLocale();
  const t = await requestMessages();
  return (
    <main className="narrow">
      <nav className="breadcrumbs" aria-label={t.breadcrumb}>
        <Link href={localePath(locale, "/")}>{t.home}</Link>
        <span>/</span>
        <span>{t.howItWorks}</span>
      </nav>
      <p className="eyebrow">{t.hiwEyebrow}</p>
      <h1>{t.hiwTitle}</h1>
      <p className="lede">{t.hiwLede}</p>
      <ol className="process-list">
        <li>
          <strong>{t.hiwStep1Title}</strong> {t.hiwStep1Body}
        </li>
        <li>
          <strong>{t.hiwStep2Title}</strong> {t.hiwStep2Body}
        </li>
        <li>
          <strong>{t.hiwStep3Title}</strong> {t.hiwStep3Body}
        </li>
        <li>
          <strong>{t.hiwStep4Title}</strong> {t.hiwStep4Body}
        </li>
      </ol>
      <Link className="button" href={localePath(locale, "/search")}>
        {t.hiwSearchCta}
      </Link>
    </main>
  );
}

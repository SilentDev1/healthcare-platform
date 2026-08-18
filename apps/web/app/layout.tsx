import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import "./styles.css";
import "leaflet/dist/leaflet.css";
import { brand } from "../lib/brand";
import { localePath } from "../lib/i18n";
import { navigationMessages } from "../lib/navigation-i18n";
import { requestLocale, requestMessages } from "../lib/i18n-server";
import { GlobalExperience } from "./components/GlobalExperience";
import { NavigationHeader } from "./components/NavigationHeader";
export function seoRobots(
  indexingEnabled = process.env.SEO_INDEXING_ENABLED,
): Metadata["robots"] {
  return indexingEnabled === "false"
    ? { index: false, follow: false, nocache: true }
    : undefined;
}
export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: {
    default: `${brand.name} | Compare healthcare prices`,
    template: `%s | ${brand.name}`,
  },
  description: brand.description,
  robots: seoRobots(),
  openGraph: {
    title: brand.name,
    description: brand.description,
    type: "website",
  },
};
export default async function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const betaMode = process.env.BETA_MODE === "true";
  const feedbackEmail = process.env.BETA_FEEDBACK_EMAIL;
  const feedbackEnabled =
    process.env.FEEDBACK_ENABLED === "true" && feedbackEmail;
  const locale = await requestLocale();
  const t = await requestMessages();
  const nav = navigationMessages[locale];
  return (
    <html lang={locale} data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#main-content">
          {t.skip}
        </a>
        <header className="site-header">
          <Link className="brand" href={localePath(locale, "/")}>
            <Image
              className="brand-logo"
              src="/brand/carevero-mark.svg"
              alt=""
              width="48"
              height="48"
            />
            <span className="brand-name">{brand.logoText}</span>
            {betaMode && (
              <span className="beta-badge">{t.privateBetaBadge}</span>
            )}
          </Link>
          <Suspense fallback={null}>
            <NavigationHeader locale={locale} languageLabel={t.language} />
          </Suspense>
        </header>
        <GlobalExperience locale={locale} />
        <div id="main-content">{children}</div>
        <footer className="footer">
          <div className="footer-inner">
            <div>
              <strong>{brand.name}</strong>
              <p>{brand.tagline}</p>
              <nav aria-label={t.footerNavigation}>
                <Link href={localePath(locale, "/search")}>{nav.findCare}</Link>
                <Link href={localePath(locale, "/providers")}>
                  {nav.providers}
                </Link>
                <Link href={localePath(locale, "/how-it-works")}>
                  {nav.howItWorks}
                </Link>
                <Link href={localePath(locale, "/about-data")}>
                  {nav.aboutData}
                </Link>
                <Link href={localePath(locale, "/privacy")}>{t.privacy}</Link>
                <Link href={localePath(locale, "/terms")}>{t.terms}</Link>
                {feedbackEnabled && (
                  <a
                    href={`mailto:${feedbackEmail}?subject=Carevero beta feedback&body=Please don't include private medical information.%0A%0APage: `}
                  >
                    {t.betaFeedbackLink}
                  </a>
                )}
              </nav>
              {betaMode && <p>{t.betaExpanding}</p>}
              {feedbackEnabled && <p>{t.feedbackNoPrivateInfo}</p>}
            </div>
            <p>{t.footerDisclaimer}</p>
          </div>
        </footer>
      </body>
    </html>
  );
}

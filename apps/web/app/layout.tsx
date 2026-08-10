import type { Metadata } from "next";
import Link from "next/link";
import "./styles.css";
import "leaflet/dist/leaflet.css";
import { brand } from "../lib/brand";
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
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const betaMode = process.env.BETA_MODE === "true";
  const feedbackEmail = process.env.BETA_FEEDBACK_EMAIL;
  const feedbackEnabled =
    process.env.FEEDBACK_ENABLED === "true" && feedbackEmail;
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <header className="site-header">
          <Link className="brand" href="/">
            <span className="brand-mark" aria-hidden="true">
              +
            </span>
            {brand.logoText}
            {betaMode && <span className="beta-badge">Private Beta</span>}
          </Link>
          <nav aria-label="Main navigation">
            <Link className="nav-primary" href="/search">
              Find prices
            </Link>
            <Link href="/hospitals">Hospitals</Link>
            <Link href="/procedures">Procedures</Link>
            <Link href="/map">Map</Link>
            <Link href="/how-it-works">How it works</Link>
          </nav>
        </header>
        <div id="main-content">{children}</div>
        <footer className="footer">
          <div className="footer-inner">
            <div>
              <strong>{brand.name}</strong>
              <p>{brand.tagline}</p>
              <nav aria-label="Footer navigation">
                <Link href="/about-data">About the data</Link>
                <Link href="/how-it-works">How it works</Link>
                <Link href="/hospitals">Hospitals</Link>
                <Link href="/procedures">Procedures</Link>
                <Link href="/privacy">Privacy</Link>
                <Link href="/terms">Terms &amp; disclaimers</Link>
                {feedbackEnabled && (
                  <a
                    href={`mailto:${feedbackEmail}?subject=Carevero beta feedback&body=Please don't include private medical information.%0A%0APage: `}
                  >
                    Send beta feedback
                  </a>
                )}
              </nav>
              {betaMode && (
                <p>Carevero is in beta and expanding hospital coverage.</p>
              )}
              {feedbackEnabled && (
                <p>
                  Please don’t include private medical information in feedback.
                </p>
              )}
            </div>
            <p>
              Published hospital prices are estimates for comparison, not a
              quote or guarantee. Verify costs and network participation with
              your hospital and insurer.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}

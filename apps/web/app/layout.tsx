import type { Metadata } from "next";
import Link from "next/link";
import "./styles.css";
import { brand } from "../lib/brand";
export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: {
    default: `${brand.name} | Compare healthcare prices`,
    template: `%s | ${brand.name}`,
  },
  description: brand.description,
  openGraph: {
    title: brand.name,
    description: brand.description,
    type: "website",
  },
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link className="brand" href="/">
            <span className="brand-mark" aria-hidden="true">
              +
            </span>
            {brand.logoText}
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/search">Find care</Link>
            <Link href="/hospitals">Hospitals</Link>
            <Link href="/procedures">Procedures</Link>
            <Link href="/map">Map</Link>
          </nav>
        </header>
        {children}
        <footer className="footer">
          <div className="footer-inner">
            <div>
              <strong>{brand.name}</strong>
              <p>{brand.tagline}</p>
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

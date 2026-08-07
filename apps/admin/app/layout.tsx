import type { Metadata } from "next";
import Link from "next/link";
import "./styles.css";

export const metadata: Metadata = { title: "CareCompare Admin" };

export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header>
          <Link href="/">CareCompare operations</Link>
          <nav aria-label="Admin navigation">
            <Link href="/">Dashboard</Link>
            <Link href="/facilities">Facilities</Link>
            <Link href="/imports">Imports</Link>
            <Link href="/source-files">Source files</Link>
            <Link href="/unmatched-records">Unmatched records</Link>
            <Link href="/quality-measures">Quality measures</Link>
            <Link href="/search">Search</Link>
            <Link href="/procedures">Procedures</Link>
            <Link href="/identities">Facility identities</Link>
            <Link href="/identity-candidates">Identity candidates</Link>
            <Link href="/data-health">Data health</Link>
            <Link href="/pipeline-status">Pipelines</Link>
            <Link href="/search-index">Search index</Link>
            <Link href="/pricing">Pricing</Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}

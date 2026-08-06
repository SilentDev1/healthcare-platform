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
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}

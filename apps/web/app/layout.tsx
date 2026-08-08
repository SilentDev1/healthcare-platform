import type { Metadata } from "next";
import Link from "next/link";
import "./styles.css";
export const metadata: Metadata = {
  title: "CareCompare",
  description: "Compare healthcare facilities",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header>
          <Link href="/">CareCompare</Link>
          <nav aria-label="Main navigation">
            <Link href="/search?q=hospital">Search</Link>
            <Link href="/facilities">Facilities</Link>
            <Link href="/procedures">Procedures</Link>
            <Link href="/map">Map</Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}

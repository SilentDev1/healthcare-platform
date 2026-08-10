import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Search",
  description:
    "Search Carevero for procedures, hospitals, cities, and ZIP codes.",
  robots: { index: false, follow: true },
};

export default function SearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
